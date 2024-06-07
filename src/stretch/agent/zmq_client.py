# (c) 2024 chris paxton under MIT license

import threading
import time
import timeit
from threading import Lock
from typing import List, Optional

import click
import cv2
import numpy as np
import zmq
from loguru import logger

from stretch.core.interfaces import ContinuousNavigationAction, Observations
from stretch.core.parameters import Parameters
from stretch.core.robot import RobotClient
from stretch.motion import PlanResult, RobotModel
from stretch.motion.kinematics import HelloStretchIdx, HelloStretchKinematics
from stretch.utils.geometry import angle_difference
from stretch.utils.image import Camera
from stretch.utils.point_cloud import show_point_cloud

# TODO: debug code - remove later if necessary
# import faulthandler
# faulthandler.enable()


class HomeRobotZmqClient(RobotClient):
    def _create_recv_socket(
        self,
        port: int,
        robot_ip: str,
        use_remote_computer: bool,
        message_type: Optional[str] = "observations",
    ):
        # Receive state information
        recv_socket = self.context.socket(zmq.SUB)
        recv_socket.setsockopt(zmq.SUBSCRIBE, b"")
        recv_socket.setsockopt(zmq.SNDHWM, 1)
        recv_socket.setsockopt(zmq.RCVHWM, 1)
        recv_socket.setsockopt(zmq.CONFLATE, 1)

        # Use remote computer or whatever
        if use_remote_computer:
            recv_address = "tcp://" + robot_ip + ":" + str(port)
        else:
            recv_address = "tcp://" + "127.0.0.1" + ":" + str(port)

        print(f"Connecting to {recv_address} to receive {message_type}...")
        recv_socket.connect(recv_address)
        return recv_socket

    def __init__(
        self,
        robot_ip: str = "192.168.1.15",
        recv_port: int = 4401,
        send_port: int = 4402,
        recv_state_port: int = 4403,
        recv_servo_port: int = 4404,
        parameters: Parameters = None,
        use_remote_computer: bool = True,
        urdf_path: str = "",
        ik_type: str = "pinocchio",
        visualize_ik: bool = False,
        grasp_frame: Optional[str] = None,
        ee_link_name: Optional[str] = None,
        manip_mode_controlled_joints: Optional[List[str]] = None,
    ):
        """
        Create a client to communicate with the robot over ZMQ.

        Args:
            robot_ip: The IP address of the robot
            recv_port: The port to receive observations on
            send_port: The port to send actions to on the robot
            use_remote_computer: Whether to use a remote computer to connect to the robot
            urdf_path: The path to the URDF file for the robot
            ik_type: The type of IK solver to use
            visualize_ik: Whether to visualize the IK solution
            grasp_frame: The frame to use for grasping
            ee_link_name: The name of the end effector link
            manip_mode_controlled_joints: The joints to control in manipulation mode
        """
        self.recv_port = recv_port
        self.send_port = send_port
        self.reset()

        # Variables we set here should not change
        self._iter = 0  # Tracks number of actions set, never reset this
        self._seq_id = 0  # Number of messages we received

        self._parameters = parameters
        self._moving_threshold = parameters["motion"]["moving_threshold"]
        self._angle_threshold = parameters["motion"]["angle_threshold"]
        self._min_steps_not_moving = parameters["motion"]["min_steps_not_moving"]

        # Robot model
        self._robot_model = HelloStretchKinematics(
            urdf_path=urdf_path,
            ik_type=ik_type,
            visualize=visualize_ik,
            grasp_frame=grasp_frame,
            ee_link_name=ee_link_name,
            manip_mode_controlled_joints=manip_mode_controlled_joints,
        )

        # Create ZMQ sockets
        self.context = zmq.Context()

        print("-------- HOME-ROBOT ROS2 ZMQ CLIENT --------")
        self.recv_socket = self._create_recv_socket(
            self.recv_port, robot_ip, use_remote_computer, message_type="observations"
        )
        self.recv_state_socket = self._create_recv_socket(
            recv_state_port, robot_ip, use_remote_computer, message_type="low level state"
        )
        self.recv_servo_socket = self._create_recv_socket(
            recv_servo_port, robot_ip, use_remote_computer, message_type="visual servoing data"
        )

        # SEnd actions back to the robot for execution
        self.send_socket = self.context.socket(zmq.PUB)
        self.send_socket.setsockopt(zmq.SNDHWM, 1)
        self.send_socket.setsockopt(zmq.RCVHWM, 1)
        action_send_address = "tcp://*:" + str(self.send_port)

        # Use remote computer or whatever
        if use_remote_computer:
            self.send_address = "tcp://" + robot_ip + ":" + str(self.send_port)
        else:
            self.send_address = "tcp://" + "127.0.0.1" + ":" + str(self.send_port)

        print(f"Connecting to {self.send_address} to send action messages...")
        self.send_socket.connect(self.send_address)
        print("...connected.")

        self._obs_lock = Lock()
        self._act_lock = Lock()

    def get_base_pose(self) -> np.ndarray:
        """Get the current pose of the base"""
        with self._obs_lock:
            t0 = timeit.default_timer()
            while self._obs is None:
                time.sleep(0.01)
                if timeit.default_timer() - t0 > 5.0:
                    logger.error("Timeout waiting for observation")
                    return None
            gps = self._obs["gps"]
            compass = self._obs["compass"]
        return np.concatenate([gps, compass], axis=-1)

    def arm_to(self, joint_angles: np.ndarray, blocking: bool = False):
        """Move the arm to a particular joint configuration.

        Args:
            joint_angles: 6 or Nx6 array of the joint angles to move to
            blocking: Whether to block until the motion is complete
        """
        if isinstance(joint_angles, list):
            joint_angles = np.array(joint_angles)
        if len(joint_angles) > 6:
            print(
                "[WARNING] arm_to: attempting to convert from full robot state to 6dof manipulation state."
            )
            # arm_cmd = self.robot_model.config_to_manip_command(joint_state)
            joint_angles = self._robot_model.config_to_manip_command(joint_angles)
        if len(joint_angles) < 6:
            raise ValueError(
                "joint_angles must be 6 dimensional: base_x, lift, arm, wrist roll, wrist pitch, wrist yaw"
            )
        assert (
            len(joint_angles) == 6
        ), "joint angles must be 6 dimensional: base_x, lift, arm, wrist roll, wrist pitch, wrist yaw"
        with self._act_lock:
            self._next_action["joint"] = joint_angles
            self._next_action["manip_blocking"] = blocking

        # Blocking is handled in here
        self.send_action()

    def navigate_to(
        self, xyt: ContinuousNavigationAction, relative=False, blocking=False, timeout: float = 10.0
    ):
        """Move to xyt in global coordinates or relative coordinates."""
        if isinstance(xyt, ContinuousNavigationAction):
            xyt = xyt.xyt
        assert len(xyt) == 3, "xyt must be a vector of size 3"
        with self._act_lock:
            self._next_action["xyt"] = xyt
            self._next_action["nav_relative"] = relative
            self._next_action["nav_blocking"] = blocking
        self.send_action(timeout=timeout)

    def reset(self):
        """Reset everything in the robot's internal state"""
        self._control_mode = None
        self._next_action = dict()
        self._obs = None
        self._thread = None
        self._finish = False
        self._last_step = -1

    def open_gripper(self, blocking: bool = True):
        """Open the gripper based on hard-coded presets."""
        gripper_target = self._robot_model.GRIPPER_OPEN
        print("Opening gripper to", gripper_target)
        self.gripper_to(gripper_target, blocking)

    def close_gripper(self, blocking: bool = True):
        """Close the gripper based on hard-coded presets."""
        gripper_target = self._robot_model.GRIPPER_CLOSED
        print("Closing gripper to", gripper_target)
        self.gripper_to(gripper_target, blocking)

    def gripper_to(self, target: float, blocking: bool = True):
        """Send the gripper to a target position."""
        with self._act_lock:
            self._next_action["gripper"] = target
            self._next_action["gripper_blocking"] = blocking
        self.send_action()
        if blocking:
            time.sleep(2.0)

    def switch_to_navigation_mode(self):
        """Velocity control of the robot base."""
        with self._act_lock:
            self._next_action["control_mode"] = "navigation"
        self.send_action()
        self._wait_for_mode("navigation")

    def in_navigation_mode(self) -> bool:
        """Returns true if we are navigating (robot head forward, velocity control on)"""
        return self._control_mode == "navigation"

    def in_manipulation_mode(self) -> bool:
        return self._control_mode == "manipulation"

    def switch_to_manipulation_mode(self):
        with self._act_lock:
            self._next_action["control_mode"] = "manipulation"
        self.send_action()
        self._wait_for_mode("manipulation")

    def move_to_nav_posture(self):
        with self._act_lock:
            self._next_action["posture"] = "navigation"
        self.send_action()
        self._wait_for_mode("navigation")

    def move_to_manip_posture(self):
        with self._act_lock:
            self._next_action["posture"] = "manipulation"
        self.send_action()
        self._wait_for_mode("manipulation")

    def _wait_for_mode(self, mode, verbose: bool = False, timeout: float = 10.0):
        t0 = timeit.default_timer()
        while True:
            with self._obs_lock:
                if verbose:
                    print(f"Waiting for mode {mode} current mode {self._control_mode}")
                if self._control_mode == mode:
                    break
            time.sleep(0.1)
            t1 = timeit.default_timer()
            if t1 - t0 > timeout:
                raise RuntimeError(f"Timeout waiting for mode {mode}: {t1 - t0} seconds")

    def _wait_for_action(
        self,
        block_id: int,
        verbose: bool = True,
        timeout: float = 10.0,
        moving_threshold: Optional[float] = None,
        angle_threshold: Optional[float] = None,
        min_steps_not_moving: Optional[int] = 1,
        goal_angle: Optional[float] = None,
    ):
        t0 = timeit.default_timer()
        last_pos = None
        last_ang = None
        not_moving_count = 0
        if moving_threshold is None:
            moving_threshold = self._moving_threshold
        if angle_threshold is None:
            angle_threshold = self._angle_threshold
        if min_steps_not_moving is None:
            min_steps_not_moving = self._min_steps_not_moving
        print("=" * 20, f"Waiting for {block_id} at goal", "=" * 20)
        while True:
            with self._obs_lock:
                if self._obs is not None:
                    pos = self._obs["gps"]
                    ang = self._obs["compass"][0]
                    moved_dist = np.linalg.norm(pos - last_pos) if last_pos is not None else 0
                    angle_dist = angle_difference(ang, last_ang) if last_ang is not None else 0
                    if goal_angle is not None:
                        angle_dist_to_goal = angle_difference(ang, goal_angle)
                    not_moving = (
                        last_pos is not None
                        and moved_dist < moving_threshold
                        and angle_dist < angle_threshold
                    )
                    if not_moving:
                        not_moving_count += 1
                    else:
                        not_moving_count = 0
                    last_pos = pos
                    last_ang = ang
                    if verbose:
                        print(
                            f"Waiting for step={block_id} {self._last_step} prev={self._last_step} at {pos} moved {moved_dist:0.04f} angle {angle_dist:0.04f} not_moving {not_moving_count} at_goal {self._obs['at_goal']}"
                        )
                        if goal_angle is not None:
                            print(
                                f"Goal angle {goal_angle} angle dist to goal {angle_dist_to_goal}"
                            )
                    if (
                        self._last_step >= block_id
                        and self._obs["at_goal"]
                        and not_moving_count > min_steps_not_moving
                    ):
                        break
                    self._obs = None
            time.sleep(0.01)
            t1 = timeit.default_timer()
            if t1 - t0 > timeout:
                raise RuntimeError(f"Timeout waiting for block with step id = {block_id}")

    def in_manipulation_mode(self) -> bool:
        """is the robot ready to grasp"""
        return self._control_mode == "manipulation"

    def in_navigation_mode(self) -> bool:
        """Is the robot to move around"""
        return self._control_mode == "navigation"

    def last_motion_failed(self) -> bool:
        """Override this if you want to check to see if a particular motion failed, e.g. it was not reachable and we don't know why."""
        return False

    def get_robot_model(self) -> RobotModel:
        """return a model of the robot for planning"""
        return self._robot_model

    def _update_obs(self, obs):
        """Update observation internally with lock"""
        with self._obs_lock:
            self._obs = obs
            self._control_mode = obs["control_mode"]
            self._last_step = obs["step"]
            if self._iter <= 0:
                self._iter = self._last_step

    def get_observation(self):
        """Get the current observation"""
        with self._obs_lock:
            if self._obs is None:
                return None
            observation = Observations(
                gps=self._obs["gps"],
                compass=self._obs["compass"],
                rgb=self._obs["rgb"],
                depth=self._obs["depth"],
                xyz=self._obs["xyz"],
            )
            observation.joint = self._obs.get("joint", None)
            observation.ee_pose = self._obs.get("ee_pose", None)
            observation.camera_K = self._obs.get("camera_K", None)
            observation.camera_pose = self._obs.get("camera_pose", None)
            observation.seq_id = self._seq_id
        return observation

    def execute_trajectory(
        self,
        trajectory: List[np.ndarray],
        pos_err_threshold: float = 0.2,
        rot_err_threshold: float = 0.75,
        spin_rate: int = 10,
        verbose: bool = False,
        per_waypoint_timeout: float = 10.0,
        final_timeout: float = 10.0,
        relative: bool = False,
    ):
        """Execute a multi-step trajectory; this is always blocking since it waits to reach each one in turn."""

        if isinstance(trajectory, PlanResult):
            trajectory = [pt.state for pt in trajectory.trajectory]

        for i, pt in enumerate(trajectory):
            assert (
                len(pt) == 3 or len(pt) == 2
            ), "base trajectory needs to be 2-3 dimensions: x, y, and (optionally) theta"
            # just_xy = len(pt) == 2
            # self.navigate_to(pt, relative, position_only=just_xy, blocking=False)
            self.navigate_to(pt, relative, blocking=False)
            self.wait_for_waypoint(
                pt,
                pos_err_threshold=pos_err_threshold,
                rot_err_threshold=rot_err_threshold,
                rate=spin_rate,
                verbose=verbose,
                timeout=per_waypoint_timeout,
            )
        self.navigate_to(pt, blocking=True, timeout=final_timeout)

    def wait_for_waypoint(
        self,
        xyt: np.ndarray,
        rate: int = 10,
        pos_err_threshold: float = 0.2,
        rot_err_threshold: float = 0.75,
        verbose: bool = False,
        timeout: float = 10.0,
    ) -> bool:
        """Wait until the robot has reached a configuration... but only roughly. Used for trajectory execution.

        Parameters:
            xyt: se(2) base pose in world coordinates to go to
            rate: rate at which we should check to see if done
            pos_err_threshold: how far robot can be for this waypoint
            verbose: prints extra info out
            timeout: aborts at this point

        Returns:
            success: did we reach waypoint in time"""
        _delay = 1.0 / rate
        xy = xyt[:2]
        if verbose:
            print(f"Waiting for {xyt}, threshold = {pos_err_threshold}")
        # Save start time for exiting trajectory loop
        t0 = timeit.default_timer()
        while not self._finish:
            # Loop until we get there (or time out)
            t1 = timeit.default_timer()
            curr = self.get_base_pose()
            pos_err = np.linalg.norm(xy - curr[:2])
            rot_err = np.abs(angle_difference(curr[-1], xyt[2]))
            # TODO: code for debugging slower rotations
            # if pos_err < pos_err_threshold and rot_err > rot_err_threshold:
            #     print(f"{curr[-1]}, {xyt[2]}, {rot_err}")
            if verbose:
                # logger.info(f"- {curr=} target {xyt=} {pos_err=} {rot_err=}")
                print(f"- {curr=} target {xyt=} {pos_err=} {rot_err=}")
            if pos_err < pos_err_threshold and rot_err < rot_err_threshold:
                # We reached the goal position
                return True
            t2 = timeit.default_timer()
            dt = t2 - t1
            if t2 - t0 > timeout:
                # logger.warning("Could not reach goal in time: " + str(xyt))
                print("[WAIT FOR WAYPOINT] WARNING! Could not reach goal in time: " + str(xyt))
                breakpoint()
                return False
            time.sleep(max(0, _delay - (dt)))
        return False

    def send_action(self, timeout: float = 10.0):
        """Send the next action to the robot"""
        print("-> sending", self._next_action)
        blocking = False
        block_id = None
        with self._act_lock:
            blocking = self._next_action.get("nav_blocking", False)
            block_id = self._iter
            # Send it
            self._next_action["step"] = block_id
            self._iter += 1
            self.send_socket.send_pyobj(self._next_action)

            # For tracking goal
            if "xyt" in self._next_action:
                goal_angle = self._next_action["xyt"][2]
            else:
                goal_angle = None

            # Empty it out for the next one
            self._next_action = dict()

        # Make sure we had time to read
        time.sleep(0.2)
        if blocking:
            # Wait for the command to finish
            self._wait_for_action(block_id, goal_angle=goal_angle, verbose=True, timeout=timeout)
            time.sleep(0.2)

    def blocking_spin(self, verbose: bool = False, visualize: bool = False):
        """Listen for incoming observations and update internal state"""
        sum_time = 0
        steps = 0
        t0 = timeit.default_timer()
        camera = None
        shown_point_cloud = visualize

        while not self._finish:

            output = self.recv_socket.recv_pyobj()
            if output is None:
                continue

            self._seq_id += 1
            output["rgb"] = cv2.imdecode(output["rgb"], cv2.IMREAD_COLOR)
            compressed_depth = output["depth"]
            depth = cv2.imdecode(compressed_depth, cv2.IMREAD_UNCHANGED)
            output["depth"] = depth / 1000.0

            if camera is None:
                camera = Camera.from_K(
                    output["camera_K"], output["rgb_height"], output["rgb_width"]
                )

            output["xyz"] = camera.depth_to_xyz(output["depth"])

            if visualize and not shown_point_cloud:
                show_point_cloud(output["xyz"], output["rgb"] / 255.0, orig=np.zeros(3))
                shown_point_cloud = True

            self._update_obs(output)
            # with self._act_lock:
            #    if len(self._next_action) > 0:

            t1 = timeit.default_timer()
            dt = t1 - t0
            sum_time += dt
            steps += 1
            if verbose:
                print("Control mode:", self._control_mode)
                print(f"time taken = {dt} avg = {sum_time/steps} keys={[k for k in output.keys()]}")
            t0 = timeit.default_timer()

    def start(self) -> bool:
        """Start running blocking thread in a separate thread"""
        self._thread = threading.Thread(target=self.blocking_spin)
        self._finish = False
        self._thread.start()
        return True

    def __del__(self):
        self.stop()

    def stop(self):
        self._finish = True
        self.recv_socket.close()
        self.recv_state_socket.close()
        self.recv_servo_socket.close()
        self.send_socket.close()
        self.context.term()
        if self._thread is not None:
            self._thread.join()


@click.command()
@click.option("--local", is_flag=True, help="Run code locally on the robot.")
@click.option("--recv_port", default=4401, help="Port to receive observations on")
@click.option("--send_port", default=4402, help="Port to send actions to on the robot")
@click.option("--robot_ip", default="192.168.1.15")
def main(
    local: bool = True,
    recv_port: int = 4401,
    send_port: int = 4402,
    robot_ip: str = "192.168.1.15",
):
    client = HomeRobotZmqClient(
        robot_ip=robot_ip,
        recv_port=recv_port,
        send_port=send_port,
        use_remote_computer=(not local),
    )
    client.blocking_spin(verbose=True, visualize=False)


if __name__ == "__main__":
    main()
