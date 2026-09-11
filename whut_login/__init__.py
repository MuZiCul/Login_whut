"""武汉理工大学（WHUT）校园网 srun 门户自动登录。

本包为独立实现，整合并修复了项目早期三份重复脚本中的缺陷。
"""

from .config import (
    DEFAULT_CONFIG_NAME,
    PASSWORD_PREFIX,
    ConfigError,
    decode_password,
    default_config_path,
    encode_password,
    load_config,
    parse_config,
    save_config,
)
from .netcheck import build_proxies, get_windows_proxy, is_online
from .portal import DEFAULT_AC_IDS, DEFAULT_PORTAL, LoginResult, PortalClient, get_mac_address

__all__ = [
    "DEFAULT_AC_IDS",
    "DEFAULT_CONFIG_NAME",
    "DEFAULT_PORTAL",
    "PASSWORD_PREFIX",
    "ConfigError",
    "LoginResult",
    "PortalClient",
    "build_proxies",
    "decode_password",
    "default_config_path",
    "encode_password",
    "get_mac_address",
    "get_windows_proxy",
    "is_online",
    "load_config",
    "parse_config",
    "save_config",
]

__version__ = "1.0.0"
