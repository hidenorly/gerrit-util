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
import re
import itertools
import subprocess

from gerrit_query import GerritUtil
from gerrit_patch_downloader import GitUtil
from gerrit_merge_conflict_extractor import ConflictExtractor
from gerrit_merge_conflict_solver import GptHelper
from gerrit_merge_conflict_solver import CaludeGptHelper
from gerrit_merge_conflict_solver import MergeConflictSolver
from gerrit_merge_conflict_resolution_applier import MergeConflictResolutionApplier
from gerrit_merge_conflict_resolution_applier import FileUtils

class ExecUtil:
    def exec_cmd(exec_cmd, target_folder="."):
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

class GerritUploader:
    def upload(target_folder, branch):
        upload_cmd = f"git add *; git commit --amend --no-edit; git push origin HEAD:refs/for/{branch}"

        # check the target_folder is git folder
        if os.path.exists(os.path.join(target_folder+"/.git")):
            ExecUtil.exec_cmd(upload_cmd, target_folder)

        return target_folder


def main():
    parser = argparse.ArgumentParser(description='Extract merge conflict for downloaded gerrit patch')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-n', '--numbers', default="", action='store', help='Specify gerrit numbers with ,')

    parser.add_argument('-w', '--download', default='.', help='Specify download path')
    parser.add_argument('-r', '--renew', default=False, action='store_true', help='Specify if re-download anyway')
    parser.add_argument('-m', '--marginline', default=10, type=int, action='store', help='Specify margin lines')

    parser.add_argument('-c', '--useclaude', action='store_true', default=False, help='specify if you want to use calude3')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-p', '--promptfile', action='store', default="./git_merge_conflict_resolution_for_upstream_integration.json", help='specify prompt.json')

    parser.add_argument('-a', '--apply', action='store_true', default=False, help='Specify if apply the modification for the conflicted file')
    parser.add_argument('-u', '--upload', action='store_true', default=False, help='Specify if upload the the conflict resolved result')

    args = parser.parse_args()

    gpt_client = None
    if args.useclaude:
        if not args.apikey:
            args.apikey = os.getenv('AWS_ACCESS_KEY_ID')
        if not args.endpoint:
            args.endpoint = "us-west-2"
        if not args.deployment:
            args.deployment = "anthropic.claude-3-sonnet-20240229-v1:0"
        gpt_client = CaludeGptHelper(args.apikey, args.secretkey, args.endpoint, args.deployment)
    else:
        if not args.apikey:
            args.apikey = os.getenv("AZURE_OPENAI_API_KEY")
        if not args.endpoint:
            args.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not args.deployment:
            args.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        gpt_client = GptHelper(args.apikey, args.endpoint, "2024-02-01", args.deployment)

    solver = MergeConflictSolver(gpt_client, args.promptfile)
    applier = MergeConflictResolutionApplier(args.marginline)

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","))
    for project, data in result.items():
        for branch, theData in data.items():
            for _data in theData:
                canUpload = True
                print(f'project:{project}')
                print(f'branch:{branch}')
                for key, value in _data.items():
                    print(f'{key}:{value}')
                print("")
                download_path = GitUtil.download(args.download, _data["number"], _data["patchset1_ssh"], args.renew)
                conflict_detector = ConflictExtractor(download_path, args.marginline)
                conflict_sections = conflict_detector.get_conflicts()
                for file_name, sections in conflict_sections.items():
                    print(file_name)
                    # get resolutions for each conflicted area
                    resolutions = []
                    for i,section in enumerate(sections):
                        print(f'---conflict_section---{i}')
                        print(section["section"])
                        resolution, _full_response = solver.query(section["section"])
                        print(f'---resolution---{i}')
                        print(resolution)
                        codes = applier.get_code_section(resolution)
                        resolutions.extend( codes )

                    # apply resolutions for the file
                    target_file_lines = applier.read_file(file_name)
                    resolutions_lines = list(itertools.chain(*resolutions))
                    target_file_lines = applier.solve_merge_conflict(target_file_lines, sections, resolutions_lines, resolutions)
                    _target_file_lines = applier.just_in_case_cleanup(target_file_lines)
                    #print(f'---resolved_full_file---{file_name}')
                    #print('\n'.join(target_file_lines))
                    if _target_file_lines != target_file_lines:
                        print("!!!!ERROR!!!!: merge conflict IS NOT solved!!!! Should skip to upload this")
                        target_file_lines = _target_file_lines
                        canUpload = False

                    if args.apply or args.upload:
                        FileUtils.save_modified_code(file_name, target_file_lines)
                if canUpload and args.upload:
                    GerritUploader.upload(os.path.join(download_path, _data["project_dir"]), branch)
                exit() # for debug


if __name__ == "__main__":
    main()
