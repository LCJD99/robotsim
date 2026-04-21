from __future__ import annotations

import sys
from pathlib import Path


def pytest_addoption(parser):
    parser.addini("pythonpath", "Additional import paths", type="pathlist")


def pytest_configure(config):
    root = Path(config.rootpath)
    for path in reversed(config.getini("pythonpath")):
        candidate = Path(str(path))
        resolved = candidate if candidate.is_absolute() else root / candidate
        sys.path.insert(0, str(resolved))
