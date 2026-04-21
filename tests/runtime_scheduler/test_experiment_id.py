from runtime_scheduler.experiment_id import make_experiment_id


def test_make_experiment_id_shape():
    value = make_experiment_id()
    assert len(value) == 15
    assert value[8] == "-"
