# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

from .interfaces import Action, Observations


class Agent(ABC):
    """
    Base stretch agent that can interact with a simulator or hardware.
    """

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def act(self, obs: Observations) -> Tuple[Action, Dict[str, Any]]:
        """
        Act end-to-end.

        Arguments:
            obs: stretch observation

        Returns:
            action: stretch action
            info: additional information (e.g., for debugging, visualization)
        """
        pass
