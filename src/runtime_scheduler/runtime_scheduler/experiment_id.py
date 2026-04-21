from datetime import datetime


def make_experiment_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
