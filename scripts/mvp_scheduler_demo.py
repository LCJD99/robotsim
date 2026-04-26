from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SCHEDULER_SRC = REPO_ROOT / "src" / "runtime_scheduler"
if str(RUNTIME_SCHEDULER_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SCHEDULER_SRC))

from runtime_scheduler.scheduler_api.simple_scheduler import run_mvp_once


def main() -> None:
    result = run_mvp_once(output_root="traces")
    print(f"experiment_id={result.experiment_id}")
    print(f"result_file={result.output_path}")


if __name__ == "__main__":
    main()
