# Login_whut — 武汉理工校园网自动登录

一个独立的武汉理工校园网自动登录工具。项目源于对早期三份重复脚本（`Login_whut.py` / `LWNK_min.py` / `LWNK_hardcoded.py`，**均不随本仓库分发**）的合并与重写：
去掉硬编码凭据、修掉导致配置文件永远读不到的致命拼写错误，并补齐依赖清单。

## 目录结构

```
Login_whut/
├── login_whut.py           # 入口：python login_whut.py
├── cli.py                  # 命令行参数与重试流程
├── config.py               # 凭据文件（config.json）读写与校验；文档内含格式示例
├── portal.py               # srun 门户认证客户端
├── netcheck.py             # 联网检测 + Windows 系统代理读取
├── config.json             # 凭据文件（首次运行时生成，已被 .gitignore 忽略）
└── requirements.txt        # 运行时依赖
```

## 依赖情况

- **本地模块依赖：无。** 项目全部 `import` 已审计，只用到标准库（`time` / `random` / `uuid` / `base64` / `winreg`）与一个第三方包。
- **第三方运行时依赖：仅 `requests`**（见 `requirements.txt`）。
- 依赖已在本项目内落地（`.venv/`，已被 `.gitignore` 忽略），无需全局安装。

```powershell
# 依赖已安装到项目内 .venv；如需重建：
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 快速开始

```powershell
# 1) 创建凭据文件（推荐交互式生成；格式说明与示例见 config.py 模块文档）
.\.venv\Scripts\python.exe login_whut.py --init-config

# 2) 检查网络是否已连通
.\.venv\Scripts\python.exe login_whut.py --check-only

# 3) 未登录时自动登录（已连通则直接退出）
.\.venv\Scripts\python.exe login_whut.py

# 4) 查看全部参数
.\.venv\Scripts\python.exe login_whut.py --help
```

## 凭据文件与安全

凭据统一放在项目根目录的 `config.json`（UTF-8 JSON），**代码里不再出现任何账号密码**：

```json
{
  "username": "你的学号或工号",
  "password": "你的密码"
}
```

- `password` 默认按**明文**保存；也兼容 `{B}` + base64 旧写法，读取时自动还原明文。
- 认证请求中该字段按**明文**提交（老版 srun 门户接受明文，详见「认证协议要点」）。
- 字段缺失、类型错误、JSON 语法错误、非法 base64 都会抛出明确的 `ConfigError`，不会静默使用错误凭据。
- 该文件已写入 `.gitignore`，**不会进入版本库**。
- 读取优先级：命令行参数 → `config.json` → 交互输入（交互输入后若文件不存在会自动生成）。

> 注意：`config.json` 属于「与代码分离 + 不入库」，**并非加密存储**——任何能读到该文件的人都能还原密码。
> 如需额外收紧权限，可用 Windows ACL 只允许当前用户读写：
>
> ```powershell
> icacls config.json /inheritance:r /grant:r "$env:USERNAME:(R,W)"
> ```

## 命令行参数

| 参数 | 说明 |
|---|---|
| `-u, --username` | 账号，优先于凭据文件 |
| `-p, --password` | 密码（明文，也接受 `{B}+base64`），优先于凭据文件 |
| `-c, --config` | 凭据文件路径，默认项目根目录 `config.json` |
| `--portal` | 门户地址，默认 `http://172.30.16.34` |
| `--ac-id` | 指定 `ac_id`；缺省时依次尝试 `0` 与 `5` |
| `--timeout` | 单次请求超时秒数，默认 5 |
| `--proxy` / `--no-proxy` | 指定代理 / 禁用代理（默认自动读取 Windows 系统代理） |
| `--retries` | 重试次数，默认 5；`0` 表示不限次数 |
| `--interval` | 重试间隔秒数，默认 10 |
| `--init-config` | 交互式创建凭据文件后退出（不执行登录） |
| `--save-config` | 把本次凭据写入凭据文件 |
| `--no-input` | 禁止交互输入，缺少凭据时直接失败（适合计划任务） |
| `--check-only` | 仅检测网络连通性 |
| `-v, --verbose` | 输出调试信息 |

退出码：`0` 已连通 / 登录成功，`1` 未连通 / 登录失败 / 凭据缺失，`130` 用户中断。

## 设计说明（已规避的历史缺陷）

> 下表列出的问题来自项目早期的三份脚本（**不随本仓库分发**），现行实现均已规避；
> 表中的 `config.txt` 指那些脚本使用的凭据文件，本项目已改用 `config.json`。

| # | 历史缺陷 | 现行处理 |
|---|---|---|
| 1 | `Login_whut.py:68` `encoding='utf=8'` 拼写错误，被裸 `except` 吞掉 → `config.txt` 永远读不到，每次退化为交互输入（**功能失效根因**） | 统一由 `config.py` 以 `utf-8` 读取，异常类型明确为 `ConfigError` |
| 2 | `__file__.split("/")` 在 Windows 下拼路径失败，`config.txt` 保存必然失败；`split("/", -1)` 语义无效 | 改用 `pathlib`，默认路径由包位置推导 |
| 3 | `"user_mac": self.get_mac_address` 漏写 `()`，实际发送 `bound method` 字符串 | 改为 `get_mac_address()` |
| 4 | `config.txt` 未校验行数，仅 1 行时 `config[1]` 抛 `IndexError` | 行数不足时抛可读的 `ConfigError`，忽略空行以兼容 CRLF |
| 5 | 请求头硬编码 `Content-Length: 109`，与真实表单长度不符 | 移除，交由 requests 计算 |
| 6 | 失败后无上限 `while` 死循环，无退避、无退出码 | 默认重试 5 次、间隔 10 秒，可用 `--retries 0` 恢复不限次数；返回明确退出码 |
| 7 | `LWNK_hardcoded.py`（原文件名即学号）源码内硬编码账号密码 | 移除硬编码，改由凭据文件 / 命令行 / 交互输入提供 |
| 8 | 开启代理但 `ProxyServer` 取值异常时返回 `":"`，拼出无效代理 | 取值校验后再构造，失败视为未配置代理 |
| 9 | 交互输入密码明文回显 | 改用 `getpass` 掩码输入 |
| 10 | 三份脚本逻辑重复（近 120 行 × 3） | 合并为单一实现，`ac_id` 候选自动逐个尝试 |
| 11 | 凭据以两行纯文本存放，格式脆弱、无字段校验、易被误提交 | 改为独立 `config.json`（含字段级校验与明确报错），新增 `--init-config` 生成入口，并纳入 `.gitignore` |
| 12 | 早期实现把密码包装成 `{B}` + base64 后提交 | 改为**明文提交**（与同校其他实现一致，老版门户本就接受明文）；仍兼容读取 `{B}` 形式的旧配置并自动还原 |

## 认证协议要点

### 深澜（srun）是什么

杭州深澜软件有限公司（1999 年成立，总部杭州）的认证计费产品线（Srun 3000 / Srun 4K / OTP），
支持 Portal / PPPoE / 802.1x 等接入方式。校园网里连上 Wi-Fi 后自动弹出的认证页即其 Portal，
武汉理工用的就是它。

### 本项目使用的接口

- 端点：`POST http://172.30.16.34/include/auth_action.php`（老版 srun Portal 的 AJAX 接口）
- 表单：`action=login`、`ajax=1`、`ac_id`、`username`、`password`、`save_me=1`、`nas_ip`、`user_ip`、`user_mac`
- 成功判定：响应体包含 `login_ok` 或 `successful`
- `ac_id` 会随校区 / 接入设备变化，登录不上时可先用 `--ac-id` 试不同取值

### 密码字段的编码前缀（深澜生态通用约定）

| 前缀 | 含义 | 适用版本 |
|---|---|---|
| 无前缀 | **明文**（本项目采用） | 老版 Portal |
| `{B}` | Base64 编码（`B` 即 Base64，**是编码不是加密**） | 老版 Portal |
| `{MD5}` | `HMAC-MD5(password, key=challenge)` | 新版 challenge 协议 |
| `{SRBX1}` | XOR 加密 + 非标准字符表 base64，用于新版 `i` 参数 | 新版协议 |
| — | `chksum` = SHA1 校验和 | 新版协议 |

老版门户对无前缀明文与 `{B}` + base64 都能识别，因此本项目直接提交明文；配置文件中若沿用
`{B}` 写法，读取时会先还原为明文再提交。

### 武汉理工认证接口的演进（排查登录失败时先看这里）

| 阶段 | 接口 | 密码 / 附加要求 |
|---|---|---|
| 老 PC Portal | `http://172.30.16.34/srun_portal_pc.php` | 明文，表单含 `ac_id` |
| 老 AJAX | `http://172.30.16.34/include/auth_action.php` | 明文或 `{B}`+base64（**本项目**） |
| 新 API | `http://172.30.21.100/api/account/login` | 明文 + `x-csrf-token` 头；需先 `GET /api/csrf-token`，`nasId` 由 msftconnecttest 重定向解析 |

校网络信息中心在 2023-02、2024-04、2026-02 多次升级认证系统。**若实测登录失败，请先 F12 抓包确认
当前接口与字段**，不要在旧接口上反复调 `ac_id`。

## 许可证

[MIT](LICENSE) © 2026 MuZiCul

> 本项目仅供个人在自有设备上自动化登录校园网使用，请遵守学校网络使用规定。
