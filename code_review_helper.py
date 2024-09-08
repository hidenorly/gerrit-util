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

import os
import subprocess
import shlex
from GitUtil import GitUtil
from ExecUtil import ExecUtil


class LlmReview:
    FILE_LLM_REVIEW = os.path.join(os.path.dirname(__file__), "llm-review.py")

    def __init__(self, options=None):
        self.options = str(options) if options else ""

    @staticmethod
    def isAvailable():
        return os.path.exists(LlmReview.FILE_LLM_REVIEW)

    def execute(self, path):
        exec_cmd = f"python3 {LlmReview.FILE_LLM_REVIEW} {shlex.quote(path)} {self.options}"
        return ExecUtil.getExecResultEachLine(exec_cmd, ".", False, False, True)

# ---- main --------------------------
all_modified, result_to_be_commited, result_changes_not_staged, result_untracked = GitUtil.status(".")

checker = []
if LlmReview.isAvailable():
    checker.append(LlmReview())

for aFile in all_modified:
    result = GitUtil.diff(".", f"HEAD {aFile}")
    if result or aFile in result_to_be_commited:
        # actual modified file!
        print(aFile)
        for aChecker in checker:
            _checker = aChecker.execute(aFile)
            print("\n".join(_checker))


















