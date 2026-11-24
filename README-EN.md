# WeCode Online Judge

A lightweight Online Judge designed for local area networks, suitable for use in school computer labs, clubs, and small teams:

- The backend is a **single Python script** (`judge_server.py`) using only the standard library—no pip install required
- The frontend is **pure vanilla HTML / CSS / JavaScript**—no frameworks, no build step, no CDN
- The problem bank is just a set of folders: `meta.json` + `testcases/`—you can create problems with Notepad
- Suitable for classroom assignments, club practice, personal problem-solving, and other LAN / standalone scenarios

> ⚠️ This project is designed for **trusted small environments** (e.g., a school LAN) and does **not** provide sandbox isolation—
> Submitted code runs **directly with the server's local privileges**. Do not expose it to the public internet or untrusted environments.

---

## Table of Contents

1. [Features at a Glance](#1-features-at-a-glance)
2. [Tech Stack](#2-tech-stack)
3. [Quick Start](#3-quick-start)
4. [Configuration Wizard Details](#4-configuration-wizard-details)
5. [Directory Structure](#5-directory-structure)
6. [Problem Format](#6-problem-format)
7. [Data Files](#7-data-files)
8. [Frontend Architecture](#8-frontend-architecture)
9. [API Overview](#9-api-overview)
10. [Judging Flow](#10-judging-flow)
11. [Security Design](#11-security-design)
12. [Thresholds and Limits Quick Reference](#12-thresholds-and-limits-quick-reference)
13. [FAQ](#13-faq)
14. [Known Inconsistencies and Improvement Directions](#14-known-inconsistencies-and-improvement-directions)
15. [Disclaimer](#15-disclaimer)
16. [License](#16-license)

---

## 1. Features at a Glance

**Frontend (Student Side, `index.html`)**

- Login / registration / automatic session restoration
- Problem list: filter by category, difficulty, and tags; keyword search
- Problem details: statement, samples, online editor (C++ / Python), submit directly and view results in real time
- Submission history: paginated view of past submissions and judging details; one-click restore of last code
- Personal center: view / edit personal information

**Admin Side (Admin Panel, `back_platform.html`)**

- User management: view user list, create accounts, ban / unban
- Problem management: create problems online (statement + test cases), delete problems
- Tag management: add / delete tags; deleting a tag automatically cleans up references in all problems

**Judging (Built into the Backend)**

- Supports C++ (g++, `-std=c++14 -O2`) and Python (`python -I -S`)
- Per-test-case judging: answer comparison ignores trailing whitespace and trailing blank lines
- Time limits, output limits (1MB), and process tree cleanup are all built in

---

## 2. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.10+ standard library | `http.server.ThreadingHTTPServer` + custom routing, zero third-party dependencies |
| Frontend | Vanilla HTML / CSS / JS | ES Modules, Hash routing, no framework, no build |
| Storage | JSON files | `data/*.json` + `problems/*/meta.json`, atomic writes (tmp + os.replace) |
| Compiler | g++ | Auto-detects PATH, Dev-C++ directories, and the registry |
| Interpreter | Python | Auto-detects PATH and common installation locations |
| Authentication | PBKDF2-SHA256 + Cookie | 200,000 rounds of salted hashing; HttpOnly + SameSite=Lax session tokens |

---

## 3. Quick Start

### Requirements

| Component | Requirement |
|---|---|
| Python | 3.10 or later (standard library only) |
| g++ | Optional—if not configured, C++ judging is unavailable |
| OS | Windows / Linux / macOS all supported (judging subprocess management is adapted for both ends) |

### Startup

```bash
cd WeCode_Online_Judge
python judge_server.py
```

On first run, a **configuration wizard** appears (see the next section). After completion:

- Service address: <http://127.0.0.1:8000> (port according to the wizard)
- LAN address: the real local IP is printed at startup, e.g. `http://192.168.1.10:8000`
- Student side: <http://…/index.html>, Admin panel: <http://…/back_platform.html>

> The listening address is fixed at `0.0.0.0`, so devices on the same LAN can access it directly.
> To stop the service: `Ctrl + C`.

---

## 4. Configuration Wizard Details

On first startup (or when `config.json` is missing / incomplete), 5 items are asked in sequence; pressing Enter accepts the default for all of them:

| Step | Item | Default | Notes |
|---|---|---|---|
| 1/5 | Service port | `8000` | 1–65535; invalid input falls back to 8000 |
| 2/5 | g++ path | Auto-detected | Detection order: PATH → common Dev-C++ install directories → registry |
| 3/5 | Python path | Auto-detected | Detection order: PATH → common installation directories |
| 4/5 | Admin username | `admin` | |
| 5/5 | Admin password | `admin123` | ⚠️ Strongly recommend changing to a strong password |

Configuration is written to `config.json`. On first initialization, the admin password is hashed and stored, and then the **plaintext is removed from config.json**. At least one of g++ and Python must be configured; otherwise startup fails and exits.

To rerun the wizard: delete `config.json` and restart.

---

## 5. Directory Structure

```
WeCode_Online_Judge/
├── judge_server.py        # Entire backend: HTTP server + judging core (single file)
├── index.html             # Student entry (single page, Hash routing)
├── back_platform.html     # Admin panel entry
├── run.bat                # (Optional) Windows one-click launch
│
├── css/
│   ├── main.css           # Entry: @import the other layered styles
│   ├── base.css           # Variables, reset, fonts
│   ├── layout.css         # Navbar, page container layout
│   ├── components.css     # Buttons, forms, cards, and other common components
│   ├── pages.css          # Styles for each business page
│   └── admin.css          # Admin-specific (sidebar, panels)
│
├── js/
│   ├── main.js            # Student startup: restore session → render nav → init router
│   ├── admin-main.js      # Admin startup
│   ├── config.js          # Frontend constants (API_BASE, default code templates)
│   ├── api.js             # fetch wrapper: unified JSON / errors / cookies
│   ├── store.js           # Minimal global state (current user)
│   ├── router.js          # Hash routing + login guard
│   ├── ui.js              # Navbar rendering
│   ├── utils.js           # escapeHtml and other utilities
│   └── pages/
│       ├── auth.js        # Login / registration
│       ├── problems.js    # Problem list
│       ├── detail.js      # Problem details + code editor + submission
│       ├── submissions.js # Submission history
│       ├── profile.js     # Personal center
│       └── admin.js       # Three admin panels (users / problems / tags)
│
├── assets/icons/          # Built-in SVG icons (hand-drawn, no external fonts/icon libraries)
│
├── problems/              # Problem bank (auto-created on first startup)
│   └── Q0001/
│       ├── meta.json      # Problem metadata
│       └── testcases/     # Test cases: 1.in / 1.out, 2.in / 2.out …
│
├── data/                  # Runtime data (auto-created)
│   ├── users.json         # Users (passwords are PBKDF2 hashes)
│   ├── submissions.json   # Submission records
│   ├── tags.json          # Tag pool
│   └── tokens.json        # Session tokens
│
├── logs/
│   └── judge.log          # Judging log (auto-rotates at 5MB)
│
└── config.json            # Service configuration (generated by wizard; plaintext admin password is auto-removed if present)
```

---

## 6. Problem Format

Each problem is a directory under `problems/`, named like `Q0001` (also compatible with `1`, `q1`, etc.; the number is the problem ID). The directory must contain `meta.json`, and test cases go in the `testcases/` subdirectory.

### meta.json Fields

```json
{
  "title": "A+B Problem",
  "difficulty": "Beginner",
  "category": "Sequential Structure",
  "description": "Input two integers and output their sum.",
  "exampleInput": "1 2",
  "exampleOutput": "3",
  "tags": ["Simulation", "Beginner"],
  "timeLimit": 2000
}
```

| Field | Required | Notes |
|---|---|---|
| `title` | Recommended | Problem title; defaults to "Untitled Problem" if missing |
| `difficulty` | No | Difficulty text; defaults to `Beginner` |
| `category` | No | Category text; defaults to `Uncategorized` |
| `description` | No | Problem statement (plain text; frontend renders with HTML escaping) |
| `exampleInput` / `exampleOutput` | No | Samples; display only, **not used in judging** |
| `tags` | No | Tag array; recommended to choose from the tag pool |
| `timeLimit` | No | Per-test-case time limit (ms); automatically clamped to 100–10000, default `2000` |

### testcases/

- Naming rule: `N.in` paired with `N.out` (N starts from 1; judged in filename sort order)
- Only paired `.in/.out` files are judged; a problem must have **at least one test case**, otherwise submissions always return System Error
- Want multiple data sets? Just add `2.in`/`2.out`, `3.in`/`3.out`, etc.

You can also skip creating files manually and create problems directly in the admin panel's "Problem Management" form (including adding test cases one by one).

---

## 7. Data Files

All located in `data/`, all UTF-8 JSON. Writes use "temp file + atomic replace" and are protected by a global lock, making them thread-safe under concurrency.

| File | Structure | Notes |
|---|---|---|
| `users.json` | Array of user objects | `id / username / password(hash) / email / isAdmin / isBanned / createdAt` |
| `submissions.json` | Array of submission objects | `id / userId / problemId / problemTitle / code / language / status / detail / createdAt` |
| `tags.json` | Array of strings | Tag pool; initialized with Luogu-style tags on first setup (Simulation, DP, Graph Theory, Data Structures…) |
| `tokens.json` | Token → `{userId, createdAt}` | Session tokens; expired after 7 days and auto-cleaned |

Fault tolerance: If any JSON fails to parse, the corrupted file is first backed up as `xxx.corrupt-timestamp` before returning defaults, preventing silent overwriting of corrupted files.

---

## 8. Frontend Architecture

Two independent entries sharing the same set of modules:

- **Student side**: `index.html` + `js/main.js` — routed pages are login, registration, problem list, problem details, submission history, personal center
- **Admin side**: `back_platform.html` + `js/admin-main.js` — sidebar switches between users / problems / tags panels; admin identity is verified before entry

Key design points:

- **Hash routing** (`#/problems`, `#/problem/1`…): `router.js` dispatches uniformly; accessing restricted pages while logged out automatically redirects to login
- **ES Modules**: `<script type="module">`, loaded natively by the browser—no bundling needed
- **Session restoration**: `main.js` requests `/me` at startup; if the cookie is valid, it enters the logged-in state directly
- **XSS protection**: All user-controllable content (usernames, statements, tags, etc.) is escaped via `escapeHtml` in `utils.js` before rendering
- **Zero external dependencies**: No CDN, no font libraries, no icon libraries—all resources are local and self-contained, so it works offline on an intranet

Style layering: `main.css` serves as the entry and imports in the order `base → layout → components → pages` (admin additionally includes `admin.css`).

---

## 9. API Overview

All endpoints are accessed same-origin (frontend and backend deployed together). Request bodies are JSON; all endpoints except login / registration require a valid session cookie (`woj_token`).

### Authentication

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/login` | Public | Login; sets an HttpOnly cookie on success; IP rate limit 30 requests / 5 minutes; same username locked for 5 minutes after 5 consecutive failures |
| POST | `/register` | Public | Registration; username 2–32 chars, password 6–128 chars, email optional; IP rate limit 5 requests / 10 minutes |
| POST | `/logout` | Logged in | Logout (revoke token + clear cookie) |
| GET | `/me` | Logged in | Current user info (excluding password field) |

### Business

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/problems` | Public | Full problem list (scans problem directories in real time) |
| GET | `/submissions?page=1&pageSize=100` | Logged in | Current user's submission records, paginated (default 100 per page, max 200) |
| GET | `/tags` | Public | Tag pool |
| POST | `/submit` | Logged in | Submit code and **return judging result synchronously**; user rate limit 12 requests / 60 seconds; code ≤ 50KB |
| GET | `/users` | Admin | User list (excluding password field) |

### Admin (All Require Admin)

| Method | Path | Notes |
|---|---|---|
| POST | `/create_user` | Create user (validation rules same as registration) |
| POST | `/toggle_ban` | Ban / unban user (cannot operate on admins) |
| POST | `/add_problem` | Create problem (including test cases; problem number auto-assigned as max number + 1) |
| POST | `/delete_problem` | Delete problem (moves to temp directory first, then cleans up; associated submissions also deleted; rollback on failure) |
| POST | `/add_tag` / `/delete_tag` | Add / delete tags (deleting automatically cleans up references in all problems) |

### Error Responses

Uniformly `{"error": "Chinese error message"}`. Status codes include: `400 Bad Request`, `401 Unauthorized`, `403 Forbidden/Banned`, `404 Not Found`, `413 Payload Too Large`, `429 Rate Limited`, `500 Internal Server Error`.

---

## 10. Judging Flow

```
POST /submit
  ├─ Auth (logged in + not banned) + user-level rate limit (12 requests/minute)
  ├─ Parameter validation (language / non-empty code / ≤50KB / problem exists)
  ├─ Acquire judging semaphore (global max 2 concurrent judgings)
  │    └─ During judging, actively yield the HTTP concurrency slot to avoid starving other endpoints
  ├─ judge_submission()
  │    ├─ Check testcases/ (no test cases → System Error immediately, no wasted compilation)
  │    ├─ C++: g++ -O2 -std=c++14 -DONLINE_JUDGE compilation (20s limit)
  │    │       Python: python -I -S main.py
  │    └─ Run per test case:
  │          Timeout        → Time Limit Exceeded
  │          Output > 1MB   → Output Limit Exceeded
  │          Return code ≠ 0 → Runtime Error (with first 500 chars of stderr)
  │          Text mismatch   → Wrong Answer (ignores trailing whitespace and trailing blank lines)
  │          All passed      → Accepted
  ├─ Write judging log to logs/judge.log
  ├─ Append submission record to data/submissions.json
  └─ Return {"status": "...", "detail": "..."} synchronously
```

**Restricted subprocesses**: Judged code runs in a one-time temporary working directory with a minimal environment variable set. On timeout / output overflow, the entire process tree is killed (Windows `taskkill /T`; POSIX `setsid` + `killpg`). Residual child processes are also cleaned up after normal exit.

**Status values**: `Accepted` / `Wrong Answer` / `Compile Error` / `Runtime Error` / `Time Limit Exceeded` / `Output Limit Exceeded` / `System Error`.

---

## 11. Security Design

| Mechanism | Implementation |
|---|---|
| Password storage | PBKDF2-SHA256, 200,000 rounds, per-user salt; legacy plaintext passwords auto-migrated on login or startup |
| Session | 32-byte random token, HttpOnly + SameSite=Lax + Path=/, 7-day expiry; revoked on logout |
| CSRF | All POSTs validate that `Origin` matches `Host`; CORS preflight only writes credentials headers for same-origin |
| Login brute force | Same username locked for 5 minutes after 5 consecutive failures; IP-level sliding window rate limiting |
| Request body | 512KB limit; non-UTF-8 / non-JSON-object requests rejected directly |
| Path traversal | Static serving whitelist (only `index.html`, `back_platform.html`, `css/js/assets/`), rejects `..`, and performs realpath normalization as a second check |
| Data safety | Global lock + atomic writes; corrupted JSON auto-backed up and reset |
| Exception fallback | Uncaught handler exceptions uniformly return JSON 500 without breaking the connection |
| Judging isolation | ⚠️ **No sandbox**—see the disclaimer at the top; already done: minimal environment variables, output limits, process tree cleanup |

---

## 12. Thresholds and Limits Quick Reference

| Item | Value | Location (judge_server.py constant) |
|---|---|---|
| HTTP concurrent requests | 32 | `MAX_CONCURRENT_REQUESTS` |
| Concurrent judgings | 2 | `JUDGE_SEMAPHORE` |
| Per-request timeout | 30s | `REQUEST_TIMEOUT_SECONDS` |
| Request body limit | 512KB | `MAX_BODY_BYTES` |
| Submission code limit | 50KB | Inline validation in `/submit` |
| Submission rate limit | 12 / 60s / user | `/submit` |
| Registration rate limit | 5 / 600s / IP | `/register` |
| Login rate limit | 30 / 300s / IP | `/login` |
| Login failure lockout | 5 failures → 300s lock / username | `LOGIN_FAILS` |
| Per-test-case time limit | 100–10000ms, default 2000 | `clamp_time_limit` |
| Compilation timeout | 20s | Inline in judging core |
| Program output limit | 1MB | `MAX_OUTPUT_BYTES` |
| Session validity | 7 days | `TOKEN_TTL_DAYS` |
| Judging log rotation | 5MB | `JUDGE_LOG_MAX_BYTES` |
| Submission pagination | Default 100, max 200 | `SUBMISSIONS_PAGE_SIZE_*` |
| Problem tags | ≤ 100 per problem | `/add_problem` |
| Tag length | ≤ 32 chars | `/add_tag` |

---

## 13. FAQ

**Q: After startup, all C++ submissions return System Error "g++ not configured"?**
A: g++ was not detected during the wizard. Install MinGW / Dev-C++ and either delete `config.json` to rerun the wizard, or manually enter the full g++ path into the `gpp` field of `config.json`.

**Q: Want to change the port / switch compilers?**
A: Edit `config.json` directly (`port`, `gpp`, `python`) and restart for it to take effect.

**Q: Forgot the admin password?**
A: Deleting `data/users.json` will recreate the initial admin (requires the plaintext password to still be in `config.json`, or rerun the wizard). A safer approach is to edit `users.json` directly: replace the corresponding admin's `password` field with a new plaintext password; the system will automatically hash it on restart.

**Q: Changed a problem's meta but the page hasn't changed?**
A: `/problems` scans the problem bank in real time on every request—just refresh the page. If browser caching is involved, do a hard refresh (Ctrl+F5).

**Q: Judging is slow / blocks other pages?**
A: Judging has a global max of 2 concurrent judgings and yields HTTP slots, so it normally won't drag each other down. If it's still slow, check whether the problem's `timeLimit` is set too high (max 10s).

**Q: How to back up?**
A: Copy the three locations `problems/`, `data/`, and `config.json` for a complete restore.

---

## 14. Known Inconsistencies and Improvement Directions

Honestly documenting the current version's known issues (intentionally retained, pending future decisions):

1. **Judging is synchronous**: `/submit` blocks until judging completes before returning (mitigated by concurrency limits + yielding HTTP slots). Full decoupling would require changing to "enqueue + frontend polling".
2. **`submissions.json` single-file storage**: Each submission reads/writes the entire file, which slows down as data grows; the frontend relies on the returned `code` for "restore last code", so fields have not been trimmed yet.
3. **No sandbox**: Judged code runs with the server's local privileges—see the disclaimer.
4. **Optional items not done**: HTTP/1.1 keep-alive, in-memory caching of problem metadata, `-std=c++17`, etc.—add as needed.

---

## 15. Disclaimer

- This software is provided "as is", without any express or implied warranty. The author assumes no liability for any losses arising from the use of this software.
- **Judging is not isolated**: Submitted code runs directly on the host with the privileges of the server process. Deploy only in environments where users trust each other (e.g., a teaching intranet), and bear the resulting risks yourself.
- Do not deploy this system on the public internet or in environments that allow untrusted third parties to submit code.

---

## 16. License

This project uses **dual licensing divided by content type**:

### Source Code — MPL-2.0

All source code files (`.py`, `.js`, `.css`, `.html`) are released under the
**Mozilla Public License 2.0 (MPL-2.0)**.

- SPDX identifier: `MPL-2.0`
- Full text: <https://www.mozilla.org/MPL/2.0/>
- Key points: **file-level** copyleft—you are free to use, modify, commercialize, and redistribute this project's code; however, **modified MPL files themselves** must continue to be open-sourced under MPL-2.0, while newly added independent files may choose their own license.
- It is recommended to retain the following notice at the top of modified source files (MPL-2.0 Exhibit A template):

  ```
  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at https://mozilla.org/MPL/2.0/.
  ```

### Documentation and Non-Code Assets — CC BY-NC-ND 4.0

The README and other documentation, SVG icons under `assets/`, sample problem texts, and other non-code assets are released under
**Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)**.

- SPDX identifier: `CC-BY-NC-ND-4.0`
- Full text: <https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.zh>
- Key points:
  - **BY (Attribution)**: Reposts must credit the source and author;
  - **NC (NonCommercial)**: May not be used for commercial purposes;
  - **ND (NoDerivatives)**: May be reposted as-is, but **may not be modified and then redistributed**.

> ⚠️ Note the boundary between the two: MPL-2.0 allows modification and commercial use of code, while CC BY-NC-ND does not allow adaptation or commercial use of documentation/assets. If you need to modify documentation or use it in commercial scenarios, you must obtain separate authorization.
> In case of conflict between source code comments and documentation, this section prevails.

### Content Outside the Scope of Licensing

The following content is **not covered by the above license grants** and is distributed with the repository only as running examples / runtime artifacts:

- Runtime data under `data/` and `logs/` (including users' personal information and submitted code);
- `config.json` (local deployment configuration);
- Problem content created by users and code submitted by users—rights belong to their authors;
- Third-party toolchains such as Python and g++ in the system, each governed by its own license.

The names "WeCode Online Judge" and "WeCode OJ" and their marks are not granted any trademark authorization and may not be used in scenarios implying endorsement without permission.
