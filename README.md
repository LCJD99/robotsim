# Runtime Scheduler

Run the baseline runtime experiment with:

```bash
python -m runtime_scheduler.main
```

The run writes traces under `traces/<YYYYMMDD-HHMMSS>/` and produces five JSONL files:

- `window_observation.jsonl`
- `plan.jsonl`
- `outcome.jsonl`
- `task_events.jsonl`
- `resource_samples.jsonl`
