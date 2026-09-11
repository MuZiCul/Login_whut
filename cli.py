"""命令行入口：``python login_whut.py``。"""

from __future__ import annotations

import argparse
import getpass
import sys
import time
from pathlib import Path

import requests

from config import (
    DEFAULT_CONFIG_NAME,
    ConfigError,
    decode_password,
    default_config_path,
    load_config,
    save_config,
)
from netcheck import build_proxies, get_windows_proxy, is_online
from portal import DEFAULT_PORTAL, LoginResult, PortalClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="login_whut",
        description="武汉理工大学校园网自动登录（srun 门户）",
    )
    parser.add_argument("-u", "--username", help="账号；缺省时读取凭据文件，仍缺则交互输入")
    parser.add_argument(
        "-p", "--password", help="密码（明文或 {B}+base64）；缺省时读取凭据文件，仍缺则交互输入"
    )
    parser.add_argument("-c", "--config", help=f"凭据文件路径，默认 {DEFAULT_CONFIG_NAME}")
    parser.add_argument("--portal", default=DEFAULT_PORTAL, help=f"门户地址，默认 {DEFAULT_PORTAL}")
    parser.add_argument("--ac-id", type=int, help="指定 ac_id；缺省时依次尝试 0 与 5")
    parser.add_argument("--timeout", type=float, default=5.0, help="单次请求超时秒数，默认 5")

    proxy_group = parser.add_mutually_exclusive_group()
    proxy_group.add_argument("--proxy", help="HTTP 代理，如 127.0.0.1:7890")
    proxy_group.add_argument(
        "--no-proxy", action="store_true", help="禁用代理（默认会自动读取 Windows 系统代理）"
    )

    parser.add_argument("--retries", type=int, default=5, help="登录失败后的重试次数，默认 5；0 表示不限次数")
    parser.add_argument("--interval", type=float, default=10.0, help="重试间隔秒数，默认 10")
    parser.add_argument("--save-config", action="store_true", help="把本次凭据写入凭据文件")
    parser.add_argument("--init-config", action="store_true", help="交互式创建凭据文件后直接退出")
    parser.add_argument("--no-input", action="store_true", help="禁止交互输入，缺少凭据时直接失败")
    parser.add_argument("--check-only", action="store_true", help="仅检测网络连通性，不执行登录")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出调试信息")
    return parser


def resolve_config_path(args: argparse.Namespace) -> Path:
    """确定凭据文件路径。"""
    return Path(args.config) if args.config else default_config_path()


def resolve_proxies(args: argparse.Namespace) -> dict[str, str] | None:
    """确定要使用的代理；默认跟随 Windows 系统代理设置。"""
    if args.no_proxy:
        return None
    proxy = args.proxy or get_windows_proxy()
    if proxy and args.verbose:
        print(f"[代理] 使用 {proxy}")
    return build_proxies(proxy)


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str, bool]:
    """解析账号密码，返回 ``(账号, 明文密码, 是否来自交互输入)``。

    优先级：命令行参数 > 凭据文件 > 交互输入。
    """
    username = args.username
    password = args.password
    from_input = False

    if username is None or password is None:
        try:
            file_username, file_password = load_config(resolve_config_path(args))
        except ConfigError as exc:
            if args.verbose:
                print(f"[配置] {exc}")
        else:
            username = username if username is not None else file_username
            password = password if password is not None else file_password

    if username is None or password is None:
        if args.no_input:
            raise ConfigError("缺少账号或密码，且已禁用交互输入（--no-input）")
        print("未找到可用凭据，请手动输入账号密码。")
        username = username if username is not None else input("请输入账号：").strip()
        password = password if password is not None else getpass.getpass("请输入密码：")
        from_input = True

    return username, decode_password(password), from_input


def init_config(args: argparse.Namespace) -> int:
    """交互式创建凭据文件，返回进程退出码。"""
    if args.no_input and (args.username is None or args.password is None):
        print("错误：--init-config 依赖交互输入，不能与 --no-input 同时使用。", file=sys.stderr)
        return 1

    config_path = resolve_config_path(args)
    print(f"凭据将写入：{config_path}")
    username = args.username if args.username is not None else input("请输入账号：").strip()
    password = args.password if args.password is not None else getpass.getpass("请输入密码：")

    if not username or not password:
        print("错误：账号与密码都不能为空。", file=sys.stderr)
        return 1

    try:
        saved = save_config(config_path, username, decode_password(password))
    except OSError as exc:
        print(f"错误：凭据写入失败（{exc}）", file=sys.stderr)
        return 1

    print(f"凭据已写入 {saved}")
    print("提示：该文件与明文等价，请勿提交到版本库，并确保他人无法读取（可用 icacls 收紧权限，见 README）。")
    return 0


def run_login(
    args: argparse.Namespace,
    username: str,
    password: str,
    proxies: dict[str, str] | None,
) -> int:
    """带重试的登录流程，返回进程退出码。

    全程复用同一个客户端（即同一个连接池），避免每轮重试重建会话。
    """
    client: PortalClient = PortalClient(args.portal, timeout=args.timeout, proxies=proxies)
    attempt = 0
    while True:
        attempt += 1
        if args.verbose:
            print(f"[登录] 第 {attempt} 次尝试……")
        try:
            result: LoginResult | None = client.login(username, password, args.ac_id)
        except requests.RequestException as exc:
            result = None
            print(f"网络异常，请确认已连接校园网 Wi-Fi 或有线网络。（{exc}）")

        if result is not None:
            print(result)
            if result.success:
                return 0

        if args.retries and attempt > args.retries:
            print("已达到最大重试次数，登录失败。", file=sys.stderr)
            return 1
        print(f"{args.interval:g} 秒后重试……")
        time.sleep(args.interval)


def main(argv: list[str] | None = None) -> int:
    """程序主入口，返回进程退出码（0 成功 / 1 失败）。"""
    args = build_parser().parse_args(argv)

    if args.init_config:
        try:
            return init_config(args)
        except (KeyboardInterrupt, EOFError):
            print("\n已取消。", file=sys.stderr)
            return 1

    proxies = resolve_proxies(args)

    if is_online(timeout=args.timeout, proxies=proxies):
        print("网络已连接，无需登录。")
        return 0
    if args.check_only:
        print("网络未连接。")
        return 1

    try:
        username, password, from_input = resolve_credentials(args)
    except ConfigError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    config_path = resolve_config_path(args)
    if args.save_config or (from_input and not config_path.exists()):
        try:
            saved = save_config(config_path, username, password)
        except OSError as exc:
            print(f"警告：凭据保存失败（{exc}），本次继续登录。", file=sys.stderr)
        else:
            print(f"凭据已保存到 {saved}")

    try:
        return run_login(args, username, password, proxies)
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
