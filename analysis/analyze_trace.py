from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TRACE_FILES = {
    "window_observation": "window_observation.jsonl",
    "plan": "plan.jsonl",
    "outcome": "outcome.jsonl",
    "task_events": "task_events.jsonl",
    "resource_samples": "resource_samples.jsonl",
}


@dataclass
class TaskFlowStats:
    arrivals: int = 0
    planned: int = 0
    completed: int = 0



def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        return records
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records



def _window_sort_key(window_id: str) -> tuple[int, str]:
    if window_id.startswith("window-"):
        suffix = window_id.removeprefix("window-")
        if suffix.isdigit():
            return (int(suffix), window_id)
    return (10**12, window_id)


def _build_task_flow(trace_dir: Path) -> tuple[dict[str, TaskFlowStats], dict[str, int]]:
    task_events = _read_jsonl(trace_dir / TRACE_FILES["task_events"])
    plans = _read_jsonl(trace_dir / TRACE_FILES["plan"])
    outcomes = _read_jsonl(trace_dir / TRACE_FILES["outcome"])

    by_window: dict[str, TaskFlowStats] = defaultdict(TaskFlowStats)

    for rec in task_events:
        if rec.get("event_type") == "TASK_ARRIVAL":
            wid = str(rec.get("window_id", "unknown"))
            by_window[wid].arrivals += 1

    for rec in plans:
        wid = str(rec.get("window_id", "unknown"))
        actions = rec.get("task_actions", [])
        if isinstance(actions, list):
            by_window[wid].planned += len(actions)

    for rec in outcomes:
        wid = str(rec.get("window_id", "unknown"))
        completed = rec.get("completed_task_ids", [])
        if isinstance(completed, list):
            by_window[wid].completed += len(completed)

    totals = {
        "arrivals": sum(v.arrivals for v in by_window.values()),
        "planned": sum(v.planned for v in by_window.values()),
        "completed": sum(v.completed for v in by_window.values()),
        "window_count": len(by_window),
    }
    return dict(sorted(by_window.items(), key=lambda kv: _window_sort_key(kv[0]))), totals



def _find_anomalies(by_window: dict[str, TaskFlowStats]) -> list[str]:
    anomalies: list[str] = []
    for wid, s in by_window.items():
        if s.planned > s.arrivals:
            anomalies.append(
                f"{wid}: planned({s.planned}) > arrivals({s.arrivals})"
            )
        if s.completed > s.planned:
            anomalies.append(
                f"{wid}: completed({s.completed}) > planned({s.planned})"
            )
    return anomalies



def _render_report(
    trace_id: str,
    trace_dir: Path,
    by_window: dict[str, TaskFlowStats],
    totals: dict[str, int],
    anomalies: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"# Trace Task-Flow Report: {trace_id}")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- Trace path: `{trace_dir}`")
    lines.append("- Focus: TASK_ARRIVAL -> Plan task_actions -> Outcome completed_task_ids")
    lines.append("")

    lines.append("## Summary")
    lines.append(f"- Windows observed: **{totals['window_count']}**")
    lines.append(f"- Total arrivals: **{totals['arrivals']}**")
    lines.append(f"- Total planned: **{totals['planned']}**")
    lines.append(f"- Total completed: **{totals['completed']}**")
    if totals["arrivals"]:
        planning_ratio = totals["planned"] / totals["arrivals"]
        lines.append(f"- Planning/Arrival ratio: **{planning_ratio:.2f}**")
    if totals["planned"]:
        completion_ratio = totals["completed"] / totals["planned"]
        lines.append(f"- Completion/Planned ratio: **{completion_ratio:.2f}**")
    lines.append("")

    lines.append("## Window Breakdown (Top 120 by window order)")
    lines.append("| window_id | arrivals | planned | completed |")
    lines.append("|---|---:|---:|---:|")
    for idx, (wid, s) in enumerate(by_window.items()):
        if idx >= 120:
            break
        lines.append(f"| {wid} | {s.arrivals} | {s.planned} | {s.completed} |")
    lines.append("")

    lines.append("## Anomalies")
    if anomalies:
        for a in anomalies:
            lines.append(f"- {a}")
    else:
        lines.append("- None")
    lines.append("")

    return "\n".join(lines)



def analyze_trace(trace_root: Path, trace_id: str, out_dir: Path) -> Path:
    trace_dir = trace_root / trace_id
    if not trace_dir.exists() or not trace_dir.is_dir():
        raise FileNotFoundError(f"trace id not found: {trace_id}")

    missing = [name for name in TRACE_FILES.values() if not (trace_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"trace missing jsonl files: {', '.join(missing)}")

    by_window, totals = _build_task_flow(trace_dir)
    anomalies = _find_anomalies(by_window)
    content = _render_report(trace_id, trace_dir, by_window, totals, anomalies)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"report_{trace_id}.md"
    out_path.write_text(content, encoding="utf-8")
    return out_path



def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one trace id and output markdown report")
    parser.add_argument("trace_id", help="trace id directory name under traces/")
    parser.add_argument("--trace-root", default="traces", help="trace root directory")
    parser.add_argument("--out-dir", default="analysis", help="report output directory")
    args = parser.parse_args()

    out_path = analyze_trace(Path(args.trace_root), args.trace_id, Path(args.out_dir))
    print(out_path)


if __name__ == "__main__":
    main()
