"""凭据文件（``config.json``）的读写。

文件格式为 UTF-8 JSON::

    {
      "username": "你的学号或工号",
      "password": "你的密码"
    }

``password`` 支持明文或 ``{B}`` + base64 两种写法（读取时统一还原为明文），
写出时默认保存明文（``encode=True`` 可改存 ``{B}`` + base64 形式）。

.. warning::
   本文件只做「与代码分离 + 不入版本库」的隔离，**并非加密存储**。
   请确保该文件不会被他人读取（Windows 下可用 ``icacls`` 收紧权限，见 README）。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

PASSWORD_PREFIX = "{B}"
DEFAULT_CONFIG_NAME = "config.json"

USERNAME_FIELD = "username"
PASSWORD_FIELD = "password"


class ConfigError(Exception):
    """凭据文件缺失、无法解析或字段不合法。"""


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
    """解析凭据 JSON 文本，返回 ``(账号, 明文密码)``。

    :raises ConfigError: JSON 语法错误或字段缺失 / 类型不合法。
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"凭据文件不是合法的 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("凭据文件顶层必须是 JSON 对象，例如 {\"username\": ..., \"password\": ...}")

    username = data.get(USERNAME_FIELD)
    password = data.get(PASSWORD_FIELD)
    if not isinstance(username, str) or not username.strip():
        raise ConfigError(f'凭据文件缺少非空字符串字段 "{USERNAME_FIELD}"')
    if not isinstance(password, str) or not password:
        raise ConfigError(f'凭据文件缺少非空字符串字段 "{PASSWORD_FIELD}"')

    return username.strip(), decode_password(password)


def default_config_path() -> Path:
    """默认凭据文件路径：项目根目录下的 ``config.json``。"""
    return Path(__file__).resolve().parent.parent / DEFAULT_CONFIG_NAME


def load_config(path: str | Path | None = None) -> tuple[str, str]:
    """读取凭据文件并返回 ``(账号, 明文密码)``。

    :raises ConfigError: 文件不存在、无法读取或内容不合法。
    """
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise ConfigError(f"凭据文件不存在：{config_path}")
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"凭据文件读取失败：{exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"凭据文件必须是 UTF-8 编码：{exc}") from exc
    return parse_config(text)


def save_config(
    path: str | Path | None,
    username: str,
    password: str,
    *,
    encode: bool = False,
) -> Path:
    """写入凭据文件并返回实际路径。

    默认按明文保存密码；``encode=True`` 时改存 ``{B}`` + base64 形式
    （两种写法读取时都能还原为明文）。
    """
    config_path = Path(path) if path is not None else default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    stored = encode_password(password) if encode else password
    payload = {USERNAME_FIELD: username, PASSWORD_FIELD: stored}
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path
