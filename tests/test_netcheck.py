"""联网检测与代理处理单元测试。"""

import sys

import pytest
import requests

from whut_login.netcheck import build_proxies, get_windows_proxy, is_online


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class TestIsOnline:
    @pytest.mark.parametrize("status", [200, 204, 302])
    def test_2xx_与_3xx_视为已联网(self, status):
        assert is_online(session=FakeSession(response=FakeResponse(status))) is True

    @pytest.mark.parametrize("status", [403, 404, 500])
    def test_4xx_与_5xx_视为未联网(self, status):
        assert is_online(session=FakeSession(response=FakeResponse(status))) is False

    def test_请求异常视为未联网(self):
        session = FakeSession(error=requests.ConnectionError("boom"))
        assert is_online(session=session) is False

    def test_透传超时与代理参数(self):
        session = FakeSession(response=FakeResponse(200))
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        is_online(timeout=1.5, proxies=proxies, session=session)
        _, kwargs = session.calls[0]
        assert kwargs["timeout"] == 1.5
        assert kwargs["proxies"] == proxies


class TestBuildProxies:
    @pytest.mark.parametrize("value", [None, ""])
    def test_空值返回_none(self, value):
        assert build_proxies(value) is None

    def test_host_port_自动补全_scheme(self):
        assert build_proxies("127.0.0.1:7890") == {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890",
        }

    def test_保留已有_scheme(self):
        assert build_proxies("http://127.0.0.1:7890")["https"] == "http://127.0.0.1:7890"
        assert build_proxies("socks5://127.0.0.1:1080")["http"] == "socks5://127.0.0.1:1080"


class TestGetWindowsProxy:
    def test_非_windows_平台返回_none(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert get_windows_proxy() is None
