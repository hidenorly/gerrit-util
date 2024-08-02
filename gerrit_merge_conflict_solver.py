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
import json
from openai import AzureOpenAI

from gerrit_query import GerritUtil
from gerrit_patch_downloader import GitUtil
from gerrit_merge_conflict_extractor import ConflictExtractor

class GptHelper:
    def __init__(self, api_key, endpoint, api_version = "2024-02-01", model = "gpt-35-turbo-instruct"):
        self.client = AzureOpenAI(
          api_key = api_key,
          api_version = api_version,
          azure_endpoint = endpoint
        )
        self.model = model

    def query(self, _messages):
        response = self.client.chat.completions.create(
            model= self.model,
            messages = _messages
        )
        return response

    @staticmethod
    def files_reader(files):
        result = ""

        for path in files:
            if os.path.exists( path ):
              with open(path, 'r', encoding='UTF-8') as f:
                result += f.read()

        return result

    @staticmethod
    def read_prompt_json(path):
        system_prompt = ""
        user_prompt = ""

        if path and os.path.isfile(path):
            with open(path, 'r', encoding='UTF-8') as f:
              result = json.load(f)
              if "system_prompt" in result:
                system_prompt = result["system_prompt"]
              if "user_prompt" in result:
                user_prompt = result["user_prompt"]

        return system_prompt, user_prompt


class MergeConflictSolver:
    def __init__(self, api_key, endpoint, api_version = "2024-02-01", model = "gpt-35-turbo-instruct", promptfile=None):
        self.system_prompt, self.user_prompt = GptHelper.read_prompt_json(promptfile)
        self.client = GptHelper(api_key, endpoint, api_version, model)

    def query(self, conflict_section):
        response = None

        messages = []
        if self.system_prompt:
            messages.append( {"role": "system", "content": self.system_prompt} )
        if self.user_prompt:
            messages.append( {"role": "user", "content": self.user_prompt+"\n```"+conflict_section+"```"} )

        try:
            response = self.client.query(messages)
        except:
            pass
        return response.choices[0].message.content, response


def main():
    parser = argparse.ArgumentParser(description='Extract merge conflict for downloaded gerrit patch')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-w', '--download', default='.', help='Specify download path')
    parser.add_argument('-r', '--renew', default=False, action='store_true', help='Specify if re-download anyway')

    parser.add_argument('-k', '--apikey', action='store', default=os.getenv("AZURE_OPENAI_API_KEY"), help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-e', '--endpoint', action='store', default=os.getenv("AZURE_OPENAI_ENDPOINT"), help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"), help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-p', '--promptfile', action='store', default="./git_merge_conflict_resolution_for_upstream_integration.json", help='specify prompt.json')

    args = parser.parse_args()

    solver = MergeConflictSolver(args.apikey, args.endpoint, "2024-02-01", args.deployment, args.promptfile)

    result = GerritUtil.query(args.target, args.branch, args.status, args.since)
    for project, data in result.items():
        for branch, theData in data.items():
            for _data in theData:
                print(f'project:{project}')
                print(f'branch:{branch}')
                for key, value in _data.items():
                    print(f'{key}:{value}')
                print("")
                download_path = GitUtil.download(args.download, _data["number"], _data["patchset1_ssh"], args.renew)
                conflict_detector = ConflictExtractor(download_path)
                conflict_sections = conflict_detector.get_conflicts()
                for file_name, sections in conflict_sections.items():
                    print(file_name)
                    for i,section in enumerate(sections):
                        print(f'---conflict_section---{i}')
                        print(section)
                        resolution, _full_response = solver.query(section)
                        print(f'---resolution---{i}')
                        print(resolution)

if __name__ == "__main__":
    main()
