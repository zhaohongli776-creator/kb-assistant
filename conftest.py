"""pytest 引导：保证 `import repo` / `import main` 在任意工作目录下都成立。

为什么需要：pytest 默认的 prepend 导入模式只把**测试文件所在目录**塞进 sys.path。
从 `D:\`、`D:\kb-assistant\tests\` 里跑 pytest 时仓库根不在路径上，
`from repo import ...` 就会 ModuleNotFoundError。

与 pyproject.toml 的 `pythonpath = ["."]` 互补：老版本 pytest（7.0 之前不认
pythonpath）也靠这个文件兜底，且 conftest 本身会被 pytest 自动收集。

注意：**用 `python tests/test_repo.py` 直接跑测试文件不在此列**——那压根不经过
pytest，sys.path[0] 是 `tests\`。测试的唯一入口是：
    python -m pytest
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
