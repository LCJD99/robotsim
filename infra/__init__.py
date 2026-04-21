from __future__ import annotations

from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "infra"
if _SRC.is_dir():
    __path__.append(str(_SRC))
