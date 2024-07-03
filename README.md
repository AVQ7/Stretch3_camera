# Stretch AI

[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat)](https://timothycrosley.github.io/isort/)

Tested with Python 3.9/3.10/3.11. **Development Notice**: The code in this repo is a work-in-progress. The code in this repo may be unstable, since we are actively conducting development. Since we have performed limited testing, you may encounter unexpected behaviors.

## Quickstart

On your PC, add the following yaml to `~/.stretch/config.yaml` (use `127.0.0.1` if you're developing on the robot only):

```yaml
robots:
  - ip_addr: 192.168.1.14 # Substitute with your robot's ip address
    port: 20200
```

On your Stretch, start the server:

```
python3 -m stretch.serve
```

Then, on your PC, write some code:

```python
import stretch
stretch.connect()

stretch.move_by(joint_arm=0.1)

for img in stretch.stream_nav_camera():
    cv2.imshow('Nav Camera', img)
    cv2.waitKey(1)
```

Check out the docs on:

- [Getting status](./docs/status.md)

## Installation

On both your PC and your robot, clone and install the package:

```basha
git clone git@github.com:hello-robot/stretch_ai.git --recursive 
```

On your Stretch, symlink the `stretch_ros2_bridge` directory to your ament workspace and build:

```bash
cd stretch_ai
ln -s `pwd`/src/stretch_ros2_bridge $HOME/ament_ws/src/stretch_ros2_bridge
colcon build --symlink-install --packages-select stretch_ros2_bridge
```

More instructions on the ROS2 bridge are in [its dedicated readme](src/stretch_ros2_bridge/README.md).

### Advanced Installation (PC Only)

If you want to install AI code using pytorch, run the following on your GPU-enabled workstation:

```
./install.sh
```

Caution, it may take a while! Several libraries are built from source to avoid potential compatibility issues.

You may need to configure some options for the right pytorch/cuda version. Make sure you have CUDA installed on your computer, preferably 11.8. For issues, see [docs/about_advanced_installation.md](docs/about_advanced_installation.md).

## Example Apps

### Visualization and Streaming Video

Visualize output from the caneras and other sensors on the robot. This will open multiple windows with wrist camera and both low and high resolution head camera feeds.

```bash
python -m stretch.app.view_images --robot_ip $ROBOT_IP
```

You can also visualize it with semantic segmentation (defaults to [Detic](https://github.com/facebookresearch/Detic/):

```bash
python -m stretch.app.view_images --robot_ip $ROBOT_IP --semantic_segmentation
```

### Dex Teleop for Data Collection

Dex teleop is a low-cost system for providing user demonstrations of dexterous skills right on your Stretch. It has two components:

- `follower` runs on the robot, publishes video and state information, and receives goals from a large remote server
- `leader` runs on a GPU enabled desktop or laptop, where you can run a larger neural network.

To start it, on the robot, run:

```bash
python -m stretch.app.dex_teleop.follower
# You can run it in fast mode once you are comfortable with execution
python -m stretch.app.dex_teleop.follower --fast
```

On a remote, GPU-enabled laptop or workstation connected to the [dex telop setup](https://github.com/hello-robot/stretch_dex_teleop):

```bash
python -m stretch.app.dex_teleop.leader
```

[Read the Dex Teleop documentation](docs/dex_teleop.md) for more details.

### Automatic 3d Mapping

```bash
python -m stretch.app.mapping
```

You can show visualizations with:

```bash
python -m stretch.app.mapping --show-intermediate-maps --show-final-map
```

The flag `--show-intermediate-maps` shows the 3d map after each large motion (waypoint reached), and `--show-final-map` shows the final map after exploration is done.

It will record a PCD/PKL file which can be interpreted with the `read_sparse_voxel_map` script; see below.

Another useful flag when testing is the `--reset` flag, which will reset the robot to the starting position of (0, 0, 0). This is done blindly before any execution or mapping, so be careful!

### Voxel Map Visualization

You can test the voxel code on a captured pickle file:

```bash
python -m stretch.app.read_sparse_voxel_map -i ~/Downloads/stretch\ output\ 2024-03-21/stretch_output_2024-03-21_13-44-19.pkl
```

Optional open3d visualization of the scene:

```bash
python -m stretch.app.read_sparse_voxel_map -i ~/Downloads/stretch\ output\ 2024-03-21/stretch_output_2024-03-21_13-44-19.pkl  --show-svm
```

### Pickup Toys

This will have the robot move around the room, explore, and pickup toys in order to put them in a box.

```bash
python -m stretch.app.pickup
```

You can add the `--reset` flag to make it go back to the start position.

```
python -m stretch.app.pickup --reset
```

## Development

Clone this repo on your Stretch and PC, and install it locally using pip with the "editable" flag:

```
cd stretchpy/src
pip install -e .[dev]
pre-commit install
```

Then follow the quickstart section. See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.

### Code Overview

The code is organized as follows. Inside the core package `src/stretch`:

- `motion` contains motion planning tools
- `mapping` is broken up into tools for voxel (3d / ok-robot style), instance mapping
- `core` is basic tools and interfaces
- `app` contains individual endpoints, runnable as `python -m stretch.app.<app_name>`, such as mapping, discussed above.
- `agent` is aggregate functionality, particularly robot_agent which includes lots of common tools including motion planning algorithms.
  - In particular, `agent/zmq_client.py` is specifically the robot control API, an implementation of the client in core/interfaces.py. there's another ROS client in `stretch_ros2_bridge`.
  - `agent/robot_agent.py` is the main robot agent, which is a high-level interface to the robot. It is used in the `app` scripts.
  - `agent/task/*` contains task-specific code, such as for the `pickup` task. This is divided between "Managers" like [pickup_manager.py](src/stretch/agent/task/pickup_manager.py) which are composed of "Operations" like those in [operations.py](src/stretch/agent/task/operations.py). Each operation is a composable state machine node with pre- and post-conditions.

The `stretch_ros2_bridge` package is a ROS2 bridge that allows the Stretch AI code to communicate with the ROS2 ecosystem. It is a separate package that is symlinked into the `ament_ws` workspace on the robot.

### Updating Code on the Robot

See the [update guide](docs/update.md) for more information. There is an [update script](scripts.update.sh) which should handle some aspects of this. Code installed from git must be updated manually, including code from this repository.

### Docker

Docker build and other instructions are located in the [docker guide](docs/docker.md). Generally speaking, from the root of the project, you  can run the docker build process with:

```
docker build -t stretch-ai_cuda-11.8:latest .
```

See the [docker guide](docs/docker.md) for more information and troubleshooting advice.
