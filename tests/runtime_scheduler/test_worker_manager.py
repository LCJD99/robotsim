from runtime_scheduler.worker_manager import WorkerManager


def test_ensure_workers_creates_pid_map_for_multiple_tasks() -> None:
    next_pid = 1000
    spawned = []
    attached = []

    def spawn_fn(task_id: str) -> int:
        nonlocal next_pid
        next_pid += 1
        spawned.append(task_id)
        return next_pid

    def attach_fn(pid: int) -> None:
        attached.append(pid)

    manager = WorkerManager(spawn_fn=spawn_fn, attach_fn=attach_fn)

    manager.ensure_workers(["task_a", "task_b"])

    assert manager.get_pid("task_a") == 1001
    assert manager.get_pid("task_b") == 1002
    assert spawned == ["task_a", "task_b"]
    assert attached == [1001, 1002]


def test_resume_and_stop_known_task_return_true() -> None:
    resumed = []
    stopped = []

    def spawn_fn(task_id: str) -> int:
        return 2001

    def resume_fn(pid: int) -> bool:
        resumed.append(pid)
        return True

    def stop_fn(pid: int) -> bool:
        stopped.append(pid)
        return True

    manager = WorkerManager(
        spawn_fn=spawn_fn,
        resume_fn=resume_fn,
        stop_fn=stop_fn,
    )
    manager.ensure_workers(["task_a"])

    assert manager.resume_task("task_a") is True
    assert manager.stop_task("task_a") is True
    assert resumed == [2001]
    assert stopped == [2001]


def test_resume_and_stop_unknown_task_return_false() -> None:
    manager = WorkerManager(
        spawn_fn=lambda _task_id: 3001,
        resume_fn=lambda _pid: True,
        stop_fn=lambda _pid: True,
    )

    assert manager.resume_task("missing") is False
    assert manager.stop_task("missing") is False
