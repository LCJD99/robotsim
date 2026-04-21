from pathlib import Path

import yaml


def test_bridge_topics_include_required_topics():
    config = yaml.safe_load(Path("src/sim_bringup/config/bridge_topics.yaml").read_text(encoding="utf-8"))

    topics = {bridge["ros_topic_name"] for bridge in config["bridges"]}

    assert topics >= {
        "/clock",
        "/cmd_vel",
        "/joint_states",
        "/tf",
        "/tf_static",
        "/scan",
        "/camera/image_raw",
    }
