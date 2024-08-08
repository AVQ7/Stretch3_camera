# # Copyright (c) Hello Robot, Inc.
# #
# # This source code is licensed under the APACHE 2.0 license found in the
# # LICENSE file in the root directory of this source tree.
# #
# # Some code may be adapted from other open-source works with their respective licenses. Original
# # licence information maybe found below, if so.
#

# Copyright (c) Hello Robot, Inc.
#
# This source code is licensed under the APACHE 2.0 license found in the
# LICENSE file in the root directory of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# licence information maybe found below, if so.


#!/usr/bin/env python3

from stretch.agent.operations import (
    AvertGazeOperation,
    NodHeadOperation,
    ShakeHeadOperation,
    WaveOperation,
)
from stretch.agent.robot_agent import RobotAgent
from stretch.agent.task.emote import EmoteManager
from stretch.agent.zmq_client import HomeRobotZmqClient
from stretch.core import get_parameters


def main(
    robot_ip: str = "",
    local: bool = False,
    parameter_file: str = "default_planner.yaml",
):
    # Create robot client
    parameters = get_parameters(parameter_file)
    robot = HomeRobotZmqClient(
        robot_ip=robot_ip,
        use_remote_computer=(not local),
        parameters=parameters,
    )

    robot.move_to_nav_posture()

    # create robot agent
    demo = RobotAgent(robot, parameters=parameters)

    # create task manager
    manager = EmoteManager(demo)
    task = manager.get_task(NodHeadOperation("emote", manager))

    # run task
    task.run()

    task = manager.get_task(ShakeHeadOperation("emote", manager))

    task.run()

    task = manager.get_task(WaveOperation("emote", manager))

    task.run()

    task = manager.get_task(AvertGazeOperation("emote", manager))

    task.run()


if __name__ == "__main__":
    main()
