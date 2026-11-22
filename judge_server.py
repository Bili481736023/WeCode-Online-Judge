# -*- coding: utf-8 -*-
"""
WeCode Online Judge - 后端服务
- 首次启动配置向导
- 扫描 problems/Qxxxx/ 目录作为题库
- data/ 目录存放用户、提交、标签、令牌
- 判题：编译运行 C++/Python，遍历 testcases/*.in/*.out
- 静态文件服务：白名单方式伺服 index.html / css / js / assets
- 认证：HttpOnly Cookie 会话令牌
- 密码：PBKDF2-SHA256 加盐哈希（旧明文自动迁移）
- CSRF：SameSite=Lax + Origin 校验
- 并发：全局锁保护 JSON 读写
- 日志：判题结果写入 logs/judge.log
仅使用 Python 标准库，MIT 协议。
"""

import os
import sys
import json
import copy
import time
import re
import signal
import hashlib
import threading
import subprocess
import tempfile
import shutil
import datetime
import secrets
import socket
import urllib.parse
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler


# ============================================================
# 1. 路径与全局状态
# ============================================================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(ROOT_DIR, 'config.json')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
PROBLEMS_DIR = os.path.join(ROOT_DIR, 'problems')
LOGS_DIR = os.path.join(ROOT_DIR, 'logs')

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
SUBMISSIONS_FILE = os.path.join(DATA_DIR, 'submissions.json')
TAGS_FILE = os.path.join(DATA_DIR, 'tags.json')
TOKENS_FILE = os.path.join(DATA_DIR, 'tokens.json')
JUDGE_LOG_FILE = os.path.join(LOGS_DIR, 'judge.log')

STATIC_ALLOWED_FILES = {'index.html', 'back_platform.html'}
STATIC_ALLOWED_DIRS = ('css/', 'js/', 'assets/')

COOKIE_NAME = 'woj_token'
COOKIE_TTL_SECONDS = 7 * 24 * 3600
TOKEN_TTL_DAYS = 7

PBKDF2_ITERATIONS = 200_000
MAX_BODY_BYTES = 512 * 1024

MAX_CONCURRENT_REQUESTS = 32
REQUEST_TIMEOUT_SECONDS = 30

JUDGE_LOG_MAX_BYTES = 5 * 1024 * 1024
SUBMISSIONS_PAGE_SIZE_DEFAULT = 100
SUBMISSIONS_PAGE_SIZE_MAX = 200

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

DATA_LOCK = threading.RLock()
LOG_LOCK = threading.Lock()
RATE_LOCK = threading.Lock()
RATE_BUCKETS = {}

# 限制同时进行的判题数量，避免并发编译/运行把 CPU 打满、拖慢整体服务
JUDGE_SEMAPHORE = threading.BoundedSemaphore(2)

config = {}
GPP_PATH = None
PYTHON_PATH = None
LOGIN_FAILS = {}


# ============================================================
# 2. 通用工具
# ============================================================
def load_json(path, default):
    """读取 JSON；解析失败时先备份损坏文件，再返回默认值，避免被静默覆盖。"""
    with DATA_LOCK:
        if not os.path.exists(path):
            return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            backup = (
                f"{path}.corrupt-"
                f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-"
                f"{secrets.token_hex(2)}"
            )
            try:
                os.replace(path, backup)
                print(f"[warn] {path} 解析失败，已备份为 {backup}")
            except Exception:
                pass
            return default


def save_json(path, data):
    with DATA_LOCK:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def update_json(path, default, mutator):
    """在同一把锁内完成 load -> mutator(data) -> save，避免并发丢更新。"""
    with DATA_LOCK:
        data = load_json(path, default)
        result = mutator(data)
        save_json(path, data)
        return result


def now_iso():
    return datetime.datetime.now().isoformat()


def _one_line(s, limit=None):
    text = ' '.join((s or '').splitlines())
    if limit is not None:
        text = text[:limit]
    return text


def _str_field(data, key, default=''):
    v = data.get(key, default)
    return v if isinstance(v, str) else default


def _valid_email(email):
    return (not email) or bool(EMAIL_RE.match(email))


def _lan_ip():
    """尽力获取本机在局域网中的 IP，用于启动提示；失败则回退到回环地址。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def normalize_text(s):
    """忽略行尾空白和末尾空行，但保留行首空白。"""
    if s is None:
        return ''
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.rstrip() for line in s.split('\n')]
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def clamp_time_limit(value, default=2000):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(100, min(n, 10000))


def _rate_limit(key, limit, window_seconds):
    """简单滑动窗口限流，内存实现；超过 limit 时返回 False。"""
    now = time.time()
    with RATE_LOCK:
        bucket = RATE_BUCKETS.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window_seconds]
        if len(bucket) >= limit:
            return False
        bucket.append(now)

        if len(RATE_BUCKETS) > 50000:
            for k in list(RATE_BUCKETS.keys()):
                if not RATE_BUCKETS[k]:
                    del RATE_BUCKETS[k]
        return True


def log_judge(user_id, username, problem_id, language, status, detail):
    """把每次判题结果追加写入 logs/judge.log，超过大小自动轮转。"""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        detail_one_line = _one_line(detail, 300)
        line = (
            f"[{ts}] uid={user_id} ({_one_line(username)}) "
            f"problem={_one_line(str(problem_id))} lang={_one_line(language)} "
            f"status={_one_line(status)} detail={detail_one_line}\n"
        )
        with LOG_LOCK:
            if (os.path.exists(JUDGE_LOG_FILE)
                    and os.path.getsize(JUDGE_LOG_FILE) > JUDGE_LOG_MAX_BYTES):
                try:
                    os.replace(JUDGE_LOG_FILE, JUDGE_LOG_FILE + '.1')
                except OSError:
                    pass
            with open(JUDGE_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(line)
    except Exception:
        pass


# ============================================================
# 2.1 密码哈希（PBKDF2-SHA256）
# ============================================================
def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password, stored):
    if not stored:
        return False, False
    if stored.startswith('pbkdf2_sha256$'):
        try:
            _, iters_s, salt_hex, hash_hex = stored.split('$')
            iters = int(iters_s)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
            dk = hashlib.pbkdf2_hmac(
                'sha256', password.encode('utf-8'), salt, iters
            )
            return secrets.compare_digest(dk, expected), False
        except Exception:
            return False, False
    try:
        ok = secrets.compare_digest(
            stored.encode('utf-8'), password.encode('utf-8')
        )
    except Exception:
        ok = False
    return ok, ok


_DUMMY_HASH = None


def _get_dummy_hash():
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    return _DUMMY_HASH


# ============================================================
# 2.5 会话令牌
# ============================================================
def _parse_iso(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def create_token(user_id):
    tok = secrets.token_urlsafe(32)
    now = datetime.datetime.now()

    def mutate(tokens):
        for t in list(tokens.keys()):
            created = _parse_iso(tokens[t].get('createdAt', ''))
            if created is None or (now - created).days >= TOKEN_TTL_DAYS:
                del tokens[t]
        tokens[tok] = {'userId': user_id, 'createdAt': now.isoformat()}

    update_json(TOKENS_FILE, {}, mutate)
    return tok


def user_from_token(token):
    if not token:
        return None
    tokens = load_json(TOKENS_FILE, {})
    entry = tokens.get(token)
    if not entry:
        return None

    created = _parse_iso(entry.get('createdAt', ''))
    if created is None or (datetime.datetime.now() - created).days >= TOKEN_TTL_DAYS:
        revoke_token(token)
        return None

    users = load_json(USERS_FILE, [])
    if not isinstance(users, list):
        users = []
    return next(
        (u for u in users if isinstance(u, dict) and u.get('id') == entry.get('userId')),
        None,
    )


def revoke_token(token):
    if not token:
        return

    def mutate(tokens):
        tokens.pop(token, None)

    update_json(TOKENS_FILE, {}, mutate)


# ============================================================
# 3. g++ / Python 自动探测
# ============================================================
def find_gpp():
    for path in os.environ.get('PATH', '').split(os.pathsep):
        p = os.path.join(path, 'g++.exe')
        if os.path.exists(p):
            return p
    candidates = [
        r"C:\Program Files (x86)\Dev-Cpp\MinGW32\bin\g++.exe",
        r"C:\Program Files\Dev-Cpp\MinGW32\bin\g++.exe",
        r"D:\Program Files (x86)\Dev-Cpp\MinGW32\bin\g++.exe",
        r"D:\Program Files\Dev-Cpp\MinGW32\bin\g++.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Dev-Cpp")
        install_dir = winreg.QueryValueEx(key, "Install_Dir")[0]
        p = os.path.join(install_dir, "MinGW32", "bin", "g++.exe")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return None


def find_python():
    for path in os.environ.get('PATH', '').split(os.pathsep):
        for name in ('python.exe', 'python3.exe'):
            p = os.path.join(path, name)
            if os.path.exists(p):
                return p
    user = os.environ.get('USERPROFILE', r'C:\Users\Default')
    candidates = [
        os.path.join(user, r'AppData\Local\Programs\Python\Python312\python.exe'),
        os.path.join(user, r'AppData\Local\Programs\Python\Python311\python.exe'),
        os.path.join(user, r'AppData\Local\Programs\Python\Python310\python.exe'),
        r'C:\Python312\python.exe',
        r'C:\Python311\python.exe',
        r'C:\Python310\python.exe',
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# ============================================================
# 4. 首次启动配置向导
# ============================================================
def run_setup_wizard():
    print()
    print("=" * 52)
    print("  WeCode Online Judge - First-Time Setup")
    print("=" * 52)
    print()

    port_in = input("[1/5] Server port [8000]: ").strip()
    try:
        port = int(port_in)
    except ValueError:
        port = 8000
    if not (1 <= port <= 65535):
        port = 8000

    detected_gpp = find_gpp()
    print()
    if detected_gpp:
        print(f"[2/5] Auto-detected g++: {detected_gpp}")
    else:
        print("[2/5] g++ not detected. Enter full path, or leave blank.")
    gpp_in = input("      Press Enter to use detected / type new path: ").strip()
    gpp = gpp_in if gpp_in else detected_gpp

    detected_py = find_python()
    print()
    if detected_py:
        print(f"[3/5] Auto-detected Python: {detected_py}")
    else:
        print("[3/5] Python not detected. Enter full path, or leave blank.")
    py_in = input("      Press Enter to use detected / type new path: ").strip()
    py = py_in if py_in else detected_py

    print()
    admin_user = input("[4/5] Admin username [admin]: ").strip() or "admin"
    admin_pass = input("[5/5] Admin password [admin123]: ").strip() or "admin123"

    cfg = {
        "port": port,
        "gpp": gpp,
        "python": py,
        "admin": {
            "username": admin_user,
            "password": admin_pass,
        },
    }
    save_json(CONFIG_FILE, cfg)
    print()
    print(f"Config saved to: {CONFIG_FILE}")
    print()
    return cfg


def load_config():
    if os.path.exists(CONFIG_FILE):
        cfg = load_json(CONFIG_FILE, {})
        if isinstance(cfg, dict) and cfg.get('port') and cfg.get('admin'):
            return cfg
        print("config.json is incomplete, re-running setup...")
    return run_setup_wizard()


# ============================================================
# 5. 内置标签（洛谷风格）
# ============================================================
DEFAULT_TAGS = [
    "模拟", "枚举", "贪心", "递归", "分治", "排序", "二分", "倍增",
    "前缀和", "差分", "递推",
    "栈", "队列", "链表", "哈希表", "并查集", "堆",
    "树状数组", "线段树", "平衡树", "树套树", "可持久化",
    "DFS", "BFS", "剪枝", "记忆化搜索", "A*",
    "最短路", "最小生成树", "拓扑排序", "强连通分量", "二分图",
    "网络流", "欧拉回路", "Tarjan", "2-SAT",
    "背包", "线性 DP", "区间 DP", "树形 DP", "状压 DP", "数位 DP",
    "单调队列优化", "斜率优化",
    "字符串", "KMP", "Trie", "AC 自动机", "后缀数组", "Manacher",
    "数论", "素数", "gcd", "逆元", "组合数学", "容斥", "博弈论",
    "概率", "快速幂", "Lucas 定理",
    "向量", "凸包", "线段相交", "扫描线",
    "数组", "字符串", "链表", "树", "排序", "搜索",
    "动态规划", "数学", "图论", "计算几何",
]
DEFAULT_TAGS = list(dict.fromkeys(DEFAULT_TAGS))


# ============================================================
# 6. 初始化数据
# ============================================================
def _make_admin_user(username, password, user_id):
    return {
        'id': user_id,
        'username': username,
        'password': hash_password(password),
        'email': '',
        'isAdmin': True,
        'isBanned': False,
        'createdAt': now_iso(),
    }


def init_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(PROBLEMS_DIR, exist_ok=True)

    admin_cfg = config.get('admin', {}) or {}
    admin_user = admin_cfg.get('username') or 'admin'
    admin_pass_plain = admin_cfg.get('password') or ''

    if not os.path.exists(USERS_FILE):
        if not admin_pass_plain:
            print()
            print("[错误] users.json 不存在，且 config.json 中无管理员密码。")
            print("       请删除 config.json 后重新运行本脚本。")
            input("按回车退出...")
            sys.exit(1)
        save_json(USERS_FILE, [_make_admin_user(admin_user, admin_pass_plain, 1)])
        print(f"[init] 已创建管理员账号 '{admin_user}'（密码已哈希存储）")
    else:
        users = load_json(USERS_FILE, [])
        if not isinstance(users, list):
            users = []
        users = [u for u in users if isinstance(u, dict)]

        if not any(u.get('isAdmin') for u in users):
            pwd = admin_pass_plain or secrets.token_urlsafe(12)
            new_id = max((u.get('id', 0) for u in users), default=0) + 1
            users.append(_make_admin_user(admin_user, pwd, new_id))
            save_json(USERS_FILE, users)
            if admin_pass_plain:
                print(f"[init] 未找到管理员，已根据 config.json 重建管理员 '{admin_user}'")
            else:
                print(f"[init] 未找到管理员，已创建临时管理员 '{admin_user}'")
                print(f"[init] 临时密码: {pwd}")

    if not os.path.exists(SUBMISSIONS_FILE):
        save_json(SUBMISSIONS_FILE, [])

    if not os.path.exists(TAGS_FILE):
        save_json(TAGS_FILE, DEFAULT_TAGS)

    if not os.path.exists(TOKENS_FILE):
        save_json(TOKENS_FILE, {})

    if admin_pass_plain:
        config['admin']['password'] = ''
        save_json(CONFIG_FILE, config)
        print("[init] 已从 config.json 清除明文管理员密码")


# ============================================================
# 7. 题目扫描
# ============================================================
def parse_problem_dir_name(name):
    if name.startswith('Q') or name.startswith('q'):
        num = name[1:]
    else:
        num = name
    try:
        return int(num)
    except ValueError:
        return None


def find_problem_dir(problem_id):
    try:
        num = int(problem_id)
    except (ValueError, TypeError):
        return None
    if not os.path.isdir(PROBLEMS_DIR):
        return None

    candidates = []
    for name in sorted(os.listdir(PROBLEMS_DIR)):
        if parse_problem_dir_name(name) == num:
            p = os.path.join(PROBLEMS_DIR, name)
            if os.path.isdir(p):
                candidates.append(p)

    if not candidates:
        return None

    canonical = os.path.join(PROBLEMS_DIR, f"Q{num:04d}")
    if canonical in candidates:
        return canonical
    exact = os.path.join(PROBLEMS_DIR, str(num))
    if exact in candidates:
        return exact
    if len(candidates) == 1:
        return candidates[0]
    return None


def scan_problems():
    result = []
    if not os.path.isdir(PROBLEMS_DIR):
        return result
    for name in sorted(os.listdir(PROBLEMS_DIR)):
        pdir = os.path.join(PROBLEMS_DIR, name)
        if not os.path.isdir(pdir):
            continue
        num = parse_problem_dir_name(name)
        if num is None:
            continue
        meta_path = os.path.join(pdir, 'meta.json')
        if not os.path.isfile(meta_path):
            continue
        meta = load_json(meta_path, {})
        if not isinstance(meta, dict):
            meta = {}
        result.append({
            'id': num,
            'title': meta.get('title', '未命名题目'),
            'difficulty': meta.get('difficulty', '入门'),
            'category': meta.get('category', '未分类'),
            'description': meta.get('description', ''),
            'exampleInput': meta.get('exampleInput', ''),
            'exampleOutput': meta.get('exampleOutput', ''),
            'tags': meta.get('tags', []),
            'timeLimit': clamp_time_limit(meta.get('timeLimit', 2000)),
        })
    return result


# ============================================================
# 7.5 受限子进程执行
# ============================================================
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
MAX_OUTPUT_BYTES = 1 << 20


class OutputLimitExceeded(Exception):
    pass


def _minimal_env():
    env = {
        'PATH': os.environ.get('PATH', ''),
        'SystemRoot': os.environ.get('SystemRoot', r'C:\Windows'),
        'TEMP': tempfile.gettempdir(),
        'TMP': tempfile.gettempdir(),
        'LANG': 'C.UTF-8',
        'PYTHONIOENCODING': 'utf-8',
    }
    return {k: v for k, v in env.items() if v}


def _kill_tree(pid):
    try:
        if os.name == 'nt':
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=5,
            )
        else:
            # 子进程以 setsid 启动，其 pgid 等于 pid，直接杀整个进程组
            try:
                os.killpg(pid, signal.SIGKILL)
            except Exception:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
    except Exception:
        pass


def _run_limited(cmd, stdin_data, timeout, cwd):
    stdin_path = os.path.join(cwd, '__stdin__.tmp')
    with open(stdin_path, 'wb') as f:
        f.write(stdin_data.encode('utf-8', errors='replace'))

    out_buf = bytearray()
    err_buf = bytearray()
    truncated = threading.Event()

    with open(stdin_path, 'rb') as fin:
        p = subprocess.Popen(
            cmd,
            stdin=fin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=_minimal_env(),
            creationflags=CREATE_NO_WINDOW,
            start_new_session=(os.name != 'nt'),
        )

    def pump(pipe, buf):
        try:
            while True:
                chunk = pipe.read(65536)
                if not chunk:
                    break
                room = MAX_OUTPUT_BYTES - len(buf)
                if room > 0:
                    buf += chunk[:room]
                if len(chunk) > max(room, 0):
                    truncated.set()
                    _kill_tree(p.pid)
                    break
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    t_out = threading.Thread(target=pump, args=(p.stdout, out_buf), daemon=True)
    t_err = threading.Thread(target=pump, args=(p.stderr, err_buf), daemon=True)
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(p.pid)
        try:
            p.wait(timeout=3)
        except Exception:
            pass

    # 即使正常退出，也清理它可能留下的后台子进程
    if not timed_out:
        _kill_tree(p.pid)

    t_out.join(3)
    t_err.join(3)
    try:
        os.remove(stdin_path)
    except OSError:
        pass

    if truncated.is_set():
        raise OutputLimitExceeded()
    if timed_out:
        raise subprocess.TimeoutExpired(cmd, timeout)

    return (
        p.returncode,
        bytes(out_buf).decode('utf-8', errors='replace'),
        bytes(err_buf).decode('utf-8', errors='replace'),
    )


# ============================================================
# 8. 判题核心
# ============================================================
def judge_submission(code, language, problem_dir, time_limit_ms=2000):
    time_limit_ms = clamp_time_limit(time_limit_ms)
    workdir = tempfile.mkdtemp(prefix='woj_judge_')
    try:
        language = (language or '').lower()

        # 先校验测试点，再编译，避免题目没有测试点时白编译一次
        tc_dir = os.path.join(problem_dir, 'testcases')
        if not os.path.isdir(tc_dir):
            return 'System Error', '该题目没有测试点'

        cases = []
        for fname in sorted(os.listdir(tc_dir)):
            if fname.endswith('.in'):
                base = fname[:-3]
                inp = os.path.join(tc_dir, fname)
                out = os.path.join(tc_dir, base + '.out')
                if os.path.isfile(out):
                    cases.append((inp, out))
        if not cases:
            return 'System Error', '该题目没有测试点'

        if language in ('cpp', 'c++'):
            if not GPP_PATH or not os.path.exists(GPP_PATH):
                return 'System Error', '未配置 g++'
            src = os.path.join(workdir, 'main.cpp')
            exe = os.path.join(workdir, 'main.exe' if os.name == 'nt' else 'main')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(code)
            try:
                rc, out, err = _run_limited(
                    [
                        GPP_PATH, src,
                        '-o', exe,
                        '-O2',
                        '-std=c++14',
                        '-DONLINE_JUDGE',
                        '-static-libstdc++',
                        '-static-libgcc',
                    ],
                    '', 20, workdir,
                )
            except OutputLimitExceeded:
                return 'Output Limit Exceeded', '编译输出超过限制'
            except subprocess.TimeoutExpired:
                return 'Compile Error', '编译超时'
            if rc != 0:
                return 'Compile Error', (err or out or '')[:2000]
            run_cmd = [exe]

        elif language in ('python', 'py'):
            if not PYTHON_PATH or not os.path.exists(PYTHON_PATH):
                return 'System Error', '未配置 Python'
            src = os.path.join(workdir, 'main.py')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(code)
            run_cmd = [PYTHON_PATH, '-I', '-S', src]

        else:
            return 'System Error', f'暂不支持的语言: {language}'

        for idx, (inp, outp) in enumerate(cases, 1):
            with open(inp, 'r', encoding='utf-8', errors='replace') as f:
                stdin_data = f.read()
            with open(outp, 'r', encoding='utf-8', errors='replace') as f:
                expected = f.read()

            case_dir = tempfile.mkdtemp(prefix=f'case{idx}_', dir=workdir)
            try:
                try:
                    rc, out, err = _run_limited(
                        run_cmd, stdin_data, time_limit_ms / 1000.0, case_dir,
                    )
                except OutputLimitExceeded:
                    return 'Output Limit Exceeded', f'测试点 {idx} 输出超过 1MB'
                except subprocess.TimeoutExpired:
                    return 'Time Limit Exceeded', f'测试点 {idx} 超时'
            finally:
                shutil.rmtree(case_dir, ignore_errors=True)

            if rc != 0:
                return 'Runtime Error', (
                    f'测试点 {idx} 运行错误（返回码 {rc}）\n'
                    + (err or '')[:500]
                )

            if normalize_text(out) != normalize_text(expected):
                return 'Wrong Answer', f'测试点 {idx} 答案错误'

        return 'Accepted', f'通过 {len(cases)} 个测试点'

    except Exception as e:
        return 'System Error', str(e)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ============================================================
# 9. HTTP 服务器
# ============================================================
class LimitedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, request_handler_class,
                 max_threads=MAX_CONCURRENT_REQUESTS):
        super().__init__(server_address, request_handler_class)
        self._semaphore = threading.BoundedSemaphore(max_threads)

    def process_request(self, request, client_address):
        self._semaphore.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self._semaphore.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._semaphore.release()

    # 判题是长耗时操作：判题期间先让出请求并发槽位，
    # 避免少量判题请求占满线程池、导致其他接口一起卡住。
    def release_request_slot(self):
        try:
            self._semaphore.release()
        except ValueError:
            pass

    def acquire_request_slot(self):
        self._semaphore.acquire()


class Handler(BaseHTTPRequestHandler):

    timeout = REQUEST_TIMEOUT_SECONDS
    _resp_started = False

    def log_message(self, fmt, *args):
        pass

    # -------- Cookie --------
    def _set_cookie_header(self, token, max_age):
        cookie = SimpleCookie()
        cookie[COOKIE_NAME] = token or ''
        morsel = cookie[COOKIE_NAME]
        morsel['path'] = '/'
        morsel['httponly'] = True
        morsel['samesite'] = 'Lax'
        morsel['max-age'] = str(max_age)
        return morsel.OutputString()

    def _read_cookie_token(self):
        raw = self.headers.get('Cookie', '')
        if not raw:
            return None
        try:
            c = SimpleCookie()
            c.load(raw)
            if COOKIE_NAME in c:
                return c[COOKIE_NAME].value
        except Exception:
            pass
        return None

    def _origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        host = self.headers.get('Host', '')
        try:
            parsed = urllib.parse.urlparse(origin)
            return parsed.netloc == host
        except Exception:
            return False

    # -------- 响应 --------
    def _send_json(self, code, obj, set_cookie=None):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self._resp_started = True
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        if set_cookie:
            self.send_header('Set-Cookie', set_cookie)
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, code, msg):
        self._send_json(code, {'error': msg})

    def _safe_500(self):
        """兜底：处理器抛未捕获异常时，尽量回一个 JSON 500（已开始响应则跳过）。"""
        if getattr(self, '_resp_started', False):
            return
        try:
            self._send_error_json(500, '服务器内部错误')
        except Exception:
            pass

    def _serve_static(self, rel_path):
        rel_path = rel_path.replace('\\', '/').lstrip('/')

        if '..' in rel_path.split('/'):
            return self._send_error_json(403, 'Forbidden')

        allowed = (
            rel_path in STATIC_ALLOWED_FILES
            or any(rel_path.startswith(d) for d in STATIC_ALLOWED_DIRS)
        )
        if not allowed:
            return self._send_error_json(404, 'Not Found')

        base = os.path.realpath(ROOT_DIR) + os.sep
        full = os.path.realpath(os.path.join(ROOT_DIR, rel_path))
        if not os.path.normcase(full).startswith(os.path.normcase(base)):
            return self._send_error_json(403, 'Forbidden')
        if not os.path.isfile(full):
            return self._send_error_json(404, 'Not Found')

        ext = os.path.splitext(full)[1].lower()
        mime = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.ico': 'image/x-icon',
        }.get(ext, 'application/octet-stream')
        try:
            with open(full, 'rb') as f:
                data = f.read()
        except Exception as e:
            return self._send_error_json(500, str(e))
        self._resp_started = True
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _current_user(self):
        token = self._read_cookie_token()
        return user_from_token(token)

    # -------- OPTIONS --------
    def do_OPTIONS(self):
        # 仅对同源预检回写 CORS 头，避免把凭据型跨域请求开放给任意站点
        origin = self.headers.get('Origin', '')
        self._resp_started = True
        self.send_response(200)
        if origin and self._origin_ok():
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # -------- GET --------
    def do_GET(self):
        try:
            self._dispatch_get()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self._safe_500()

    def _dispatch_get(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/me':
            return self._handle_me()
        if path == '/problems':
            return self._handle_problems()
        if path == '/submissions':
            return self._handle_submissions()
        if path == '/tags':
            return self._handle_tags()
        if path == '/users':
            return self._handle_users()

        if path in ('/', ''):
            path = '/index.html'
        rel = path.lstrip('/')
        self._serve_static(rel)

    # -------- POST --------
    def do_POST(self):
        try:
            self._dispatch_post()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self._safe_500()

    def _dispatch_post(self):
        if not self._origin_ok():
            return self._send_error_json(403, 'Invalid Origin')

        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return self._send_error_json(400, 'Invalid Content-Length')
        if length < 0 or length > MAX_BODY_BYTES:
            return self._send_error_json(413, '请求体过大')

        try:
            body = self.rfile.read(length).decode('utf-8') if length else ''
        except UnicodeDecodeError:
            return self._send_error_json(400, '请求体必须是 UTF-8')

        try:
            data = json.loads(body) if body else {}
        except Exception:
            return self._send_error_json(400, 'Invalid JSON')
        if not isinstance(data, dict):
            return self._send_error_json(400, 'JSON 必须是对象')

        path = urllib.parse.urlparse(self.path).path

        if path == '/login':
            return self._handle_login(data)
        if path == '/register':
            return self._handle_register(data)
        if path == '/logout':
            return self._handle_logout()
        if path == '/submit':
            return self._handle_submit(data)
        if path == '/create_user':
            return self._handle_create_user(data)
        if path == '/toggle_ban':
            return self._handle_toggle_ban(data)
        if path == '/add_problem':
            return self._handle_add_problem(data)
        if path == '/delete_problem':
            return self._handle_delete_problem(data)
        if path == '/add_tag':
            return self._handle_add_tag(data)
        if path == '/delete_tag':
            return self._handle_delete_tag(data)

        self._send_error_json(404, 'Not Found')

    # =========================================================
    # API 处理器
    # =========================================================

    def _handle_me(self):
        user = self._current_user()
        if not user:
            return self._send_error_json(401, '未登录')
        if user.get('isBanned'):
            return self._send_error_json(403, '账号已被封禁')
        safe = {k: v for k, v in user.items() if k != 'password'}
        self._send_json(200, safe)

    def _handle_problems(self):
        self._send_json(200, scan_problems())

    def _handle_submissions(self):
        user = self._current_user()
        if not user:
            return self._send_error_json(401, '未登录')
        if user.get('isBanned'):
            return self._send_error_json(403, '账号已被封禁')

        subs = load_json(SUBMISSIONS_FILE, [])
        if not isinstance(subs, list):
            subs = []
        mine = [s for s in subs if isinstance(s, dict)
                and s.get('userId') == user['id']]

        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            page = int(qs.get('page', ['1'])[0])
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = int(qs.get('pageSize', [str(SUBMISSIONS_PAGE_SIZE_DEFAULT)])[0])
        except (ValueError, TypeError):
            page_size = SUBMISSIONS_PAGE_SIZE_DEFAULT

        page = max(1, page)
        page_size = max(1, min(page_size, SUBMISSIONS_PAGE_SIZE_MAX))

        total = len(mine)
        end = total - (page - 1) * page_size
        if end <= 0:
            items = []
        else:
            start = max(0, end - page_size)
            items = mine[start:end]

        self._send_json(200, items)

    def _handle_tags(self):
        tags = load_json(TAGS_FILE, [])
        if not isinstance(tags, list):
            tags = []
        self._send_json(200, tags)

    def _handle_users(self):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')
        users = load_json(USERS_FILE, [])
        if not isinstance(users, list):
            users = []
        safe = [{k: v for k, v in u.items() if k != 'password'}
                for u in users if isinstance(u, dict)]
        self._send_json(200, safe)

    def _handle_login(self, data):
        ip = self.client_address[0] if self.client_address else 'unknown'
        if not _rate_limit(f'login-ip:{ip}', 30, 300):
            return self._send_error_json(429, '请求过于频繁，请稍后再试')

        username = _str_field(data, 'username').strip()
        password = _str_field(data, 'password')

        now = datetime.datetime.now()
        if username in LOGIN_FAILS:
            fails, last_time = LOGIN_FAILS[username]
            if fails >= 5 and (now - last_time).total_seconds() < 300:
                return self._send_error_json(403, '密码错误次数过多，请 5 分钟后再试')
            if (now - last_time).total_seconds() >= 300:
                del LOGIN_FAILS[username]

        users = load_json(USERS_FILE, [])
        if not isinstance(users, list):
            users = []
        user = next((u for u in users
                     if isinstance(u, dict) and u.get('username') == username), None)

        stored = user.get('password', '') if user else _get_dummy_hash()
        ok, needs_migrate = verify_password(password, stored)

        if not user or not ok:
            fails = LOGIN_FAILS.get(username, (0, now))[0]
            if len(LOGIN_FAILS) > 10000:
                oldest = min(LOGIN_FAILS, key=lambda k: LOGIN_FAILS[k][1])
                LOGIN_FAILS.pop(oldest, None)
            LOGIN_FAILS[username] = (fails + 1, now)
            return self._send_error_json(401, '用户名或密码错误')

        if user.get('isBanned'):
            return self._send_error_json(403, '账号已被封禁')

        if username in LOGIN_FAILS:
            del LOGIN_FAILS[username]

        if needs_migrate:
            def migrate(users_data):
                for u in users_data:
                    if isinstance(u, dict) and u.get('id') == user.get('id'):
                        u['password'] = hash_password(password)

            update_json(USERS_FILE, [], migrate)

        token = create_token(user['id'])
        safe = {k: v for k, v in user.items() if k != 'password'}
        self._send_json(
            200, safe,
            set_cookie=self._set_cookie_header(token, COOKIE_TTL_SECONDS),
        )

    def _handle_logout(self):
        token = self._read_cookie_token()
        revoke_token(token)
        self._send_json(
            200,
            {'message': '已登出'},
            set_cookie=self._set_cookie_header('', 0),
        )

    def _handle_register(self, data):
        ip = self.client_address[0] if self.client_address else 'unknown'
        if not _rate_limit(f'register:{ip}', 5, 600):
            return self._send_error_json(429, '注册过于频繁，请稍后再试')

        username = _str_field(data, 'username').strip()
        password = _str_field(data, 'password')
        email = _str_field(data, 'email').strip()

        if len(username) < 2 or len(username) > 32:
            return self._send_error_json(400, '用户名长度应为 2-32 个字符')
        if len(password) < 6 or len(password) > 128:
            return self._send_error_json(400, '密码长度应为 6-128 个字符')
        if len(email) > 128 or not _valid_email(email):
            return self._send_error_json(400, '邮箱格式不正确')

        def add_user(users):
            if any(isinstance(u, dict) and u.get('username') == username
                   for u in users):
                raise ValueError('用户名已存在')
            users.append({
                'id': max((u.get('id', 0) for u in users
                           if isinstance(u, dict)), default=0) + 1,
                'username': username,
                'password': hash_password(password),
                'email': email,
                'isAdmin': False,
                'isBanned': False,
                'createdAt': now_iso(),
            })

        try:
            update_json(USERS_FILE, [], add_user)
        except ValueError as e:
            return self._send_error_json(400, str(e))

        self._send_json(200, {'message': '注册成功'})

    def _handle_submit(self, data):
        user = self._current_user()
        if not user:
            return self._send_error_json(401, '未登录')
        if user.get('isBanned'):
            return self._send_error_json(403, '账号已被封禁')

        if not _rate_limit(f'submit:{user["id"]}', 12, 60):
            return self._send_error_json(429, '提交过于频繁，请稍后再试')

        code = _str_field(data, 'code')
        language = _str_field(data, 'language', 'cpp').strip().lower()
        problem_id = data.get('problemId')

        if language not in ('cpp', 'c++', 'python', 'py'):
            return self._send_error_json(400, '不支持的语言')
        if not code.strip():
            return self._send_error_json(400, '代码为空')
        if len(code) > 50000:
            return self._send_error_json(400, '代码过长，请精简后提交（最大 50KB）')

        problem_dir = find_problem_dir(problem_id)
        if not problem_dir:
            return self._send_error_json(404, '题目不存在')

        meta = load_json(os.path.join(problem_dir, 'meta.json'), {})
        if not isinstance(meta, dict):
            meta = {}
        time_limit = clamp_time_limit(meta.get('timeLimit', 2000))

        # 判题限并发；判题期间让出 HTTP 并发槽位，避免拖垮其他接口
        JUDGE_SEMAPHORE.acquire()
        try:
            server = self.server
            release_slot = getattr(server, 'release_request_slot', None)
            acquire_slot = getattr(server, 'acquire_request_slot', None)
            if release_slot:
                release_slot()
            try:
                status, detail = judge_submission(
                    code, language, problem_dir, time_limit
                )
            finally:
                if acquire_slot:
                    acquire_slot()
        finally:
            JUDGE_SEMAPHORE.release()

        log_judge(user['id'], user.get('username', ''), problem_id,
                  language, status, detail)

        try:
            stored_pid = int(problem_id)
        except (TypeError, ValueError):
            stored_pid = problem_id

        def add_sub(subs):
            subs.append({
                'id': max((s.get('id', 0) for s in subs
                           if isinstance(s, dict)), default=0) + 1,
                'userId': user['id'],
                'problemId': stored_pid,
                'problemTitle': meta.get('title', ''),
                'code': code,
                'language': language,
                'status': status,
                'detail': detail,
                'createdAt': now_iso(),
            })

        update_json(SUBMISSIONS_FILE, [], add_sub)
        self._send_json(200, {'status': status, 'detail': detail})

    def _handle_create_user(self, data):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')

        username = _str_field(data, 'username').strip()
        password = _str_field(data, 'password')
        email = _str_field(data, 'email').strip()

        if not username or not password:
            return self._send_error_json(400, '用户名和密码不能为空')
        if len(username) < 2 or len(username) > 32:
            return self._send_error_json(400, '用户名长度应为 2-32 个字符')
        if len(password) < 6 or len(password) > 128:
            return self._send_error_json(400, '密码长度应为 6-128 个字符')
        if len(email) > 128 or not _valid_email(email):
            return self._send_error_json(400, '邮箱格式不正确')

        new_holder = {}

        def add_user(users):
            if any(isinstance(u, dict) and u.get('username') == username
                   for u in users):
                raise ValueError('用户名已存在')
            new_user = {
                'id': max((u.get('id', 0) for u in users
                           if isinstance(u, dict)), default=0) + 1,
                'username': username,
                'password': hash_password(password),
                'email': email,
                'isAdmin': False,
                'isBanned': False,
                'createdAt': now_iso(),
            }
            users.append(new_user)
            new_holder.update(new_user)

        try:
            update_json(USERS_FILE, [], add_user)
        except ValueError as e:
            return self._send_error_json(400, str(e))

        safe = {k: v for k, v in new_holder.items() if k != 'password'}
        self._send_json(200, safe)

    def _handle_toggle_ban(self, data):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')

        target_id = data.get('userId')
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            pass
        result = {}

        def toggle(users):
            target = next((u for u in users
                           if isinstance(u, dict) and u.get('id') == target_id), None)
            if not target:
                raise LookupError('用户不存在')
            if target.get('isAdmin'):
                raise PermissionError('不能操作管理员')
            target['isBanned'] = not target.get('isBanned', False)
            result['isBanned'] = target['isBanned']

        try:
            update_json(USERS_FILE, [], toggle)
        except LookupError as e:
            return self._send_error_json(404, str(e))
        except PermissionError as e:
            return self._send_error_json(403, str(e))

        self._send_json(200, {'message': '操作成功', 'isBanned': result['isBanned']})

    def _handle_add_problem(self, data):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')

        title = _str_field(data, 'title').strip()
        if not title:
            return self._send_error_json(400, '题目标题不能为空')

        tags = data.get('tags') or []
        if not isinstance(tags, list):
            tags = []
        tags = [t.strip() for t in tags if isinstance(t, str) and t.strip()][:100]

        testcases = data.get('testCases') or []
        if not isinstance(testcases, list):
            testcases = []

        if not testcases:
            ex_in = _str_field(data, 'exampleInput')
            ex_out = _str_field(data, 'exampleOutput')
            if ex_in or ex_out:
                testcases = [{'input': ex_in, 'output': ex_out}]

        if not testcases:
            return self._send_error_json(400, '至少需要一个测试点')

        with DATA_LOCK:
            existing = set()
            if os.path.isdir(PROBLEMS_DIR):
                for name in os.listdir(PROBLEMS_DIR):
                    num = parse_problem_dir_name(name)
                    if num is not None:
                        existing.add(num)
            new_id = max(existing, default=0) + 1
            dir_name = f"Q{new_id:04d}"
            pdir = os.path.join(PROBLEMS_DIR, dir_name)

            try:
                os.makedirs(os.path.join(pdir, 'testcases'), exist_ok=True)

                meta = {
                    'title': title,
                    'difficulty': _str_field(data, 'difficulty', '入门').strip() or '入门',
                    'category': _str_field(data, 'category', '未分类').strip() or '未分类',
                    'description': _str_field(data, 'description'),
                    'exampleInput': _str_field(data, 'exampleInput'),
                    'exampleOutput': _str_field(data, 'exampleOutput'),
                    'tags': tags,
                    'timeLimit': clamp_time_limit(data.get('timeLimit', 2000)),
                }
                save_json(os.path.join(pdir, 'meta.json'), meta)

                for i, tc in enumerate(testcases, 1):
                    if not isinstance(tc, dict):
                        continue
                    with open(os.path.join(pdir, 'testcases', f'{i}.in'), 'w',
                              encoding='utf-8') as f:
                        f.write(_str_field(tc, 'input'))
                    with open(os.path.join(pdir, 'testcases', f'{i}.out'), 'w',
                              encoding='utf-8') as f:
                        f.write(_str_field(tc, 'output'))
            except Exception as e:
                shutil.rmtree(pdir, ignore_errors=True)
                return self._send_error_json(500, f'创建失败: {e}')

        self._send_json(200, {'id': new_id, 'message': '题目创建成功'})

    def _handle_delete_problem(self, data):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')

        problem_id = data.get('problemId')
        pdir = find_problem_dir(problem_id)
        if not pdir:
            return self._send_error_json(404, '题目不存在')

        try:
            pid_num = int(problem_id)
        except (TypeError, ValueError):
            pid_num = problem_id

        trash = pdir + '.deleting-' + secrets.token_hex(4)
        try:
            os.replace(pdir, trash)
        except OSError as e:
            return self._send_error_json(500, f'删除失败: {e}')

        try:
            def remove_subs(subs):
                subs[:] = [
                    s for s in subs
                    if not isinstance(s, dict)
                    or str(s.get('problemId')) != str(pid_num)
                ]

            update_json(SUBMISSIONS_FILE, [], remove_subs)
        except Exception as e:
            try:
                os.replace(trash, pdir)
            except OSError:
                pass
            return self._send_error_json(500, f'删除失败: {e}')

        try:
            shutil.rmtree(trash)
        except OSError as e:
            return self._send_error_json(500, f'题目已移除，但临时目录清理失败: {e}')

        self._send_json(200, {'message': '删除成功'})

    def _handle_add_tag(self, data):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')

        tag = _str_field(data, 'tag').strip()
        if not tag:
            return self._send_error_json(400, '标签名不能为空')
        if len(tag) > 32:
            return self._send_error_json(400, '标签名过长')

        def add(tags):
            if tag in tags:
                raise ValueError('标签已存在')
            tags.append(tag)

        try:
            update_json(TAGS_FILE, [], add)
        except ValueError as e:
            return self._send_error_json(400, str(e))

        self._send_json(200, {'message': '添加成功'})

    def _handle_delete_tag(self, data):
        user = self._current_user()
        if not user or not user.get('isAdmin') or user.get('isBanned'):
            return self._send_error_json(403, '权限不足')

        tag = _str_field(data, 'tag').strip()
        if not tag:
            return self._send_error_json(400, '标签名不能为空')

        def remove(tags):
            if tag not in tags:
                raise ValueError('标签不存在')
            tags.remove(tag)

        try:
            update_json(TAGS_FILE, [], remove)
        except ValueError as e:
            return self._send_error_json(400, str(e))

        changed = {}
        original = {}
        try:
            if os.path.isdir(PROBLEMS_DIR):
                for name in os.listdir(PROBLEMS_DIR):
                    pdir = os.path.join(PROBLEMS_DIR, name)
                    if not os.path.isdir(pdir):
                        continue
                    meta_path = os.path.join(pdir, 'meta.json')
                    if not os.path.isfile(meta_path):
                        continue
                    meta = load_json(meta_path, {})
                    if not isinstance(meta, dict):
                        continue
                    tags = meta.get('tags') or []
                    if isinstance(tags, list) and tag in tags:
                        original[meta_path] = copy.deepcopy(meta)
                        meta['tags'] = [t for t in tags if t != tag]
                        changed[meta_path] = meta

            for path, meta in changed.items():
                save_json(path, meta)
        except Exception as e:
            for path, meta in original.items():
                try:
                    save_json(path, meta)
                except Exception:
                    pass
            # 题目回滚之后再把标签补回，避免 tags.json 与题目引用不一致
            try:
                def restore(tags):
                    if tag not in tags:
                        tags.append(tag)
                update_json(TAGS_FILE, [], restore)
            except Exception:
                pass
            return self._send_error_json(500, f'标签清理失败: {e}')

        self._send_json(200, {
            'message': '删除成功',
            'affectedProblems': len(changed),
        })


# ============================================================
# 10. 入口
# ============================================================
def main():
    global config, GPP_PATH, PYTHON_PATH

    config = load_config()
    GPP_PATH = config.get('gpp')
    PYTHON_PATH = config.get('python')

    if GPP_PATH and not os.path.exists(GPP_PATH):
        GPP_PATH = None
    if PYTHON_PATH and not os.path.exists(PYTHON_PATH):
        PYTHON_PATH = None

    if not GPP_PATH and not PYTHON_PATH:
        print()
        print("[错误] 未找到可用的 g++ 或 Python。")
        print("       请删除 config.json 后重新运行本脚本，按向导重新配置。")
        input("按回车退出...")
        sys.exit(1)

    print()
    print("=" * 52)
    print("  WeCode Online Judge")
    print("=" * 52)
    print(f"  g++    : {GPP_PATH or '（未配置，C++ 判题不可用）'}")
    print(f"  Python : {PYTHON_PATH or '（未配置，Python 判题不可用）'}")
    print(f"  Data   : {DATA_DIR}")
    print(f"  Problems: {PROBLEMS_DIR}")
    print()

    if os.path.exists(USERS_FILE):
        users = load_json(USERS_FILE, [])
        if not isinstance(users, list):
            users = []
        need_save = False
        for u in users:
            if not isinstance(u, dict):
                continue
            pwd = u.get('password')
            if pwd and not pwd.startswith('pbkdf2_sha256$'):
                u['password'] = hash_password(pwd)
                need_save = True
        if need_save:
            save_json(USERS_FILE, users)
            print("[init] 已自动将明文密码升级为 PBKDF2 哈希存储")

    init_data()

    port = config.get('port', 8000)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 8000
    if not (1 <= port <= 65535):
        port = 8000

    host = '0.0.0.0'

    server = LimitedThreadingHTTPServer((host, port), Handler)
    print(f"  服务已启动: http://127.0.0.1:{port}")
    print(f"  局域网访问: http://{_lan_ip()}:{port}")
    print()
    print("  按 Ctrl+C 停止服务")
    print("=" * 52)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        server.shutdown()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()