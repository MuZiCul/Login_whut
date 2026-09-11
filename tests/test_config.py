"""凭据模块单元测试。"""

import base64

import pytest

from whut_login.config import (
    ConfigError,
    decode_password,
    default_config_path,
    encode_password,
    load_config,
    parse_config,
    save_config,
)


class TestEncodePassword:
    def test_明文编码为_b_前缀加_base64(self):
        assert encode_password("123456") == "{B}" + base64.b64encode(b"123456").decode("ascii")

    def test_编码幂等(self):
        once = encode_password("p@ss word")
        assert encode_password(once) == once

    def test_支持非_ascii_字符(self):
        assert decode_password(encode_password("密码123")) == "密码123"


class TestDecodePassword:
    def test_明文原样返回(self):
        assert decode_password("456") == "456"

    def test_还原_base64_密码(self):
        encoded = "{B}" + base64.b64encode("secret".encode("utf-8")).decode("ascii")
        assert decode_password(encoded) == "secret"

    def test_非法_base64_抛_config_error(self):
        with pytest.raises(ConfigError):
            decode_password("{B}not-base64!!")


class TestParseConfig:
    def test_解析两行(self):
        assert parse_config("123\n456\n") == ("123", "456")

    def test_忽略空行与_crlf(self):
        assert parse_config("\r\n123\r\n\r\n456\r\n") == ("123", "456")

    def test_base64_密码被还原为明文(self):
        text = "123\n{B}" + base64.b64encode(b"456").decode("ascii")
        assert parse_config(text) == ("123", "456")

    @pytest.mark.parametrize("text", ["", "\n", "123", "123\n\n"])
    def test_行数不足抛_config_error(self, text):
        with pytest.raises(ConfigError):
            parse_config(text)


class TestConfigFile:
    def test_保存后读取得到明文密码(self, tmp_path):
        path = tmp_path / "config.txt"
        save_config(path, "u1", "s3cret-pwd")
        assert load_config(path) == ("u1", "s3cret-pwd")

    def test_默认以_b_前缀_base64_保存(self, tmp_path):
        path = tmp_path / "config.txt"
        save_config(path, "u1", "p1")
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "u1"
        assert lines[1].startswith("{B}")

    def test_可保存为明文(self, tmp_path):
        path = tmp_path / "config.txt"
        save_config(path, "u1", "p1", encode=False)
        assert path.read_text(encoding="utf-8").splitlines()[1] == "p1"

    def test_读取不存在的文件抛_config_error(self, tmp_path):
        with pytest.raises(ConfigError):
            load_config(tmp_path / "missing.txt")

    def test_默认路径位于项目根目录(self):
        assert default_config_path().name == "config.txt"
