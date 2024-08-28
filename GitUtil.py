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

from ExecUtil import ExecUtil
import os
import subprocess

class GitUtil:
    STATUS_CHANGES_TO_BE_COMMITED = 0
    STATUS_CHANGES_TO_BE_COMMITED_IDENTIFIER = "Changes to be committed:"

    STATUS_CHANGES_NOT_STAGED = 1
    STATUS_CHANGES_NOT_STAGED_IDENTIFIER = "Changes not staged for commit:"
    STATUS_CHANGES_MODIFIED = "modified:"
    STATUC_CHANGES_NEWFILE = "new file:"
    STATUS_CHANGES_MODIFIED_LEN = len(STATUS_CHANGES_MODIFIED)

    STATUS_UNTRACKED = 2
    STATUS_UNTRACKED_IDENTIFIER = "Untracked files:"

    STATUS_IGNORE_OTHERS = [
        '(use "git restore --staged <file>..." to unstage)',
        '(use "git add <file>..." to update what will be committed)',
        '(use "git add <file>..." to include in what will be committed)',
        '(use "git restore <file>..." to discard changes in working directory)',
        'no changes added to commit (use "git add" and/or "git commit -a")'
    ]

    @staticmethod
    def status(gitPath, gitOpt=""):
        result_to_be_commited = []
        result_changes_not_staged = []
        result_untracked = []

        exec_cmd = f"git status {gitOpt if gitOpt else ''}"
        result = ExecUtil.getExecResultEachLine(exec_cmd, gitPath, False, True, True)

        mode = GitUtil.STATUS_CHANGES_TO_BE_COMMITED
        for aLine in result:
            aLine = str(aLine).strip()
            if aLine == GitUtil.STATUS_CHANGES_TO_BE_COMMITED_IDENTIFIER:
                mode = GitUtil.STATUS_CHANGES_TO_BE_COMMITED
            elif aLine == GitUtil.STATUS_CHANGES_NOT_STAGED_IDENTIFIER:
                mode = GitUtil.STATUS_CHANGES_NOT_STAGED
            elif aLine == GitUtil.STATUS_UNTRACKED_IDENTIFIER:
                mode = GitUtil.STATUS_UNTRACKED
            elif aLine in GitUtil.STATUS_IGNORE_OTHERS:
                pass
            else:
                if mode in [GitUtil.STATUS_CHANGES_NOT_STAGED, GitUtil.STATUS_CHANGES_TO_BE_COMMITED]:
                    pos = aLine.find(GitUtil.STATUS_CHANGES_MODIFIED)
                    if pos == -1:
                        pos = aLine.find(GitUtil.STATUC_CHANGES_NEWFILE)
                    if pos != -1:
                        aFile = aLine[pos + GitUtil.STATUS_CHANGES_MODIFIED_LEN + 1:].strip()
                        if os.path.exists(aFile):
                            if mode == GitUtil.STATUS_CHANGES_TO_BE_COMMITED:
                                result_to_be_commited.append(aFile)
                            else:
                                result_changes_not_staged.append(aFile)
                elif mode == GitUtil.STATUS_UNTRACKED:
                    if os.path.exists(aLine):
                        result_untracked.append(aLine)

        all_modified = result_to_be_commited.copy()
        all_modified.extend(result_changes_not_staged)
        all_modified.extend(result_untracked)
        all_modified = list(set(all_modified))

        return all_modified, result_to_be_commited, result_changes_not_staged, result_untracked

    @staticmethod
    def diff(gitPath, gitOpt=""):
        exec_cmd = f"git diff {gitOpt if gitOpt else ''}"
        return ExecUtil.getExecResultEachLine(exec_cmd, gitPath, False, False, True)