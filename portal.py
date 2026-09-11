"""srun 门户认证客户端（武汉理工大学校园网）。"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

import requests

DEFAULT_PORTAL = "http://172.30.16.34"
AUTH_PATH = "/include/auth_action.php"
REFERER_PATH = "/srun_portal_pc.php?ac_id=5&url=1.1.1.1"

#: ac_id 会随校区 / 接入设备变化，缺省时逐个尝试这些候选值
DEFAULT_AC_IDS: tuple[int, ...] = (0, 5)

#: 门户返回成功时会包含其中一个标记
SUCCESS_MARKERS = ("login_ok", "successful")

USER_AGENT = (
    "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 10.0; WOW64; Trident/7.0; "
    ".NET4.0C; .NET4.0E; .NET CLR 2.0.50727; .NET CLR 3.0.30729; "
    ".NET CLR 3.5.30729; Tablet PC 2.0)"
)


def get_mac_address() -> str:
    """返回本机 MAC 地址，格式 ``AA-BB-CC-DD-EE-FF``。"""
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return "-".join(mac[index:index + 2] for index in range(0, 12, 2)).upper()


def is_success_response(body: str) -> bool:
    """判断门户响应体是否表示登录成功。"""
    return any(marker in body for marker in SUCCESS_MARKERS)


@dataclass(frozen=True)
class LoginResult:
    """一次认证尝试的结果。"""

    success: bool
    ac_id: int
    response: str

    def __str__(self) -> str:
        state = "成功" if self.success else "失败"
        return f"登录{state}（ac_id={self.ac_id}）：{self.response}"


class PortalClient:
    """校园网 srun 门户的薄封装，所有网络交互都经由此类。"""

    def __init__(
        self,
        portal: str = DEFAULT_PORTAL,
        *,
        timeout: float = 5.0,
        proxies: dict[str, str] | None = None,
        session: requests.Session | None = None,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.portal = portal.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies
        self.session = session if session is not None else requests.Session()
        self.user_agent = user_agent

    @property
    def auth_url(self) -> str:
        return f"{self.portal}{AUTH_PATH}"

    def build_headers(self) -> dict[str, str]:
        """构造认证请求头。

        不再手工设置 ``Content-Length``，交给 requests 依据实际表单计算。
        """
        return {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN",
            "Cache-Control": "no-cache",
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": self.portal,
            "Referer": f"{self.portal}{REFERER_PATH}",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": self.user_agent,
        }

    def build_payload(self, username: str, password: str, ac_id: int) -> dict[str, str]:
        """构造认证表单。

        密码按**明文**提交：老版 srun 门户同样接受明文（``{B}`` + base64 也被接受，
        若配置里是那种写法，读取时已还原为明文）。MAC 取本机真实值。
        """
        return {
            "action": "login",
            "ajax": "1",
            "ac_id": str(ac_id),
            "nas_ip": "",
            "username": username,
            "password": password,
            "save_me": "1",
            "user_ip": "",
            "user_mac": get_mac_address(),
        }

    def authenticate(self, username: str, password: str, ac_id: int) -> LoginResult:
        """使用指定 ``ac_id`` 发起一次认证。"""
        response = self.session.post(
            self.auth_url,
            headers=self.build_headers(),
            data=self.build_payload(username, password, ac_id),
            timeout=self.timeout,
            proxies=self.proxies,
        )
        body = response.content.decode("utf-8", errors="replace")
        return LoginResult(is_success_response(body), ac_id, body)

    def login(self, username: str, password: str, ac_id: int | None = None) -> LoginResult:
        """登录校园网。

        ``ac_id`` 为 ``None`` 时，按随机顺序逐个尝试 :data:`DEFAULT_AC_IDS`，
        任一成功即返回；全部失败时返回最后一次的结果。
        """
        if ac_id is not None:
            candidates = [ac_id]
        else:
            candidates = random.sample(DEFAULT_AC_IDS, len(DEFAULT_AC_IDS))

        result = self.authenticate(username, password, candidates[0])
        for candidate in candidates[1:]:
            if result.success:
                break
            result = self.authenticate(username, password, candidate)
        return result
