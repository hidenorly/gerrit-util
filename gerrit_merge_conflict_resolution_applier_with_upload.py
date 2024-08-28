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

from GerritUtil import GerritUtil
from GitUtil import GitUtil
from ExecUtil import ExecUtil
from GptHelper import GptClientFactory, IGpt
from gerrit_merge_conflict_extractor import ConflictExtractor
from gerrit_merge_conflict_solver import MergeConflictSolver
from gerrit_merge_conflict_resolution_applier import MergeConflictResolutionApplier
from gerrit_merge_conflict_resolution_applier import FileUtils

class GerritUploader:
    def upload(target_folder, branch):
        upload_cmd = f"git add *; git commit --amend --no-edit; git push origin HEAD:refs/for/{branch}"

        # check the target_folder is git folder
        if os.path.exists(os.path.join(target_folder+"/.git")):
            ExecUtil.exec_cmd_with_cd(upload_cmd, target_folder)

        return target_folder

class UploadableChecker:
    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "git_merge_resolved_checker.json")

    def __init__(self, client=None, promptfile=None):
        self.system_prompt, self.user_prompt = IGpt.read_prompt_json(UploadableChecker.PROMPT_FILE)
        self.client = client #GptClientFactory.new_client(args)

    def _generate_prompt(self, replace_keydata={}):
        system_prompt = self.system_prompt
        user_prompt = self.user_prompt

        for replace_keyword, replace_data in replace_keydata.items():
            user_prompt = user_prompt.replace(replace_keyword, replace_data)

        return system_prompt, user_prompt

    def _query(self, system_prompt, user_prompt):
        content = None
        response = None

        if self.client and system_prompt and user_prompt:
            try:
                print(system_prompt)
                print(user_prompt)
                content, response = self.client.query(system_prompt, user_prompt)
            except:
                pass
            return content, response

        return None, None

    def query(self, diff_result):
        retry_count = 0
        content = None
        response = None

        if isinstance(diff_result, list):
            diff_result = "\n".join(diff_result)

        print(f"{diff_result=}")

        system_prompt, user_prompt = self._generate_prompt({"[GIT_DIFF]":diff_result})

        while True:
            # 1st level
            content, response = self._query(system_prompt, user_prompt)
            print(str(content))
            retry_count += 1
            if content.strip().startswith(("YES","NO")) or retry_count>3:
                break
            else:
                print(f"ERROR!!!: LLM didn't expected anser. Retry:{retry_count}")
                print(content)

        return content, response


    def is_diff_ok(self, git_dir, file_path):
        is_ok = False

        if file_path.startswith(git_dir):
            file_path = file_path[len(git_dir)+1:]

        print(f"{git_dir=}, {file_path=}")

        diff_result = GitUtil.diff(git_dir, f"HEAD {file_path}")
        content, response = self.query(diff_result)
        if content:
            content = content.strip().upper()
            is_ok = True if content == "YES" else False

        return is_ok


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
    parser.add_argument('-l', '--largerconflictsection', default=False, action='store_true', help='Specify if unify overwrapped sections')

    parser.add_argument('-c', '--useclaude', action='store_true', default=False, help='specify if you want to use calude3')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-p', '--promptfile', action='store', default="./git_merge_conflict_resolution_for_upstream_integration.json", help='specify prompt.json')

    parser.add_argument('-a', '--apply', action='store_true', default=False, help='Specify if apply the modification for the conflicted file')
    parser.add_argument('-u', '--upload', action='store_true', default=False, help='Specify if upload the the conflict resolved result')

    args = parser.parse_args()

    gpt_client = GptClientFactory.new_client(args)
    solver = MergeConflictSolver(gpt_client, args.promptfile)
    applier = MergeConflictResolutionApplier(args.marginline)
    checker = UploadableChecker(gpt_client)

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
                download_path = GerritUtil.download(args.download, _data["number"], _data["patchset1_ssh"], args.renew)
                conflict_detector = ConflictExtractor(download_path, args.marginline, args.largerconflictsection)
                conflict_sections = conflict_detector.get_conflicts()
                for file_name, sections in conflict_sections.items():
                    print(file_name)
                    target_file_lines = applier.read_file(file_name)
                    _target_file_lines = []

                    # get resolutions for each conflicted area
                    resolutions = []
                    _resolutions = []
                    resolution_section_mapper={}
                    last_pos = 0
                    for i,section in enumerate(sections):
                        start_pos = section["start"]
                        end_pos = section["end"]
                        orig_start_pos = section["orig_start"]
                        orig_end_pos = section["orig_end"]
                        conflict_section_codes = section["section"]
                        print(f'---conflict_section---{i} ({file_name})')
                        print(conflict_section_codes)
                        resolution, _full_response = solver.query(conflict_section_codes)
                        print(f'---resolution---{i} ({file_name})')
                        print(resolution)
                        codes = applier.get_code_section(resolution)
                        resolutions.extend( codes )
                        for _code in codes:
                            _code = str(_code)
                            resolution_section_mapper[_code] = [start_pos, end_pos, orig_start_pos, orig_end_pos]
                            if orig_start_pos!=None and orig_start_pos>=start_pos:
                                resolution_section_mapper[_code].append(target_file_lines[start_pos:orig_start_pos+1])
                            else:
                                resolution_section_mapper[_code].append([target_file_lines[start_pos]])
                            if orig_end_pos!=None and orig_end_pos<=end_pos:
                                resolution_section_mapper[_code].append(target_file_lines[orig_end_pos:end_pos])
                            else:
                                resolution_section_mapper[_code].append([target_file_lines[end_pos]])

                    # apply resolutions for the file
                    resolutions_lines = list(itertools.chain(*resolutions))
                    target_file_lines = applier.solve_merge_conflict(target_file_lines, sections, resolutions_lines, resolutions, resolution_section_mapper)
                    _, is_modified_target_file_lines = applier.just_in_case_cleanup(target_file_lines)
                    if is_modified_target_file_lines:
                        print("!!!!ERROR!!!!: merge conflict IS NOT solved!!!! Should skip this file")
                        canUpload = False
                        #break
                        #the following is for debug
                        #target_file_lines = _

                    #print(f'---resolved_full_file---{file_name}')
                    #print('\n'.join(target_file_lines))
                    if args.apply or args.upload:
                        FileUtils.save_modified_code(file_name, target_file_lines)
                        if not checker.is_diff_ok(download_path, file_name):
                            print(f"{file_name}'s git diff seems to be NOT OK to git commit; git push")
                            canUpload = False

                if canUpload and args.upload:
                    GerritUploader.upload(os.path.join(download_path, _data["project_dir"]), branch)
                exit() # for debug


if __name__ == "__main__":
    main()
