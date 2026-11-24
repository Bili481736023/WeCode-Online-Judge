# WeCode Online Judge

一款为**局域网**设计的**轻量**在线评判机，适用于**学校计算机实验室**、**社团**和**小型团队**：

- 后端是**单个 Python 脚本**（`judge_server.py`），只用标准库，无需 pip install
- 前端是**纯原生 HTML / CSS / JavaScript**，无框架、无构建、无 CDN
- 题库就是一个个文件夹，`meta.json` + `testcases/`，用记事本就能建题
- 适合班级作业、社团练习、个人刷题等局域网 / 单机场景

> ⚠️ 本项目面向**可信小环境**（如校内局域网）设计，未做沙箱隔离——
> 提交的代码会**以服务器本机权限直接运行**，请勿在公网或不可信环境开放使用。

---

## 目录

1. [功能一览](#1-功能一览)
2. [技术栈](#2-技术栈)
3. [快速开始](#3-快速开始)
4. [配置向导详解](#4-配置向导详解)
5. [目录结构](#5-目录结构)
6. [题目格式](#6-题目格式)
7. [数据文件](#7-数据文件)
8. [前端架构](#8-前端架构)
9. [API 一览](#9-api-一览)
10. [判题流程](#10-判题流程)
11. [安全设计](#11-安全设计)
12. [阈值与限制速查](#12-阈值与限制速查)
13. [常见问题](#13-常见问题)
14. [已知的不一致与改进方向](#14-已知的不一致与改进方向)
15. [免责声明](#15-免责声明)
16. [许可证](#16-许可证)

---

## 1. 功能一览

**前台（学生端，`index.html`）**

- 登录 / 注册 / 自动会话恢复
- 题目列表：按分类、难度、标签筛选，关键词搜索
- 题目详情：题面、样例、在线编辑器（C++ / Python）、直接提交并实时看结果
- 提交记录：分页查看历史提交与判题详情，可一键恢复上次代码
- 个人中心：查看 / 修改个人信息

**后台（管理端，`back_platform.html`）**

- 用户管理：查看用户列表、创建账号、封禁 / 解封
- 题目管理：在线建题（题面 + 测试点）、删除题目
- 标签管理：添加 / 删除标签，删除时自动清理题目引用

**判题（后端内置）**

- 支持 C++（g++，`-std=c++14 -O2`）与 Python（`python -I -S`）
- 逐测试点评测：答案比对忽略行尾空白与末尾空行
- 时间限制、输出限制（1MB）、进程树清理全部内置

---

## 2. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.10+ 标准库 | `http.server.ThreadingHTTPServer` + 自写路由，零第三方依赖 |
| 前端 | 原生 HTML / CSS / JS | ES Modules，Hash 路由，无框架无构建 |
| 存储 | JSON 文件 | `data/*.json` + `problems/*/meta.json`，原子写入（tmp + os.replace） |
| 编译器 | g++ | 自动探测 PATH、Dev-C++ 目录与注册表 |
| 解释器 | Python | 自动探测 PATH 与常见安装位置 |
| 认证 | PBKDF2-SHA256 + Cookie | 200,000 轮加盐哈希；HttpOnly + SameSite=Lax 会话令牌 |

---

## 3. 快速开始

### 环境要求

| 组件 | 要求 |
|---|---|
| Python | 3.10 及以上（仅标准库） |
| g++ | 可选——不配置则 C++ 判题不可用 |
| 操作系统 | Windows / Linux / macOS 均可（判题子进程管理两端都做了适配） |

### 启动

```bash
cd WeCode_Online_Judge
python judge_server.py
```

首次运行会进入**配置向导**（见下一节），完成后：

- 服务地址：<http://127.0.0.1:8000>（端口以向导为准）
- 局域网地址：启动时打印真实本机 IP，如 `http://192.168.1.10:8000`
- 学生端：<http://…/index.html>，管理后台：<http://…/back_platform.html>

> 监听地址固定为 `0.0.0.0`，同一局域网内的设备可直接访问。
> 停止服务：`Ctrl + C`。

---

## 4. 配置向导详解

首次启动（或 `config.json` 缺失 / 不完整时）会依次询问 5 项，全部可直接回车用默认值：

| 步骤 | 项 | 默认值 | 说明 |
|---|---|---|---|
| 1/5 | 服务端口 | `8000` | 1–65535，非法输入回落 8000 |
| 2/5 | g++ 路径 | 自动探测 | 探测顺序：PATH → Dev-C++ 常见安装目录 → 注册表 |
| 3/5 | Python 路径 | 自动探测 | 探测顺序：PATH → 常见安装目录 |
| 4/5 | 管理员用户名 | `admin` | |
| 5/5 | 管理员密码 | `admin123` | ⚠️ 建议务必改成强密码 |

配置写入 `config.json`。管理员密码在首次初始化时会哈希入库，随后**从 config.json 中清除明文**。g++ 与 Python 至少要配置一个，否则启动报错退出。

想重跑向导：删除 `config.json` 再启动即可。

---

## 5. 目录结构

```
WeCode_Online_Judge/
├── judge_server.py        # 后端全部：HTTP 服务 + 判题核心（单文件）
├── index.html             # 学生端入口（单页，Hash 路由）
├── back_platform.html     # 管理后台入口
├── run.bat                # (可选) Windows 一键启动
│
├── css/
│   ├── main.css           # 入口：@import 其余分层样式
│   ├── base.css           # 变量、Reset、字体
│   ├── layout.css         # 导航栏、页面容器布局
│   ├── components.css     # 按钮、表单、卡片等通用组件
│   ├── pages.css          # 各业务页面样式
│   └── admin.css          # 管理后台专用（侧边栏、面板）
│
├── js/
│   ├── main.js            # 学生端启动：恢复会话 → 渲染导航 → 初始化路由
│   ├── admin-main.js      # 管理端启动
│   ├── config.js          # 前端常量（API_BASE、默认代码模板）
│   ├── api.js             # fetch 封装：统一 JSON / 错误 / Cookie
│   ├── store.js           # 极简全局状态（当前用户）
│   ├── router.js          # Hash 路由 + 登录守卫
│   ├── ui.js              # 导航栏渲染
│   ├── utils.js           # escapeHtml 等工具
│   └── pages/
│       ├── auth.js        # 登录 / 注册
│       ├── problems.js    # 题目列表
│       ├── detail.js      # 题目详情 + 代码编辑器 + 提交
│       ├── submissions.js # 提交记录
│       ├── profile.js     # 个人中心
│       └── admin.js       # 后台三个面板（用户/题目/标签）
│
├── assets/icons/          # 内置 SVG 图标（自绘，无外部字体/图标库）
│
├── problems/              # 题库（首次启动自动创建）
│   └── Q0001/
│       ├── meta.json      # 题面元数据
│       └── testcases/     # 测试点：1.in / 1.out、2.in / 2.out …
│
├── data/                  # 运行数据（自动创建）
│   ├── users.json         # 用户（密码为 PBKDF2 哈希）
│   ├── submissions.json   # 提交记录
│   ├── tags.json          # 标签池
│   └── tokens.json        # 会话令牌
│
├── logs/
│   └── judge.log          # 判题日志（5MB 自动轮转）
│
└── config.json            # 服务配置（向导生成；含管理员明文密码时会被自动清除）
```

---

## 6. 题目格式

每道题是 `problems/` 下一个目录，目录名形如 `Q0001`（也兼容 `1`、`q1` 等写法，编号即题目 ID）。目录里必须有 `meta.json`，测试点放在 `testcases/` 子目录。

### meta.json 字段

```json
{
  "title": "A+B Problem",
  "difficulty": "入门",
  "category": "顺序结构",
  "description": "输入两个整数，输出它们的和。",
  "exampleInput": "1 2",
  "exampleOutput": "3",
  "tags": ["模拟", "入门"],
  "timeLimit": 2000
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 建议 | 题目标题，缺省显示「未命名题目」 |
| `difficulty` | 否 | 难度文本，默认 `入门` |
| `category` | 否 | 分类文本，默认 `未分类` |
| `description` | 否 | 题面（纯文本，前端做 HTML 转义渲染） |
| `exampleInput` / `exampleOutput` | 否 | 样例；仅作展示，**不参与判题** |
| `tags` | 否 | 标签数组，建议从标签池中选 |
| `timeLimit` | 否 | 单测试点时限（毫秒），自动夹取到 100–10000，默认 `2000` |

### testcases/

- 命名规则：`N.in` 配对 `N.out`（N 从 1 开始，按文件名排序依次评测）
- 只有成对存在的 `.in/.out` 才会被评测；一题**至少要有一个测试点**，否则提交一律返回 System Error
- 想多组数据？加 `2.in`/`2.out`、`3.in`/`3.out` 即可

也可以不手动建文件，直接在管理后台「题目管理」里填表单创建（含逐个添加测试点）。

---

## 7. 数据文件

全部位于 `data/`，均为 UTF-8 JSON，写入采用「临时文件 + 原子替换」，并由全局锁保护，多线程并发安全。

| 文件 | 结构 | 说明 |
|---|---|---|
| `users.json` | 用户对象数组 | `id / username / password(哈希) / email / isAdmin / isBanned / createdAt` |
| `submissions.json` | 提交对象数组 | `id / userId / problemId / problemTitle / code / language / status / detail / createdAt` |
| `tags.json` | 字符串数组 | 标签池，首次初始化内置洛谷风格标签（模拟、DP、图论、数据结构…） |
| `tokens.json` | 令牌 → `{userId, createdAt}` | 会话令牌，7 天过期自动清理 |

容错：任一 JSON 解析失败时，会先把损坏文件备份为 `xxx.corrupt-时间戳` 再返回默认值，避免损坏文件被静默覆盖。

---

## 8. 前端架构

两个独立入口，共享同一套模块：

- **学生端**：`index.html` + `js/main.js` —— 路由页面为登录、注册、题目列表、题目详情、提交记录、个人中心
- **管理端**：`back_platform.html` + `js/admin-main.js` —— 侧边栏切换用户 / 题目 / 标签三个面板，进入前校验管理员身份

关键设计：

- **Hash 路由**（`#/problems`、`#/problem/1`…）：`router.js` 统一分发，未登录访问受限页自动跳登录页
- **ES Modules**：`<script type="module">`，浏览器原生加载，无需打包
- **会话恢复**：`main.js` 启动时先请求 `/me`，Cookie 有效则直接进入已登录状态
- **XSS 防护**：所有用户可控内容（用户名、题面、标签等）均经 `utils.js` 的 `escapeHtml` 转义后渲染
- **零外部依赖**：无 CDN、无字体库、无图标库，全部资源本地自含，内网断网也能跑

样式分层：`main.css` 作为入口按 `base → layout → components → pages` 顺序引入（管理端额外加 `admin.css`）。

---

## 9. API 一览

所有接口同源访问（前端与后端部署在一起），请求体均为 JSON；除登录 / 注册外都需要有效的会话 Cookie（`woj_token`）。

### 认证相关

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/login` | 公开 | 登录，成功后种下 HttpOnly Cookie；IP 限流 30 次/5 分钟，同名连续错 5 次锁 5 分钟 |
| POST | `/register` | 公开 | 注册；用户名 2–32 字符，密码 6–128 字符，邮箱可选；IP 限流 5 次/10 分钟 |
| POST | `/logout` | 登录 | 注销（吊销令牌 + 清 Cookie） |
| GET | `/me` | 登录 | 当前用户信息（不含密码字段） |

### 业务相关

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/problems` | 公开 | 全部题目列表（实时扫描题库目录） |
| GET | `/submissions?page=1&pageSize=100` | 登录 | 当前用户的提交记录，分页返回（默认 100 条/页，最大 200） |
| GET | `/tags` | 公开 | 标签池 |
| POST | `/submit` | 登录 | 提交代码并**同步返回判题结果**；用户限流 12 次/60 秒；代码 ≤ 50KB |
| GET | `/users` | 管理员 | 用户列表（不含密码字段） |

### 管理相关（均需管理员）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/create_user` | 创建用户（校验规则与注册一致） |
| POST | `/toggle_ban` | 封禁 / 解封用户（不能操作管理员） |
| POST | `/add_problem` | 创建题目（含测试点；题号自动分配为最大编号 + 1） |
| POST | `/delete_problem` | 删除题目（先移入临时目录再清理，关联提交一并删除，失败可回滚） |
| POST | `/add_tag` / `/delete_tag` | 标签增删（删除时自动清理所有题目的引用） |

### 错误响应

统一为 `{"error": "中文错误信息"}`，状态码含：`400 参数错误`、`401 未登录`、`403 权限不足/被封禁`、`404 不存在`、`413 请求体过大`、`429 触发限流`、`500 服务器内部错误`。

---

## 10. 判题流程

```
POST /submit
  ├─ 鉴权（登录 + 未封禁）+ 用户级限流（12 次/分钟）
  ├─ 参数校验（语言 / 代码非空 / ≤50KB / 题目存在）
  ├─ 获取判题信号量（全局最多同时 2 个判题）
  │    └─ 判题期间主动让出 HTTP 并发槽位，避免拖垮其他接口
  ├─ judge_submission()
  │    ├─ 检查 testcases/（无测试点直接 System Error，不浪费编译）
  │    ├─ C++：g++ -O2 -std=c++14 -DONLINE_JUDGE 编译（限时 20s）
  │    │       Python：python -I -S main.py
  │    └─ 逐测试点运行：
  │          超时        → Time Limit Exceeded
  │          输出 > 1MB  → Output Limit Exceeded
  │          返回码 ≠ 0  → Runtime Error（附 stderr 前 500 字符）
  │          文本比对不符 → Wrong Answer（忽略行尾空白与末尾空行）
  │          全部通过     → Accepted
  ├─ 写入判题日志 logs/judge.log
  ├─ 追加提交记录到 data/submissions.json
  └─ 同步返回 {"status": "...", "detail": "..."}
```

**受限子进程**：判题运行的代码工作目录为一次性临时目录，环境变量裁剪到最小集，超时 / 超输出时杀掉整个进程树（Windows `taskkill /T`；POSIX `setsid` + `killpg`），正常退出后也会兜底清理残留子进程。

**状态值一览**：`Accepted` / `Wrong Answer` / `Compile Error` / `Runtime Error` / `Time Limit Exceeded` / `Output Limit Exceeded` / `System Error`。

---

## 11. 安全设计

| 机制 | 实现 |
|---|---|
| 密码存储 | PBKDF2-SHA256，200,000 轮，每用户独立盐；旧明文密码在登录或启动时自动迁移 |
| 会话 | 32 字节随机令牌，HttpOnly + SameSite=Lax + Path=/，7 天过期；登出即吊销 |
| CSRF | 所有 POST 校验 `Origin` 与 `Host` 一致；CORS 预检仅对同源回写凭据头 |
| 登录爆破 | 同用户名连错 5 次锁定 5 分钟；IP 级滑动窗口限流 |
| 请求体 | 上限 512KB，非 UTF-8 / 非 JSON 对象直接拒绝 |
| 路径穿越 | 静态服务白名单（仅 `index.html`、`back_platform.html`、`css/js/assets/`），拒绝 `..`，并做 realpath 归一化二次校验 |
| 数据安全 | 全局锁 + 原子写；损坏 JSON 自动备份后重置 |
| 异常兜底 | 处理器未捕获异常统一回 JSON 500，不中断连接 |
| 判题隔离 | ⚠️ **无沙箱**——见文首免责声明；已做：最小环境变量、输出限制、进程树清理 |

---

## 12. 阈值与限制速查

| 项 | 值 | 位置（judge_server.py 常量） |
|---|---|---|
| HTTP 并发请求数 | 32 | `MAX_CONCURRENT_REQUESTS` |
| 同时判题数 | 2 | `JUDGE_SEMAPHORE` |
| 单请求超时 | 30s | `REQUEST_TIMEOUT_SECONDS` |
| 请求体上限 | 512KB | `MAX_BODY_BYTES` |
| 提交代码上限 | 50KB | `/submit` 内联校验 |
| 提交限流 | 12 次 / 60s / 用户 | `/submit` |
| 注册限流 | 5 次 / 600s / IP | `/register` |
| 登录限流 | 30 次 / 300s / IP | `/login` |
| 登录失败锁定 | 错 5 次锁 300s / 用户名 | `LOGIN_FAILS` |
| 单测试点时限 | 100–10000ms，默认 2000 | `clamp_time_limit` |
| 编译超时 | 20s | 判题核心内联 |
| 程序输出上限 | 1MB | `MAX_OUTPUT_BYTES` |
| 会话有效期 | 7 天 | `TOKEN_TTL_DAYS` |
| 判题日志轮转 | 5MB | `JUDGE_LOG_MAX_BYTES` |
| 提交记录分页 | 默认 100，最大 200 | `SUBMISSIONS_PAGE_SIZE_*` |
| 题目标签数 | ≤ 100 个/题 | `/add_problem` |
| 标签长度 | ≤ 32 字符 | `/add_tag` |

---

## 13. 常见问题

**Q：启动后 C++ 提交全部 System Error「未配置 g++」？**
A：向导时没检测到 g++。安装 MinGW / Dev-C++ 后，删除 `config.json` 重跑向导，或手动把 g++ 完整路径填进 `config.json` 的 `gpp` 字段。

**Q：想改端口 / 换编译器？**
A：直接改 `config.json`（`port`、`gpp`、`python`），重启生效。

**Q：管理员密码忘了？**
A：删除 `data/users.json` 会重建初始管理员（需要 `config.json` 里还有明文密码，或重跑向导）。更稳妥的方式是直接编辑 `users.json`：把对应管理员的 `password` 字段替换为新的明文密码，重启后系统会自动把它哈希化。

**Q：题目改了 meta 但页面没变化？**
A：`/problems` 每次请求都实时扫描题库，刷新页面即可；浏览器侧若有缓存请强刷（Ctrl+F5）。

**Q：判题很慢 / 卡住别的页面？**
A：判题全局最多 2 个并发且会让出 HTTP 槽位，正常不会互相拖垮。若仍慢，检查题目 `timeLimit` 是否被设得过大（上限 10s）。

**Q：怎么备份？**
A：拷贝 `problems/`、`data/`、`config.json` 三个位置即可完整还原。

---

## 14. 已知的不一致与改进方向

如实记录当前版本的已知问题（有意保留、待后续决策）：

1. **判题为同步模型**：`/submit` 会阻塞到判题结束才返回（已通过限并发 + 让出 HTTP 槽位缓解）。彻底解耦需改为「入队 + 前端轮询」。
2. **`submissions.json` 单文件存储**：每次提交全量读写整个文件，数据量大后会变慢；前端依赖返回的 `code` 做「恢复上次代码」，故暂未裁剪字段。
3. **无沙箱**：判题代码以服务本机权限运行，见免责声明。
4. **可选项未做**：HTTP/1.1 keep-alive、题目元数据内存缓存、`-std=c++17` 等，按需再加。

---

## 15. 免责声明

- 本软件按「现状」提供，不附带任何明示或暗示的担保。作者不对因使用本软件而产生的任何损失承担责任。
- **判题不隔离**：提交的代码将以服务器进程的权限在宿主机上直接运行。请仅在与使用者互相可信的环境中部署（如教学内网），并自行承担由此带来的风险。
- 请勿将本系统部署于公网或允许不可信第三方提交代码的环境。

---

## 16. 许可证

本项目采用**按内容类型划分的双重许可**：

### 源代码 —— MPL-2.0

所有源代码文件（`.py`、`.js`、`.css`、`.html`）以
**Mozilla Public License 2.0（MPL-2.0）** 发布。

- SPDX 标识：`MPL-2.0`
- 全文：<https://www.mozilla.org/MPL/2.0/>
- 要点：以**文件为单位**的 copyleft——你可以自由使用、修改、商用、再分发本项目代码；但**修改过的 MPL 文件本身**必须继续以 MPL-2.0 开源，新增的独立文件可以自选协议。
- 建议在修改过的源文件头部保留以下声明（MPL-2.0 Exhibit A 模板）：

  ```
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
  ```

### 文档与非代码素材 —— CC BY-NC-ND 4.0

README 及其他文档、`assets/` 下的 SVG 图标、示例题目文本等非代码素材，以
**知识共享 署名-非商业性使用-禁止演绎 4.0 国际（CC BY-NC-ND 4.0）** 发布。

- SPDX 标识：`CC-BY-NC-ND-4.0`
- 全文：<https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.zh>
- 要点：
  - **BY（署名）**：转载须注明出处与作者；
  - **NC（非商业）**：不得用于商业目的；
  - **ND（禁止演绎）**：可原样转载，但**不得修改后再分发**。

> ⚠️ 注意二者的边界：MPL-2.0 允许修改和商用代码，而 CC BY-NC-ND 对文档/素材不允许改作与商用。若需要修改文档或用于商业场景，须另行获得授权。
> 源代码注释与文档冲突时，以本节为准。

### 不属于授权范围的内容

以下内容**不在上述许可授予范围内**，随仓库分发仅为运行示例 / 运行产物：

- `data/` , `logs/` 与`problems`下的运行数据（含用户个人信息、提交代码及题目信息）；
- `config.json`（本地部署配置）；
- 用户自己创建的题目内容与用户提交的代码，权利归其作者；
- 系统中的 Python、g++ 等第三方工具链，各自遵循其自身许可证。

「WeCode Online Judge」「WeCode OJ」名称及标识未作商标授权，未经许可不得用于暗示背书的场景。

Copyright (c) 2026-2032 爱玩机的学生 All rights reserved.
