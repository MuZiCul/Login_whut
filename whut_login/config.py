"""凭据文件（``config.txt``）的读写。

文件格式为 UTF-8 文本、两行：

* 第 1 行：账号（学号 / 工号）
* 第 2 行：密码，明文或 ``{B}`` + base64 形式均可

空行会被忽略，因此 CRLF 换行、末尾多余空行都能正常解析。
"""

from __future__ import annotations

import base64
from pathlib import Path

PASSWORD_PREFIX = "{B}"
DEFAULT_CONFIG_NAME = "config.txt"


class ConfigError(Exception):
    """凭据文件缺失或内容不合法。"""


def encode_password(password: str) -> str:
    """把明文密码编码为门户要求的 ``{B}`` + base64 形式。

    已经是 ``{B}`` 前缀的输入会原样返回，保证幂等。
    """
    if password.startswith(PASSWORD_PREFIX):
        return password
    encoded = base64.b64encode(password.encode("utf-8")).decode("ascii")
    return PASSWORD_PREFIX + encoded


def decode_password(password: str) -> str:
    """把 ``{B}`` + base64 形式还原为明文；非该形式时原样返回。"""
    if not password.startswith(PASSWORD_PREFIX):
        return password
    payload = password[len(PASSWORD_PREFIX):]
    try:
        return base64.b64decode(payload, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConfigError("凭据文件中的密码不是合法的 base64 编码") from exc


def parse_config(text: str) -> tuple[str, str]:
    """解析凭据文本，返回 ``(账号, 明文密码)``。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ConfigError("凭据文件需要两行内容：第 1 行账号，第 2 行密码")
    return lines[0], decode_password(lines[1])


def default_config_path() -> Path:
    """默认凭据文件路径：项目根目录下的 ``config.txt``。"""
    return Path(__file__).resolve().parent.parent / DEFAULT_CONFIG_NAME


def load_config(path: str | Path | None = None) -> tuple[str, str]:
    """读取凭据文件并返回 ``(账号, 明文密码)``。

    :raises ConfigError: 文件不存在或内容不合法。
    """
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise ConfigError(f"凭据文件不存在：{config_path}")
    return parse_config(config_path.read_text(encoding="utf-8"))


def save_config(
    path: str | Path | None,
    username: str,
    password: str,
    *,
    encode: bool = True,
) -> Path:
    """写入凭据文件并返回实际路径。

    默认以 ``{B}`` + base64 形式保存密码，与上游脚本保持一致。
    """
    config_path = Path(path) if path is not None else default_config_path()
    stored = encode_password(password) if encode else password
    config_path.write_text(f"{username}\n{stored}\n", encoding="utf-8")
    return config_path
