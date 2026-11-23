# WeCode Online Judge (WOJ)

一个面向**局域网**的轻量级 Online Judge，单文件 Python 实现，尽量不引入额外运行环境，适合学校机房、社团、小团队内部使用。

> 重要：本项目\*\*没有真正的代码沙箱\*\*，只适合\*\*可信局域网\*\*。不要直接暴露到公网。

\---

## 功能

* 用户注册 / 登录 / 登出（Cookie + Token）
* 密码使用 PBKDF2-SHA256 哈希存储
* 题目列表、题目详情、标签分类
* 提交代码并判题
* 支持语言：

  * C++（g++，C++14，`-O2`）
  * Python（可选，配置 Python 解释器后可用）
* 管理员功能：

  * 创建用户
  * 封禁 / 解封用户
  * 创建 / 删除题目
  * 添加 / 删除标签
* 提交记录查询（支持分页参数）
* 判题日志 `logs/judge.log`，超过 5MB 自动轮转
* 首次启动配置向导
* 数据文件损坏自动备份 `.corrupt-\*`，避免被静默覆盖

\---

## 环境要求

* Windows 10 20H2 及以上（64 位）
* Python 3.10+（测试过 3.10 / 3.11 / 3.12）
* C++ 判题需要 g++（MinGW / Dev-Cpp 均可）
* Python 判题需要额外配置一个 Python 解释器
* 工作目录必须放在 **NTFS 磁盘**上，不要放在 FAT32/exFAT 的 U 盘或只读目录

\---

## 快速开始

### 1\. 安装运行环境

安装 Python 3.10+，并确保命令行可用：

```powershell
python --version
```

安装 MinGW / Dev-Cpp，并确保 `g++.exe` 在 `PATH` 中，或首次启动时手动填写完整路径：

```powershell
g++ --version
```

### 2\. 启动

```powershell
python judge\_server.py
```

首次启动会进入配置向导，依次填写：

1. 服务端口（默认 8000）
2. g++ 路径
3. Python 路径（可留空）
4. 管理员用户名（默认 admin）
5. 管理员密码（默认 admin123，建议修改）

配置会写入 `config.json`。第一次启动后，`config.json` 中的明文管理员密码会被清除。

### 3\. 访问

浏览器打开：

```text
http://127.0.0.1:8000
```

局域网其他机器访问：

```text
http://<服务器局域网IP>:8000
```

\---

## 目录结构

```text
.
├── judge\_server.py          # 主程序
├── config.json              # 首次启动生成
├── data/
│   ├── users.json           # 用户数据
│   ├── submissions.json     # 提交记录
│   ├── tags.json            # 标签
│   └── tokens.json          # 登录 Token
├── problems/
│   └── Q0001/
│       ├── meta.json
│       └── testcases/
│           ├── 1.in
│           ├── 1.out
│           ├── 2.in
│           └── 2.out
├── logs/
│   └── judge.log            # 判题日志，超过 5MB 轮转为 judge.log.1
├── index.html
├── back\_platform.html
├── css/
├── js/
└── assets/
```

\---

## 题目格式

题目目录名建议使用 `Q0001`、`Q0002` 这种格式，也兼容 `1`、`Q1`，但同时存在多个同 ID 目录时只会确定性命中一个。

`meta.json` 示例：

```json
{
  "title": "A+B Problem",
  "difficulty": "入门",
  "category": "基础",
  "description": "输入两个整数，输出它们的和。",
  "exampleInput": "1 2",
  "exampleOutput": "3",
  "tags": \["模拟", "数学"],
  "timeLimit": 2000
}
```

测试点：

```text
problems/Q0001/testcases/1.in
problems/Q0001/testcases/1.out
```

* `.in` 与 `.out` 必须同名配对
* `timeLimit` 单位是毫秒，会被限制在 100 \~ 10000 之间
* 代码长度上限 50KB
* 单个测试点输出上限 1MB，超过会判 `Output Limit Exceeded`

\---

## 配置文件

`config.json` 示例：

```json
{
  "port": 8000,
  "gpp": "C:\\\\MinGW\\\\bin\\\\g++.exe",
  "python": "C:\\\\Python312\\\\python.exe",
  "admin": {
    "username": "admin",
    "password": ""
  }
}
```

* `gpp` 和 `python` 至少配置一个，否则程序拒绝启动
* `python` 可以为空，此时 Python 判题不可用
* 初始化完成后 `admin.password` 会被清空

\---

## API 简表

### GET

|路径|说明|
|-|-|
|`/me`|当前登录用户|
|`/problems`|题目列表|
|`/submissions?page=1\&pageSize=100`|当前用户提交记录|
|`/tags`|标签列表|
|`/users`|用户列表（仅管理员）|

`/submissions` 默认每页 100 条，最大 200 条，返回的是当前用户该页数据。

### POST

所有 POST 请求体为 JSON。

|路径|说明|
|-|-|
|`/login`|登录|
|`/register`|注册|
|`/logout`|登出|
|`/submit`|提交代码|
|`/create\_user`|创建用户（管理员）|
|`/toggle\_ban`|封禁/解封（管理员）|
|`/add\_problem`|创建题目（管理员）|
|`/delete\_problem`|删除题目（管理员）|
|`/add\_tag`|添加标签（管理员）|
|`/delete\_tag`|删除标签（管理员）|

提交示例：

```json
{
  "problemId": 1,
  "language": "cpp",
  "code": "#include <iostream>\\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}"
}
```

支持的 `language`：

* `cpp`
* `c++`
* `python`
* `py`

判题状态：

* `Accepted`
* `Wrong Answer`
* `Compile Error`
* `Runtime Error`
* `Time Limit Exceeded`
* `Output Limit Exceeded`
* `System Error`

\---

## 安全边界与已知限制

**请务必阅读。**

### 1\. 没有代码沙箱

用户提交的 C++ / Python 代码是在服务器本机直接运行的，可以：

* 读取服务器上的任意文件
* 访问网络
* 写入临时目录或磁盘
* 启动子进程
* 尝试读取测试点、配置文件、用户数据

当前只做了：

* 每个测试点独立工作目录
* 运行超时
* 输出大小限制
* 进程树清理

**无法阻止恶意代码。** 只能用于可信用户环境。

### 2\. 仅适合局域网

* 默认监听 `0.0.0.0`
* 默认 HTTP，没有 TLS
* Token 通过 Cookie 明文传输
* 没有 Secure Cookie（因为局域网 HTTP 会直接导致无法登录）

不要直接暴露到公网。如需公网使用，请在前面加 HTTPS 反向代理，并重新评估沙箱方案。

### 3\. 存储是 JSON 文件

* 数据量小、并发低时够用
* 不适合大规模并发写入
* 多进程/多实例同时运行会互相覆盖
* 建议只运行一个实例
* 定期备份 `data/` 目录

### 4\. 资源限制不完整

已实现：

* 运行超时
* 1MB 输出上限
* 进程树清理
* 最大并发请求数 32
* 请求超时 30 秒

未实现：

* 内存上限
* CPU 核心隔离
* 磁盘配额
* 注册表/文件系统隔离
* Windows Job Object 级别限制

恶意代码仍然可以占用大量内存或磁盘。

### 5\. 限流是内存实现

* 登录：单 IP 每 5 分钟 30 次
* 注册：单 IP 每 10 分钟 5 次
* 提交：单用户每分钟 12 次
* 用户名登录失败：连续 5 次锁定 5 分钟

限制在进程内存中，重启后清空。阈值需要在代码常量中调整。

### 6\. 数据增长

* `submissions.json` 会持续增长
* `/submissions` 已支持分页，但文件本身不会自动归档
* `judge.log` 超过 5MB 会轮转为 `judge.log.1`

题目和用户量很大时，建议改用 SQLite 或外部数据库。

### 7\. 其他

* 没有邮箱验证、找回密码、修改密码功能
* 管理员账号丢失时，程序会尝试根据 `config.json` 重建；如果配置里没有密码，会生成临时密码并打印在控制台
* 删除题目会同时清理对应的提交记录
* 标签删除会同步清理题目 `meta.json`，失败时会尝试回滚

\---

## 部署建议

1. **不要用管理员账户运行本程序**
建议创建一个专用的低权限 Windows 本地用户来运行。
2. **工作目录放在 NTFS 磁盘**
不要放在 FAT32/exFAT U 盘或只读目录。
3. **限制防火墙来源**
只允许局域网网段访问：

```powershell
   New-NetFirewallRule `
     -DisplayName "WOJ 8000" `
     -Direction Inbound `
     -Protocol TCP `
     -LocalPort 8000 `
     -Action Allow `
     -RemoteAddress LocalSubnet
   ```

4. **定期备份**

```powershell
   Compress-Archive -Path .\\data, .\\problems, .\\config.json `
     -DestinationPath .\\backup-$(Get-Date -Format yyyyMMdd-HHmmss).zip
   ```

5. **不要让不可信用户提交代码**
如果必须接受不可信代码，请改用 Docker / WSL / 独立低权限账号 / Windows Job Object 方案，当前版本不提供这些隔离。

\---

## 常见问题

### Q: 启动提示未找到 g++ 或 Python？

检查 `config.json` 中的路径，或删除 `config.json` 重新运行配置向导。

### Q: Python 判题不可用？

在 `config.json` 的 `python` 字段填写 `python.exe` 的完整路径，然后重启服务。

### Q: 提交后一直是 System Error？

检查：

* `g++` / `python` 路径是否正确
* 题目目录是否存在 `testcases/\*.in` 和 `\*.out`
* 服务器控制台是否有异常输出

\##常见问题

### Q: 能不能公网部署？

不建议。当前版本没有沙箱、没有 HTTPS、没有完整的资源隔离。公网部署前必须做安全加固。

### Q: 为什么数据文件旁边出现 `.corrupt-\*`？

说明原 JSON 文件解析失败，程序已自动备份损坏文件并继续运行。可以从备份中恢复数据。

\---

## 设计取舍

本项目优先考虑：

* 单文件、易部署
* 不依赖数据库
* 不依赖 Docker / WSL
* 适合 Windows 10 局域网小规模使用

因此没有实现：

* 完整沙箱
* 内存/CPU 硬限制
* 分布式判题
* 高并发数据库存储
* HTTPS 证书管理

这些属于后续版本或部署层需要解决的问题。

