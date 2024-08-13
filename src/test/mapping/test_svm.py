# Copyright (c) Hello Robot, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in the root directory
# of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# license information maybe found below, if so.

from stretch.agent import RobotAgent
from stretch.core import Parameters
from stretch.utils.config import Config
from stretch.utils.dummy_stretch_client import DummyStretchClient

SMALL_DATA_FILE = "hq_small.pkl"
LARGE_DATA_FILE = "hq_large.pkl"
TEST_PLANNER_FILENAME = "planner.yaml"


def _eval_svm(filename: str):

    print("==== SVM Evaluation ====")
    print(f"Loading voxel map from {filename}...")
    config = Config()
    config.merge_from_file(TEST_PLANNER_FILENAME)
    config.freeze()
    parameters = Parameters(**config)

    print("Create dummy robot and agent...")
    dummy_robot = DummyStretchClient()
    agent = RobotAgent(
        dummy_robot,
        parameters,
        semantic_sensor=None,
        rpc_stub=None,
        grasp_client=None,
        voxel_map=None,
        use_instance_memory=True,
    )
    voxel_map = agent.voxel_map

    print("Reading from pkl file of raw observations...")
    frame = -1
    semantic_sensor = None
    ok = voxel_map.read_from_pickle(filename, num_frames=frame, perception=semantic_sensor)

    print(f"Reading from pkl file of raw observations... {ok=}")
    assert ok, "Failed to read from pkl file of raw observations"


def test_svm_small():
    _eval_svm(SMALL_DATA_FILE)


def test_svm_large():
    _eval_svm(LARGE_DATA_FILE)


if __name__ == "__main__":
    test_svm_small()
    test_svm_large()
