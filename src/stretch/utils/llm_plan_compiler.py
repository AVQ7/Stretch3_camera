# Copyright (c) Hello Robot, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in the root directory
# of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# license information maybe found below, if so.

import ast

from stretch.agent.base import TaskManager
from stretch.agent.robot_agent import RobotAgent
from stretch.agent.operations import (
    GoToNavOperation,
    GraspObjectOperation,
    SpeakOperation,
    WaveOperation
)

from stretch.core.task import Task

class TreeNode:
    def __init__(self, function_call, success=None, failure=None):
        self.function_call = function_call
        self.success = success
        self.failure = failure

class LLMPlanCompiler(ast.NodeVisitor):
    def __init__(self,
                 agent: RobotAgent,
                 manager: TaskManager,
                 llm_plan: str):
        self.agent = agent
        self.manager = manager
        self.llm_plan = llm_plan
        self.task = None

    def go_to(self, location: str):
        """Adds a GoToNavOperation to the task"""
        self.task.add_operation(GoToNavOperation(name="go_to_" + location, location=location))
        return "go_to_" + location

    def pick(self, object_name: str):
        """Adds a GraspObjectOperation to the task"""
        self.task.add_operation(GraspObjectOperation(name="pick_" + object_name, object_name=object_name))
        return "pick_" + object_name

    def place(self, object_name: str):
        """Adds a PlaceObjectOperation to the task"""
        speak_not_implemented = SpeakOperation(name="place_" + object_name, manager=self.manager)
        speak_not_implemented.configure(message="Place operation not implemented")
        self.task.add_operation(speak_not_implemented)
        return "place_" + object_name

    def say(self, message: str):
        """Adds a SpeakOperation to the task"""
        say_operation = SpeakOperation(name="say_" + message, manager=self.manager)
        say_operation.configure(message=message)
        self.task.add_operation(say_operation)
        return "say_" + message

    def wave(self):
        """Adds a WaveOperation to the task"""
        self.task.add_operation(WaveOperation(name="wave", manager=self.manager))
        return "wave"

    def open_cabinet(self):
        """Adds a SpeakOperation (not implemented) to the task"""
        speak_not_implemented = SpeakOperation(name="open_cabinet", manager=self.manager)
        speak_not_implemented.configure(message="Open cabinet operation not implemented")
        self.task.add_operation(speak_not_implemented)
        return "open_cabinet"

    def close_cabinet(self):
        """Adds a SpeakOperation (not implemented) to the task"""
        speak_not_implemented = SpeakOperation(name="close_cabinet", manager=self.manager)
        speak_not_implemented.configure(message="Close cabinet operation not implemented")
        self.task.add_operation(speak_not_implemented)
        return "close_cabinet"

    def get_detections(self):
        """Adds a SpeakOperation (not implemented) to the task"""
        speak_not_implemented = SpeakOperation(name="get_detections", manager=self.manager)
        speak_not_implemented.configure(message="Get detections operation not implemented")
        self.task.add_operation(speak_not_implemented)
        return "get_detections"

    def build_tree(self, node):
        """Recursively build a tree of function calls"""
        if isinstance(node, ast.If):
            # Extract function call in the test condition
            test = node.test
            if isinstance(test, ast.Call):
                function_call = ast.unparse(test)
            else:
                raise ValueError("Unexpected test condition")

            # Create the root node with the function call
            root = TreeNode(function_call=function_call)

            # Recursively build success and failure branches
            if len(node.body) > 0:
                root.success = self.build_tree(node.body[0])
            if len(node.orelse) > 0:
                root.failure = self.build_tree(node.orelse[0])

            return root

        elif isinstance(node, ast.Expr):
            # Extract function call
            expr = node.value
            if isinstance(expr, ast.Call):
                function_call = ast.unparse(expr)
                return TreeNode(function_call=function_call)

        elif isinstance(node, ast.Module):
            # Start processing the body of the module
            if len(node.body) > 0:
                return self.build_tree(node.body[0])
            
        elif isinstance(node, ast.FunctionDef):
            if len(node.body) > 0:
                return self.build_tree(node.body[0])

        raise ValueError("Unexpected AST node")
    
    def convert_to_task(self,
                        root: TreeNode,
                        parent_operation_name: str = None,
                        success: bool = True):
        """Recursively convert the tree into a task by adding operations and connecting them"""
        if root is None:
            return
        
        # Create the operation
        root_operation_name = eval("self." + root.function_call)

        # Connect the operation to the parent
        if parent_operation_name is not None:
            if success:
                self.task.connect_on_success(parent_operation_name, root_operation_name)
            else:
                self.task.connect_on_failure(parent_operation_name, root_operation_name)

        # Recursively process the success and failure branches
        self.convert_to_task(root.success, root_operation_name, True)
        self.convert_to_task(root.failure, root_operation_name, False)

    def compile(self):
        self.task = Task()
        tree = ast.parse(self.llm_plan)
        root = self.build_tree(tree)
        self.convert_to_task(root)

        return self.task

