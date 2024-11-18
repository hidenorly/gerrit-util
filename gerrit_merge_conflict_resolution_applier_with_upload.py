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
from FileUtil import FileUtil


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

        system_prompt, user_prompt = self._generate_prompt({"[GIT_DIFF]":diff_result})
        #print(user_prompt)

        while True:
            # 1st level
            content, response = self._query(system_prompt, user_prompt)
            retry_count += 1
            review_result = str(content).strip().upper()
            if "YES" in review_result or "NO" in review_result or retry_count>3:
                break
            else:
                print(f"ERROR!!!: LLM didn't expected anser. Retry:{retry_count}")
                print(content)

        return content, response

    def is_diff_available(self, diff_result):
        result = []
        for i, line in enumerate(diff_result):
            if line.startswith("+++ b/"):
                diff_result = diff_result[i+1:]
                break
        for i, line in enumerate(diff_result):
            line = line.strip()
            if line:
                result.append(line)
        result = "".join(result).strip()
        return True if result else False

    def get_non_diff_result(self, git_dir, file_path, margin_lines = 10):
        results = ["The following is a part of changed code (non-diff):"]

        # extract diff positions
        diff_result = GitUtil.diff(git_dir, f"--ignore-space-at-eol --ignore-cr-at-eol {file_path}")
        positions = []
        for line in diff_result:
            if line.startswith("@@ "):
                start_pos = None
                line_count = None
                pos = line.find("+")
                if pos:
                    line = line[pos+1:]
                pos = line.find(",")
                if pos:
                    start_pos = line[:pos]
                    line = line[pos+1:]
                pos = line.find(" @@ ")
                if pos:
                    line_count = line[:pos]
                if start_pos and line_count:
                    try:
                        positions.append([int(start_pos), int(line_count)])
                    except:
                        pass

        target_file_lines = FileUtil.read_file(os.path.join(git_dir, file_path))
        target_file_lines_length = len(target_file_lines)
        for pos in positions:
            start_pos = max(pos[0]-margin_lines, 0)
            end_pos = min(pos[0]+pos[1]+margin_lines, target_file_lines_length)
            results = results + ["", "..snip.."] + target_file_lines[start_pos:end_pos] + ["..snip..",""]

        return results

    def is_diff_marker_included(self, git_dir, file_path):
        target_file_lines = FileUtil.read_file(os.path.join(git_dir, file_path))
        for line in target_file_lines:
            line=line.strip()
            if line.startswith(("<<<<<<< ", "=======", ">>>>>>> ")):
                return True
        return False

    def _check_change(self, lines):
        is_ok = False
        if self.is_diff_available(lines):
            content, response = self.query(lines)
            print(content)
            if content:
                content = content.strip().upper()
                is_ok = True if "YES" in content else False
        else:
            is_ok = True
        return is_ok

    def is_diff_ok(self, git_dir, file_path):
        if file_path.startswith(git_dir):
            file_path = file_path[len(git_dir)+1:]

        is_ok = self.is_diff_marker_included(git_dir, file_path)
        if is_ok:
            # Not found the conflict marker
            # --- Try to check with git diff
            diff_result = GitUtil.diff(git_dir, f"--ignore-space-at-eol --ignore-cr-at-eol {file_path}")
            is_ok = self._check_change(diff_result)

            # --- Try to check with non-diff (Fallback for LMM's confusion)
            if not is_ok:
                print("try with non-diff...")
                non_diff_result = self.get_non_diff_result(git_dir, file_path)
                is_ok = self._check_change(non_diff_result)

        return is_ok


def main():
    parser = argparse.ArgumentParser(description='Extract merge conflict for downloaded gerrit patch')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-n', '--numbers', default="", action='store', help='Specify gerrit numbers with ,')
    parser.add_argument('--gitpath', default=None, action='store', help='Specify regexp for project(gitpath) if necessary')

    parser.add_argument('--connection', default="http", action='store', help='Specify ssh or http')

    parser.add_argument('-w', '--download', default='.', help='Specify download path')
    parser.add_argument('-r', '--renew', default=False, action='store_true', help='Specify if re-download anyway')
    parser.add_argument('-m', '--marginline', default=10, type=int, action='store', help='Specify margin lines')
    parser.add_argument('-l', '--largerconflictsection', default=False, action='store_true', help='Specify if unify overwrapped sections')

    parser.add_argument('-c', '--useclaude', action='store_true', default=False, help='specify if you want to use calude3 (force to use claude3 for option backward compatibiliy)')
    parser.add_argument('-g', '--gpt', action='store', default="openai", help='specify openai or calude3 or openaicompatible')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=None, help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-H', '--header', action='append', default=[], help='Specify headers for http e.g. header_key:value (multiple --header are ok)')

    parser.add_argument('-p', '--promptfile', action='store', default="./git_merge_conflict_resolution_for_upstream_integration.json", help='specify prompt.json')

    parser.add_argument('-a', '--apply', action='store_true', default=False, help='Specify if apply the modification for the conflicted file')
    parser.add_argument('-u', '--upload', action='store_true', default=False, help='Specify if upload the the conflict resolved result')

    args = parser.parse_args()

    gpt_client = GptClientFactory.new_client(args)
    solver = MergeConflictSolver(gpt_client, args.promptfile)
    applier = MergeConflictResolutionApplier(args.marginline)
    args.useclaude=True if not args.apikey and not args.endpoint and not args.deployment else False
    #print(f"UploadableChecker:{args.useclaude=}")
    checker = UploadableChecker( GptClientFactory.new_client(args) ) #gpt_client)

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","), [], args.connection, args.gitpath)
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
                    is_resolution_ok = False
                    retry_count = 0
                    target_file_lines_orig = FileUtil.read_file(file_name)
                    while(not is_resolution_ok and retry_count<3):
                        retry_count += 1
                        print(f"{file_name} ({retry_count=}))")
                        _target_file_lines = []
                        target_file_lines = target_file_lines_orig.copy()
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
                            if len(conflict_section_codes)>300:
                                print(conflict_section_codes[0:300]+"\n..snip..")
                            else:
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
                        if args.apply or args.upload:
                            FileUtil.save_modified_code(file_name, target_file_lines)
                            is_resolution_ok = checker.is_diff_ok(download_path, file_name)
                            if is_resolution_ok:
                                print(f"{file_name}'s git diff should be OK to git commit; git push")
                                break
                            else:
                                print(f"{file_name}'s git diff seems to be NOT OK to git commit; git push")
                                # will retry
                        else:
                            is_resolution_ok = True # this means may include not complete resolution but it should be ok since it's not applied
                            break
                    canUpLoad = canUpload and is_resolution_ok

                if args.upload:
                    if canUpload:
                        GerritUtil.upload(download_path, branch)
                    else:
                        print(f"{canUpload=}")


if __name__ == "__main__":
    main()
