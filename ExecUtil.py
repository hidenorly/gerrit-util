#   Copyright 2024 hidenorly
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import subprocess
import os

class ExecUtil:
    @staticmethod
    def execCmd(command, execPath=".", quiet=True):
        result = False
        if os.path.isdir(execPath):
            exec_cmd = command
            if quiet and "> /dev/null" not in exec_cmd:
                exec_cmd += " > /dev/null 2>&1"
            result = subprocess.call(exec_cmd, shell=True, cwd=execPath) == 0
        return result

    def exec_cmd_with_cd(exec_cmd, target_folder="."):
        current_dir = target_folder

        commands = exec_cmd.split(';')
        for command in commands:
            command = command.strip()
            if command.startswith('cd'):
                # Change directory command
                new_dir = command[3:].strip()
                current_dir = os.path.join(current_dir, new_dir)
            else:
                # Execute other commands
                try:
                    subprocess.run(command, shell=True, check=True, cwd=current_dir)
                except:
                    pass

        return current_dir

    @staticmethod
    def hasResult(command, execPath=".", enableStderr=True):
        result = False
        if os.path.isdir(execPath):
            exec_cmd = command
            if enableStderr and " 2>" not in exec_cmd:
                exec_cmd += " 2>&1"
            try:
                output = subprocess.check_output(exec_cmd, shell=True, cwd=execPath, stderr=subprocess.STDOUT)
                output = output.strip()
                result = True if output else False
            except subprocess.CalledProcessError:
                pass
        return result

    @staticmethod
    def getExecResultEachLine(command, execPath=".", enableStderr=True, enableStrip=True, enableMultiLine=True):
        result = []
        if os.path.isdir(execPath):
            exec_cmd = command
            if enableStderr and " 2>" not in exec_cmd:
                exec_cmd += " 2>&1"
            try:
                output = subprocess.check_output(exec_cmd, shell=True, cwd=execPath, stderr=subprocess.STDOUT)
                lines = output.splitlines()
                for aLine in lines:
                    aLine = aLine.decode('utf-8')
                    if enableStrip:
                        aLine = aLine.strip()
                    result.append(aLine)
            except subprocess.CalledProcessError:
                pass
        return result