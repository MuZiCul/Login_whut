# Login_whut — 武汉理工校园网自动登录

对 [MuZiCul/little_demo](https://github.com/MuZiCul/little_demo) 中 `WHUT/` 目录三份登录脚本的**修复与合并版**：
把原先重复的三份实现（`Login_whut.py` / `LWNK_min.py` / `LWNK_hardcoded.py`）整合为一个包 + 一个入口脚本，
去掉硬编码凭据、修掉导致配置文件永远读不到的致命拼写错误，并补齐依赖清单与单元测试。

## 目录结构

```
Login_whut/
├── login_whut.py           # 入口：python login_whut.py
├── whut_login/             # 主包
│   ├── config.py           # 凭据文件读写（明文 / {B}+base64）
│   ├── portal.py           # srun 门户认证客户端
│   ├── netcheck.py         # 联网检测 + Windows 系统代理读取
│   └── cli.py              # 命令行参数与重试流程
├── tests/                  # pytest 单元测试（全部 mock，不发起真实请求）
├── WHUT/                   # 上游原始脚本快照，仅作对照，不被主程序引用
├── requirements.txt        # 运行时依赖
├── requirements-dev.txt    # 开发依赖
├── config.example.txt      # 凭据文件示例
└── pytest.ini
```

## 依赖情况

- **本地模块依赖：无。** 三份上游脚本的 `import` 全部审计过，只用到标准库（`time` / `random` / `uuid` / `base64` / `winreg`）与一个第三方包。
- **第三方运行时依赖：仅 `requests`**（见 `requirements.txt`）。
- 开发额外需要 `pytest`（见 `requirements-dev.txt`）。
- 依赖已在本项目内落地（`.venv/`，已被 `.gitignore` 忽略），无需全局安装。

```powershell
# 依赖已安装到项目内 .venv；如需重建：
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 快速开始

```powershell
# 1) 配置凭据（可选，也可运行时交互输入）
Copy-Item config.example.txt config.txt
notepad config.txt          # 第 1 行账号，第 2 行密码

# 2) 检查网络是否已连通
.\.venv\Scripts\python.exe login_whut.py --check-only

# 3) 未登录时自动登录（已连通则直接退出）
.\.venv\Scripts\python.exe login_whut.py

# 4) 查看全部参数
.\.venv\Scripts\python.exe login_whut.py --help
```

`config.txt` 格式为两行 UTF-8 文本（不支持注释行，空行会被忽略）：

```
testuser
你的密码
```

第 2 行也可以直接填 `{B}` + base64 形式；两种写法都会在发送前统一编码，读取时自动还原明文。

## 命令行参数

| 参数 | 说明 |
|---|---|
| `-u, --username` | 账号，优先于凭据文件 |
| `-p, --password` | 密码（明文或 `{B}+base64`），优先于凭据文件 |
| `-c, --config` | 凭据文件路径，默认项目根目录 `config.txt` |
| `--portal` | 门户地址，默认 `http://172.30.16.34` |
| `--ac-id` | 指定 `ac_id`；缺省时依次尝试 `0` 与 `5` |
| `--timeout` | 单次请求超时秒数，默认 5 |
| `--proxy` / `--no-proxy` | 指定代理 / 禁用代理（默认自动读取 Windows 系统代理） |
| `--retries` | 重试次数，默认 5；`0` 表示不限次数 |
| `--interval` | 重试间隔秒数，默认 10 |
| `--save-config` | 把本次凭据写入凭据文件 |
| `--no-input` | 禁止交互输入，缺少凭据时直接失败（适合计划任务） |
| `--check-only` | 仅检测网络连通性 |
| `-v, --verbose` | 输出调试信息 |

退出码：`0` 已连通 / 登录成功，`1` 未连通 / 登录失败 / 凭据缺失，`130` 用户中断。

## 相对上游的修复清单

| # | 上游问题 | 修复方式 |
|---|---|---|
| 1 | `Login_whut.py:68` `encoding='utf=8'` 拼写错误，被裸 `except` 吞掉 → `config.txt` 永远读不到，每次退化为交互输入（**功能失效根因**） | 统一由 `whut_login/config.py` 以 `utf-8` 读取，异常类型明确为 `ConfigError` |
| 2 | `__file__.split("/")` 在 Windows 下拼路径失败，`config.txt` 保存必然失败；`split("/", -1)` 语义无效 | 改用 `pathlib`，默认路径由包位置推导 |
| 3 | `"user_mac": self.get_mac_address` 漏写 `()`，实际发送 `bound method` 字符串 | 改为 `get_mac_address()`，并加回归测试 |
| 4 | `config.txt` 未校验行数，仅 1 行时 `config[1]` 抛 `IndexError` | 行数不足时抛可读的 `ConfigError`，忽略空行以兼容 CRLF |
| 5 | 请求头硬编码 `Content-Length: 109`，与真实表单长度不符 | 移除，交由 requests 计算 |
| 6 | 失败后无上限 `while` 死循环，无退避、无退出码 | 默认重试 5 次、间隔 10 秒，可用 `--retries 0` 恢复不限次数；返回明确退出码 |
| 7 | `LWNK_hardcoded.py` 源码内硬编码账号密码 | 移除硬编码，改由凭据文件 / 命令行 / 交互输入提供 |
| 8 | 开启代理但 `ProxyServer` 取值异常时返回 `":"`，拼出无效代理 | 取值校验后再构造，失败视为未配置代理 |
| 9 | 交互输入密码明文回显 | 改用 `getpass` 掩码输入 |
| 10 | 三份脚本逻辑重复（近 120 行 × 3） | 合并为单一实现，`ac_id` 候选自动逐个尝试 |

> `WHUT/LWNK_hardcoded.py` 里仍保留上游硬编码的账号密码（作为原始快照）。该文件属私有仓库内容，建议后续单独从上游仓库删除或改为读取环境变量。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

覆盖范围：凭据编码/解析/读写与异常分支、表单与请求头构造（含上述 bug 的回归用例）、`ac_id` 回退、连通性判定边界、代理构造，以及 CLI 的凭据优先级、凭据落盘、重试与退出码。全部用假 Session / 假客户端，不发起真实网络请求。

## 认证协议要点

- 端点：`POST http://172.30.16.34/include/auth_action.php`（srun 门户）
- 表单：`action=login`、`ajax=1`、`ac_id`、`username`、`password`（`{B}` + base64）、`save_me=1`、`nas_ip`、`user_ip`、`user_mac`
- 成功判定：响应体包含 `login_ok` 或 `successful`
- `ac_id` 会随校区 / 接入设备变化，登录不上时可先用 `--ac-id` 试不同取值
