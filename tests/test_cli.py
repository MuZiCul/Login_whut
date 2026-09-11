"""命令行入口测试：使用假客户端，不产生真实网络请求。"""

import json

import requests

from whut_login import cli
from whut_login.config import load_config
from whut_login.portal import LoginResult


class FakePortalClient:
    """替换 ``cli.PortalClient``：按调用顺序抛出异常 / 返回预置结果。"""

    def __init__(self, results, errors=None) -> None:
        self._results = list(results)
        self._errors = list(errors or [])
        self.calls: list[tuple[str, str, int | None]] = []

    def login(self, username, password, ac_id=None):
        self.calls.append((username, password, ac_id))
        if self._errors:
            error = self._errors.pop(0)
            if error is not None:
                raise error
        return self._results.pop(0)


def patch_client(monkeypatch, results, errors=None):
    """把 CLI 使用的客户端换成假实现，返回创建出的实例列表。"""
    created: list[FakePortalClient] = []

    def factory(*args, **kwargs):
        client = FakePortalClient(results, errors)
        created.append(client)
        return client

    monkeypatch.setattr(cli, "PortalClient", factory)
    return created


def patch_online(monkeypatch, online: bool) -> None:
    monkeypatch.setattr(cli, "is_online", lambda **kwargs: online)


def write_config(path, username="fileuser", password="filepwd"):
    path.write_text(json.dumps({"username": username, "password": password}), encoding="utf-8")


class TestCheckOnly:
    def test_已联网返回0(self, monkeypatch, capsys):
        patch_online(monkeypatch, True)
        assert cli.main(["--check-only"]) == 0
        assert "已连接" in capsys.readouterr().out

    def test_未联网返回1(self, monkeypatch):
        patch_online(monkeypatch, False)
        assert cli.main(["--check-only"]) == 1


class TestInitConfig:
    def test_用命令行参数创建配置文件(self, tmp_path):
        config = tmp_path / "config.json"
        assert cli.main(["--init-config", "-u", "testuser", "-p", "s3cret", "-c", str(config)]) == 0
        assert load_config(config) == ("testuser", "s3cret")

    def test_交互输入创建配置文件并去除账号空白(self, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        monkeypatch.setattr("builtins.input", lambda *args: " testuser ")
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: "s3cret")

        assert cli.main(["--init-config", "-c", str(config)]) == 0
        assert load_config(config) == ("testuser", "s3cret")

    def test_密码为空返回1且不落盘(self, tmp_path):
        config = tmp_path / "config.json"
        assert cli.main(["--init-config", "-u", "u", "-p", "", "-c", str(config)]) == 1
        assert not config.exists()

    def test_不能与_no_input_同时使用(self, tmp_path, capsys):
        config = tmp_path / "config.json"
        assert cli.main(["--init-config", "--no-input", "-c", str(config)]) == 1
        assert "不能与 --no-input" in capsys.readouterr().err

    def test_不触发网络检测(self, monkeypatch, tmp_path):
        def unexpected(**kwargs):
            raise AssertionError("--init-config 不应检测网络")

        monkeypatch.setattr(cli, "is_online", unexpected)
        config = tmp_path / "config.json"
        assert cli.main(["--init-config", "-u", "u", "-p", "p", "-c", str(config)]) == 0


class TestCredentials:
    def test_禁用交互输入且无凭据时返回1(self, monkeypatch, tmp_path, capsys):
        patch_online(monkeypatch, False)
        code = cli.main(["--no-input", "-c", str(tmp_path / "missing.json"), "--no-proxy"])
        assert code == 1
        assert "缺少账号或密码" in capsys.readouterr().err

    def test_命令行凭据优先于凭据文件(self, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        write_config(config)
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])

        assert cli.main(["-u", "cliuser", "-p", "clipwd", "-c", str(config), "--no-proxy"]) == 0
        assert created[0].calls[0][:2] == ("cliuser", "clipwd")

    def test_从凭据文件读取(self, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        write_config(config)
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 0, "login_ok")])

        assert cli.main(["-c", str(config), "--no-proxy"]) == 0
        assert created[0].calls[0][:2] == ("fileuser", "filepwd")

    def test_凭据文件中的_b_密码被还原(self, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        write_config(config, password="{B}c2VjcmV0")
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 0, "login_ok")])

        assert cli.main(["-c", str(config), "--no-proxy"]) == 0
        assert created[0].calls[0][1] == "secret"

    def test_凭据文件损坏时报错返回1(self, monkeypatch, tmp_path, capsys):
        config = tmp_path / "config.json"
        config.write_text("not json at all", encoding="utf-8")
        patch_online(monkeypatch, False)
        patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])
        monkeypatch.setattr("builtins.input", lambda *args: "u")
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: "p")

        assert cli.main(["-c", str(config), "--no-proxy", "-v"]) == 0
        assert "凭据文件不是合法的 JSON" in capsys.readouterr().out

    def test_交互输入后在凭据缺失时自动保存_json(self, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        patch_online(monkeypatch, False)
        patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])
        monkeypatch.setattr("builtins.input", lambda *args: "testuser")
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: "s3cret")

        assert cli.main(["-c", str(config), "--no-proxy"]) == 0
        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["username"] == "testuser"
        assert data["password"] == "s3cret"

    def test_save_config_显式保存命令行凭据(self, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        patch_online(monkeypatch, False)
        patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])

        args = ["-u", "u", "-p", "p", "-c", str(config), "--save-config", "--no-proxy"]
        assert cli.main(args) == 0
        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["username"] == "u"
        assert data["password"] == "p"


class TestRetry:
    def test_重试后成功返回0(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(
            monkeypatch,
            [LoginResult(False, 0, '{"error":"a"}'), LoginResult(True, 5, "login_ok")],
        )
        code = cli.main(
            ["-u", "u", "-p", "p", "-c", str(tmp_path / "c.json"), "--retries", "2", "--interval", "0", "--no-proxy"]
        )
        assert code == 0
        assert len(created[0].calls) == 2

    def test_超过重试次数返回1(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(False, 0, '{"error":"a"}')] * 3)
        code = cli.main(
            ["-u", "u", "-p", "p", "-c", str(tmp_path / "c.json"), "--retries", "1", "--interval", "0", "--no-proxy"]
        )
        assert code == 1
        assert len(created[0].calls) == 2

    def test_网络异常后继续重试(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(
            monkeypatch,
            [LoginResult(True, 5, "login_ok")],
            errors=[requests.ConnectionError("boom")],
        )
        code = cli.main(
            ["-u", "u", "-p", "p", "-c", str(tmp_path / "c.json"), "--retries", "2", "--interval", "0", "--no-proxy"]
        )
        assert code == 0
        assert len(created[0].calls) == 2

    def test_指定_ac_id_透传给客户端(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])
        cli.main(["-u", "u", "-p", "p", "-c", str(tmp_path / "c.json"), "--ac-id", "5", "--no-proxy"])
        assert created[0].calls[0][2] == 5
