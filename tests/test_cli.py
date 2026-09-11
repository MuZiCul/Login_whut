"""命令行入口测试：使用假客户端，不产生真实网络请求。"""

import requests

from whut_login import cli
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


class TestCheckOnly:
    def test_已联网返回0(self, monkeypatch, capsys):
        patch_online(monkeypatch, True)
        assert cli.main(["--check-only"]) == 0
        assert "已连接" in capsys.readouterr().out

    def test_未联网返回1(self, monkeypatch):
        patch_online(monkeypatch, False)
        assert cli.main(["--check-only"]) == 1


class TestCredentials:
    def test_禁用交互输入且无凭据时返回1(self, monkeypatch, tmp_path, capsys):
        patch_online(monkeypatch, False)
        code = cli.main(["--no-input", "-c", str(tmp_path / "missing.txt"), "--no-proxy"])
        assert code == 1
        assert "缺少账号或密码" in capsys.readouterr().err

    def test_命令行凭据优先于凭据文件(self, monkeypatch, tmp_path):
        config = tmp_path / "config.txt"
        config.write_text("fileuser\nfilepwd\n", encoding="utf-8")
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])

        assert cli.main(["-u", "cliuser", "-p", "clipwd", "-c", str(config), "--no-proxy"]) == 0
        assert created[0].calls[0][:2] == ("cliuser", "clipwd")

    def test_从凭据文件读取(self, monkeypatch, tmp_path):
        config = tmp_path / "config.txt"
        config.write_text("fileuser\nfilepwd\n", encoding="utf-8")
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 0, "login_ok")])

        assert cli.main(["-c", str(config), "--no-proxy"]) == 0
        assert created[0].calls[0][:2] == ("fileuser", "filepwd")

    def test_凭据文件中的_b_密码被还原(self, monkeypatch, tmp_path):
        config = tmp_path / "config.txt"
        config.write_text("fileuser\n{B}c2VjcmV0\n", encoding="utf-8")
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 0, "login_ok")])

        assert cli.main(["-c", str(config), "--no-proxy"]) == 0
        assert created[0].calls[0][1] == "secret"

    def test_交互输入后在凭据缺失时自动保存(self, monkeypatch, tmp_path):
        config = tmp_path / "config.txt"
        patch_online(monkeypatch, False)
        patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])
        monkeypatch.setattr("builtins.input", lambda *args: "testuser")
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: "s3cret")

        assert cli.main(["-c", str(config), "--no-proxy"]) == 0
        lines = config.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "testuser"
        assert lines[1].startswith("{B}")

    def test_save_config_显式保存命令行凭据(self, monkeypatch, tmp_path):
        config = tmp_path / "config.txt"
        patch_online(monkeypatch, False)
        patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])

        args = ["-u", "u", "-p", "p", "-c", str(config), "--save-config", "--no-proxy"]
        assert cli.main(args) == 0
        assert config.is_file()
        assert config.read_text(encoding="utf-8").startswith("u\n{B}")


class TestRetry:
    def test_重试后成功返回0(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(
            monkeypatch,
            [LoginResult(False, 0, '{"error":"a"}'), LoginResult(True, 5, "login_ok")],
        )
        code = cli.main(
            ["-u", "u", "-p", "p", "-c", str(tmp_path / "c.txt"), "--retries", "2", "--interval", "0", "--no-proxy"]
        )
        assert code == 0
        assert len(created[0].calls) == 2

    def test_超过重试次数返回1(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(False, 0, '{"error":"a"}')] * 3)
        code = cli.main(
            ["-u", "u", "-p", "p", "-c", str(tmp_path / "c.txt"), "--retries", "1", "--interval", "0", "--no-proxy"]
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
            ["-u", "u", "-p", "p", "-c", str(tmp_path / "c.txt"), "--retries", "2", "--interval", "0", "--no-proxy"]
        )
        assert code == 0
        assert len(created[0].calls) == 2

    def test_指定_ac_id_透传给客户端(self, monkeypatch, tmp_path):
        patch_online(monkeypatch, False)
        created = patch_client(monkeypatch, [LoginResult(True, 5, "login_ok")])
        cli.main(["-u", "u", "-p", "p", "-c", str(tmp_path / "c.txt"), "--ac-id", "5", "--no-proxy"])
        assert created[0].calls[0][2] == 5
