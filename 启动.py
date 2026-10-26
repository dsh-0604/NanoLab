# -*- coding: utf-8 -*-
"""NanoCode 电子实验室 —— 启动入口（供 exe 调用的纯 Python 版本）

用法：
    python 启动.py
如果当前 Python 没装 PySide6，会以退出码 2 结束，启动器会自动换一个解释器再试。
"""

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

try:
    import PySide6  # noqa: F401
except Exception:
    sys.stderr.write("当前 Python 没有 PySide6，换一个解释器\n")
    sys.exit(2)

from nanolab.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
