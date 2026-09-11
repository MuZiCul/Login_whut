"""联网状态检测与 Windows 系统代理读取。"""

from __future__ import annotations

import sys

import requests

DEFAULT_PROBE_URL = "https://www.baidu.com/"
DEFAULT_TIMEOUT = 3.0

_WIN_INET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def get_windows_proxy() -> str | None:
    """读取 Windows「Internet 选项」中的代理，返回 ``host:port``。

    未开启代理、读取失败或非 Windows 平台时返回 ``None``。
    """
    if sys.platform != "win32":
        return None
    import winreg  # noqa: PLC0415 - winreg 仅 Windows 可用，延迟导入以便跨平台导入本模块

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_INET_SETTINGS) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return None
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except OSError:
        return None

    server = (server or "").strip()
    if not server or ":" not in server:
        # 上游脚本在这里会拼出 ":" 这样的无效代理，此处直接按「未配置」处理
        return None
    return server


def build_proxies(proxy: str | None) -> dict[str, str] | None:
    """把 ``host:port`` 或完整 URL 转成 requests 的 ``proxies`` 参数。"""
    if not proxy:
        return None
    url = proxy if "://" in proxy else f"http://{proxy}"
    return {"http": url, "https": url}


def is_online(
    probe_url: str = DEFAULT_PROBE_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    proxies: dict[str, str] | None = None,
    session: requests.Session | None = None,
) -> bool:
    """探测外网是否可达。

    使用 HTTPS 探针：未认证时门户通常会在明文 HTTP 层做劫持跳转，
    但 HTTPS 握手会被打断而抛错，因此比探测 HTTP 更不容易误判。
    """
    requester = session if session is not None else requests
    try:
        response = requester.get(probe_url, timeout=timeout, proxies=proxies)
    except requests.RequestException:
        return False
    return 200 <= response.status_code < 400
