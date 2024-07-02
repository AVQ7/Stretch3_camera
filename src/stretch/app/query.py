# (c) 2024 Hello Robot by Chris Paxton
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import datetime
import sys
import time
import timeit
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import matplotlib.pyplot as plt
import numpy as np
import open3d
import torch
from PIL import Image

# Mapping and perception
import stretch.utils.depth as du
from stretch.agent.robot_agent import RobotAgent
from stretch.agent.zmq_client import HomeRobotZmqClient
from stretch.core import Parameters, RobotClient, get_parameters
from stretch.perception import create_semantic_sensor
from stretch.utils.dummy_stretch_client import DummyStretchClient


@click.command()
@click.option("--local", is_flag=True, help="Run code locally on the robot.")
@click.option("--recv_port", default=4401, help="Port to receive observations on")
@click.option("--send_port", default=4402, help="Port to send actions to on the robot")
@click.option("--robot_ip", default="192.168.1.15")
@click.option("--output-filename", default="stretch_output", type=str)
@click.option("--explore-iter", default=0)
@click.option("--spin", default=False, is_flag=True)
@click.option("--reset", is_flag=True)
@click.option(
    "--input_file", default="", type=str, help="Path to input file used instead of robot data"
)
@click.option(
    "--write-instance-images",
    default=False,
    is_flag=True,
    help="write out images of every object we found",
)
@click.option("--parameter-file", default="default_planner.yaml")
@click.option("--reset", is_flag=True, help="Reset the robot to origin before starting")
def main(
    device_id: int = 0,
    verbose: bool = True,
    parameter_file: str = "config/default_planner.yaml",
    local: bool = True,
    recv_port: int = 4401,
    send_port: int = 4402,
    robot_ip: str = "192.168.1.15",
    reset: bool = False,
    explore_iter: int = 0,
    output_filename: str = "stretch_output",
    spin: bool = False,
    write_instance_images: bool = False,
    input_file: str = "",
):

    print("- Load parameters")
    parameters = get_parameters(parameter_file)

    if len(input_file) == 0 or input_file is None:
        current_datetime = datetime.datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        output_pkl_filename = output_filename + "_" + formatted_datetime + ".pkl"

        robot = HomeRobotZmqClient(
            robot_ip=robot_ip,
            recv_port=recv_port,
            send_port=send_port,
            use_remote_computer=(not local),
            parameters=parameters,
        )
        _, semantic_sensor = create_semantic_sensor(
            device_id=device_id,
            verbose=verbose,
            category_map_file=parameters["open_vocab_category_map_file"],
        )
        demo = RobotAgent(robot, parameters, semantic_sensor)

        if reset:
            demo.move_closed_loop([0, 0, 0], max_time=60.0)

        if spin:
            demo.rotate_in_place(steps=8, visualize=False)

        if explore_iter > 0:
            raise NotImplementedError("Exploration not implemented yet")

        # Save out file
        if len(output_pkl_filename) > 0:
            print(f"Write pkl to {output_pkl_filename}...")
            demo.voxel_map.write_to_pickle(output_pkl_filename)

        # At the end...
        robot.stop()
    else:
        dummy_robot = DummyStretchClient()
        with input_path.open("rb") as f:
            loaded_voxel_map = pickle.load(f)
        agent = RobotAgent(
            dummy_robot,
            parameters,
            None,
            rpc_stub=None,
            grasp_client=None,
            voxel_map=loaded_voxel_map,
        )

    # Debugging: write out images of instances that you saw
    if write_instance_images:
        demo.save_instance_images(".")


if __name__ == "__main__":
    main()
