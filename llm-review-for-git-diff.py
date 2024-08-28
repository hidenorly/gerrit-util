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

import argparse
import os
import sys
from gerrit_merge_conflict_solver import GptClientFactory
from gerrit_merge_conflict_resolution_applier_with_upload import UploadableChecker
from GitUtil import GitUtil

if __name__=="__main__":
    parser = argparse.ArgumentParser(description='Review the git diff')
    parser.add_argument('-c', '--useclaude', action='store_true', default=False, help='specify if you want to use calude3')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')

    args = parser.parse_args()

    gpt_client = GptClientFactory.new_client(args)
    checker = UploadableChecker(gpt_client)

    all_modified, result_to_be_commited, result_changes_not_staged, result_untracked = GitUtil.status(".")

    for file_path in all_modified:
        result = checker.is_diff_ok(".", file_path)
        print(f"{file_path}:{str(result)}")
