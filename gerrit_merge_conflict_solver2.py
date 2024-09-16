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
import re
import sys
import json
from GerritUtil import GerritUtil
from GitUtil import GitUtil
from GptHelper import GptClientFactory, IGpt, GptQueryWithCheck
from gerrit_merge_conflict_extractor import ConflictExtractor


class MergeConflictSolver(GptQueryWithCheck):
    def __init__(self, client, promptfile):
        super().__init__(client, promptfile)

    def _generate_prompt(self, query_key, replace_keydata={}):
        system_prompt = ""
        user_prompt = ""

        if self.prompts and query_key in self.prompts:
            system_prompt = self.prompts[query_key]["system_prompt"]
            user_prompt = self.additional_user_prompt + self.prompts[query_key]["user_prompt"]
            for replace_keyword, replace_data in replace_keydata.items():
                user_prompt = user_prompt.replace(replace_keyword, replace_data)

        return system_prompt, user_prompt

    # for 1st level LLM "reolver" in the prompt .json
    def _query_conflict_resolution(self, conflict_section):
        system_prompt, user_prompt = self._generate_prompt("resolver", {"[MERGE_CONFLICT]":conflict_section})
        return self._query(system_prompt, user_prompt)

    # for 2nd level LLM "checker" in the prompt .json
    def _query_checker(self, conflict_section, resolution_diff):
        system_prompt, user_prompt = self._generate_prompt("checker", {"[DIFF_OUTPUT]":resolution_diff, "[MERGE_CONFLICT]":conflict_section})
        return self._query(system_prompt, user_prompt)

    def _check_valid_merge_conflict_resolution(self, lines, is_fallback=True):
        if not lines:
            return False

        _lines = lines.split('\n')

        check_items = {
            '<<<<<<< ': False,
            '=======': False,
            '>>>>>>> ': False
        }
        # check -<<<<<<<, -======= and ->>>>>>> are included as diff
        for line in _lines:
            line = line.strip()
            for key, status in check_items.items():
                if not status and line.startswith("-") and line[1:].strip().startswith(key):
                    check_items[key] = True
                    break
            isAllFound = True
            for status in check_items.values():
                isAllFound = isAllFound and status
            if isAllFound:
                return True

        # check the given lines do NOT include any <<<<<<<, ======= and >>>>>>>
        if is_fallback:
            for key in check_items.keys():
                if key in lines:
                    return False
            return True

        return False

    def get_code_section(self, lines):
        results = []

        if lines and not isinstance(lines, list):
            lines = lines.split("\n")
        if not lines:
            lines=[]

        start_pos = None
        for i in range(0, len(lines)):
            line = lines[i].strip()
            if start_pos==None and (line.startswith("```") or line.startswith("++ b/")):
                start_pos = i
            elif start_pos!=None and line.startswith("```"):
                results.extend( lines[start_pos+1:i] )
                start_pos = None
        if start_pos!=None:
            results.extend( lines[start_pos+1:len(lines)] )
        if not results and not lines:
            print("ERROR!!!!!")
            print("\n".join(lines))
            results = lines

        return str("\n".join(results))


    def is_ok_query_result(self, query_result, is_fallback=False):
        if not query_result:
            resolution_code = self.get_code_section(query_result)
            return self._check_valid_merge_conflict_resolution(resolution_code, is_fallback)
        return False


    def query(self, conflict_section):
        retry_count = 0
        content = None
        response = None

        self.additional_user_prompt = ""

        # is_fallback==True means to accept non-diff style (replace style)
        is_fallback = False
        if self.prompts and "is_replace_allowed" in self.prompts:
            if self.prompts["is_replace_allowed"]=="true":
                is_fallback=True

        while True:
            # 1st level
            content, response = self._query_conflict_resolution(conflict_section)
            resolution_code = None
            if content:
                resolution_code = self.get_code_section(content)
            # 2nd level is necessary
            if resolution_code:
                if not self._check_valid_merge_conflict_resolution(resolution_code, is_fallback):
                    _content, _response = self._query_checker(conflict_section, resolution_code)
                    if _content and _response:
                        resolution_code = self.get_code_section(_content)
                        content = _content
                        response = _response
            retry_count += 1
            if self._check_valid_merge_conflict_resolution(resolution_code, is_fallback) or retry_count>3:
                break
            else:
                print(f"ERROR!!!: LLM didn't provide merge conflict resolution. Retry:{retry_count}")
                print(content)
                if content!=None:
                    self.additional_user_prompt = "Don't forget to remove '<<<<<<<', '=======', '>>>>>>' with '-' line in the resolution diff\n"

        return content, response


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

    args = parser.parse_args()

    gpt_client = GptClientFactory.new_client(args)
    solver = MergeConflictSolver(gpt_client, args.promptfile)

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","))
    for project, data in result.items():
        for branch, theData in data.items():
            for _data in theData:
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
                    for i,section in enumerate(sections):
                        print(f'---conflict_section---{i}')
                        print(section["section"])
                        resolution, _full_response = solver.query(section["section"])
                        print(f'---resolution---{i}')
                        print(resolution)

if __name__ == "__main__":
    main()
