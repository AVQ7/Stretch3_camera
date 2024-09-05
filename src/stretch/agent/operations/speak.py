# Copyright (c) Hello Robot, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in the root directory
# of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# license information maybe found below, if so.

from time import sleep

import numpy as np

import stretch.motion.constants as constants
from stretch.agent.base import ManagedOperation

class SpeakOperation(ManagedOperation):
    """
    Speaks a message given by the user.
    """
    _success = True

    def can_start(self) -> bool:
        return True
    
    def configure(self,
                  message: str = "Hello, world!",):
        """Configure the operation given a message to speak."""
        self.message = message

    def run(
        self,
        message: str = "Hello, world!",
    ):
        """
        Speaks a message

        Parameters:
            message (str): The message to speak.
        """
        try:
            self.agent.tts.say_async(message)
            self._success = True
        except Exception as e:
            self._success = False
            self._error = e


    def was_successful(self) -> bool:
        """Return true if successful"""
        return self._success

    