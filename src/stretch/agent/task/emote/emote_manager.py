# Copyright (c) Hello Robot, Inc.
#
# This source code is licensed under the APACHE 2.0 license found in the
# LICENSE file in the root directory of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# licence information maybe found below, if so.
#

from stretch.agent.base import TaskManager
from stretch.agent.robot_agent import RobotAgent
from stretch.core.task import Operation, Task


class EmoteManager(TaskManager):
    """
    Provides a minimal interface with the TaskManager class.
    """

    def __init__(self, agent: RobotAgent):
        super().__init__(agent)

        # random stuff that has to be synced...
        self.navigation_space = agent.space
        self.parameters = agent.parameters
        self.robot = agent.robot

    def get_task(self, emote_operation: Operation) -> Task:
        task = Task()
        task.add_operation(emote_operation)
        return task
