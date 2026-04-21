from pathlib import Path
import xml.etree.ElementTree as ET


def test_dynamic_dense_world_contains_many_dynamic_obstacles():
    world_path = Path('src/sim_description/worlds/dynamic_obstacle_dense.sdf')
    assert world_path.exists()

    root = ET.fromstring(world_path.read_text(encoding='utf-8'))
    models = root.findall('.//world/model')
    moving = [model for model in models if model.attrib.get("name", "").startswith("moving_")]
    custom_plugins = root.findall(".//plugin[@filename='libMovingObstacle.so']")

    assert len(models) >= 12
    assert len(moving) >= 6
    assert len(custom_plugins) == 0
