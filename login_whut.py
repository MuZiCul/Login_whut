#!/usr/bin/env python3
"""武汉理工大学校园网自动登录入口。

用法::

    python login_whut.py                 # 检测网络，未登录则自动登录
    python login_whut.py --check-only    # 仅检测网络连通性
    python login_whut.py --help          # 查看全部参数

依赖：仅 ``requests``（见 requirements.txt）。
"""

from whut_login.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
