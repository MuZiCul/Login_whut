"""凭据模块单元测试。"""

import base64
import json
from pathlib import Path

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
    def test_解析_json_对象(self):
        assert parse_config('{"username": "123", "password": "456"}') == ("123", "456")

    def test_密码支持_b_前缀_base64(self):
        encoded = "{B}" + base64.b64encode(b"456").decode("ascii")
        text = json.dumps({"username": "123", "password": encoded})
        assert parse_config(text) == ("123", "456")

    def test_支持中文(self):
        text = json.dumps({"username": "学号", "password": "密码123"}, ensure_ascii=False)
        assert parse_config(text) == ("学号", "密码123")

    def test_账号两侧空白被去除(self):
        assert parse_config('{"username": " 123 ", "password": "456"}') == ("123", "456")

    def test_密码保留原始空白(self):
        assert parse_config('{"username": "1", "password": " 456 "}') == ("1", " 456 ")

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "not json",
            "[1, 2]",
            '"just a string"',
            "{}",
            '{"username": "1"}',
            '{"password": "2"}',
            '{"username": "", "password": "2"}',
            '{"username": "   ", "password": "2"}',
            '{"username": "1", "password": ""}',
            '{"username": 1, "password": "2"}',
            '{"username": "1", "password": 2}',
            '{"username": null, "password": "2"}',
        ],
    )
    def test_非法内容抛_config_error(self, text):
        with pytest.raises(ConfigError):
            parse_config(text)

    def test_非法_base64_密码抛_config_error(self):
        with pytest.raises(ConfigError):
            parse_config('{"username": "1", "password": "{B}not-base64!!"}')


class TestConfigFile:
    def test_保存后读取得到明文密码(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(path, "u1", "s3cret-pwd")
        assert load_config(path) == ("u1", "s3cret-pwd")

    def test_默认保存明文密码(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(path, "u1", "p1")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["username"] == "u1"
        assert data["password"] == "p1"

    def test_可选保存_b_前缀_base64_密码(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(path, "u1", "p1", encode=True)
        assert json.loads(path.read_text(encoding="utf-8"))["password"].startswith("{B}")

    def test_中文密码往返(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(path, "u1", "密码123")
        assert load_config(path) == ("u1", "密码123")

    def test_自动创建父目录(self, tmp_path):
        path = tmp_path / "nested" / "config.json"
        save_config(path, "u1", "p1")
        assert path.is_file()

    def test_读取不存在的文件抛_config_error(self, tmp_path):
        with pytest.raises(ConfigError):
            load_config(tmp_path / "missing.json")

    def test_读取非_utf8_文件抛_config_error(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_bytes(b"\xff\xfe\x00{}")
        with pytest.raises(ConfigError):
            load_config(path)

    def test_默认路径为项目根目录下的_config_json(self):
        path = default_config_path()
        assert path.name == "config.json"
        assert path.parent == Path(__file__).resolve().parent.parent
