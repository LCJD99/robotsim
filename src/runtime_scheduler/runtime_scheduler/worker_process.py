from __future__ import annotations


def run_worker_loop() -> None:
    value = 0
    while True:
        value = (value + 1) % 1_000_000


def main() -> None:
    run_worker_loop()


if __name__ == "__main__":
    main()
