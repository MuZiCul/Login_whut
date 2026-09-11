"""门户客户端单元测试：全部使用假 Session，不产生真实网络请求。"""

import pytest

from whut_login.portal import (
    DEFAULT_PORTAL,
    LoginResult,
    PortalClient,
    get_mac_address,
    is_success_response,
)


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.content = body.encode("utf-8")


class FakeSession:
    """按顺序返回预置响应，并记录每次调用参数。"""

    def __init__(self, bodies: list[str]) -> None:
        self._bodies = list(bodies)
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self._bodies:
            raise AssertionError("收到超出预期的请求")
        return FakeResponse(self._bodies.pop(0))


@pytest.fixture
def make_client():
    def _factory(bodies: list[str]) -> tuple[PortalClient, FakeSession]:
        session = FakeSession(bodies)
        client = PortalClient(session=session, timeout=1.0, proxies=None)
        return client, session

    return _factory


class TestGetMacAddress:
    def test_格式为六段大写十六进制(self):
        mac = get_mac_address()
        parts = mac.split("-")
        assert len(parts) == 6
        assert all(len(part) == 2 for part in parts)
        assert mac == mac.upper()

    def test_去掉分隔符后是十二位十六进制(self):
        raw = get_mac_address().replace("-", "")
        assert len(raw) == 12
        int(raw, 16)


class TestIsSuccessResponse:
    @pytest.mark.parametrize("body", ["login_ok", '{"result": "successful"}'])
    def test_成功标记(self, body):
        assert is_success_response(body) is True

    def test_失败响应(self):
        assert is_success_response('{"error":"login_error","error_msg":"账号或密码错误"}') is False


class TestBuildPayload:
    def test_关键字段(self, make_client):
        client, _ = make_client(["login_ok"])
        payload = client.build_payload("testuser", "s3cret", 5)
        assert payload["action"] == "login"
        assert payload["ajax"] == "1"
        assert payload["ac_id"] == "5"
        assert payload["save_me"] == "1"
        assert payload["username"] == "testuser"

    def test_密码按明文提交(self, make_client):
        client, _ = make_client(["login_ok"])
        payload = client.build_payload("testuser", "s3cret", 0)
        assert payload["password"] == "s3cret"

    def test_客户端不对密码做二次加工(self, make_client):
        """``{B}`` 前缀不再由客户端包装；传什么发什么。"""
        client, _ = make_client(["login_ok"])
        payload = client.build_payload("u", "{B}c2VjcmV0", 0)
        assert payload["password"] == "{B}c2VjcmV0"

    def test_user_mac_为真实地址字符串(self, make_client):
        """回归：上游漏写调用括号，发送的是 bound method 字符串。"""
        client, _ = make_client(["login_ok"])
        payload = client.build_payload("testuser", "s3cret", 0)
        assert isinstance(payload["user_mac"], str)
        assert "bound method" not in payload["user_mac"]
        assert len(payload["user_mac"].split("-")) == 6


class TestHeadersAndUrl:
    def test_认证地址(self, make_client):
        client, session = make_client(["login_ok"])
        client.login("u", "p", ac_id=0)
        assert session.calls[0][0] == f"{DEFAULT_PORTAL}/include/auth_action.php"

    def test_不再硬编码_content_length(self, make_client):
        client, session = make_client(["login_ok"])
        client.login("u", "p", ac_id=0)
        _, kwargs = session.calls[0]
        assert "Content-Length" not in kwargs["headers"]

    def test_携带_referer_与_origin(self, make_client):
        client, session = make_client(["login_ok"])
        client.login("u", "p", ac_id=0)
        _, kwargs = session.calls[0]
        assert kwargs["headers"]["Origin"] == DEFAULT_PORTAL
        assert kwargs["headers"]["Referer"].startswith(DEFAULT_PORTAL)

    def test_portal_尾部斜杠被去除(self):
        client = PortalClient("http://172.30.16.34/", session=FakeSession(["login_ok"]))
        assert client.auth_url == "http://172.30.16.34/include/auth_action.php"


class TestLogin:
    def test_指定_ac_id_只请求一次(self, make_client):
        client, session = make_client(["login_ok"])
        result = client.login("u", "p", ac_id=5)
        assert result.success is True
        assert result.ac_id == 5
        assert len(session.calls) == 1

    def test_自动模式逐个尝试候选_ac_id(self, make_client):
        client, session = make_client(['{"error":"login_error"}', "login_ok"])
        assert client.login("u", "p").success is True
        assert {call[1]["data"]["ac_id"] for call in session.calls} == {"0", "5"}

    def test_首次成功则不继续尝试(self, make_client):
        client, session = make_client(["login_ok", "login_ok"])
        assert client.login("u", "p").success is True
        assert len(session.calls) == 1

    def test_全部失败时返回最后一次结果(self, make_client):
        client, session = make_client(['{"error":"a"}', '{"error":"b"}'])
        result = client.login("u", "p")
        assert result.success is False
        assert len(session.calls) == 2
        assert result.response == '{"error":"b"}'

    def test_successful_标记同样视为成功(self, make_client):
        client, _ = make_client(["successful"])
        assert client.login("u", "p", ac_id=0).success is True

    def test_透传超时与代理(self, make_client):
        session = FakeSession(["login_ok"])
        proxies = {"http": "http://127.0.0.1:7890"}
        client = PortalClient(session=session, timeout=2.5, proxies=proxies)
        client.login("u", "p", ac_id=0)
        _, kwargs = session.calls[0]
        assert kwargs["timeout"] == 2.5
        assert kwargs["proxies"] == proxies


class TestLoginResult:
    def test_str_包含状态与_ac_id(self):
        assert "成功" in str(LoginResult(True, 5, "login_ok"))
        assert "失败" in str(LoginResult(False, 0, "error"))
