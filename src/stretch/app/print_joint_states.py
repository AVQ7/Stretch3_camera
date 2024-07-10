#!/usr/bin/env python3

import time

import click
import cv2
import numpy as np

from stretch.agent.zmq_client import HomeRobotZmqClient
from stretch.core import Parameters, get_parameters
from stretch.motion import HelloStretchIdx


@click.command()
@click.option("--robot_ip", default="192.168.1.15", help="IP address of the robot")
@click.option(
    "--local",
    is_flag=True,
    help="Set if we are executing on the robot and not on a remote computer",
)
@click.option("--parameter_file", default="default_planner.yaml", help="Path to parameter file")
@click.option("-j", "--joint", default="", help="Joint to print")
def main(
    robot_ip: str = "192.168.1.15",
    local: bool = False,
    parameter_file: str = "config/default_planner.yaml",
    joint: str = "",
):
    # Create robot
    parameters = get_parameters(parameter_file)
    robot = HomeRobotZmqClient(
        robot_ip=robot_ip,
        use_remote_computer=(not local),
        parameters=parameters,
    )
    robot.start()
    try:
        while True:
            joint_state = robot.get_joint_state()
            if joint_state is None:
                continue
            if len(joint) > 0:
                print(f"{joint}: {joint_state[HelloStretchIdx.get_idx(joint.lower())]}")
            else:
                print(
                    f"Arm: {joint_state[HelloStretchIdx.ARM]}, Lift: {joint_state[HelloStretchIdx.LIFT]}, Gripper: {joint_state[HelloStretchIdx.GRIPPER]}"
                )
            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    robot.stop()


if __name__ == "__main__":
    main()
