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
from openai import AzureOpenAI
import logging
import boto3
from botocore.exceptions import ClientError

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

    def query(self, system_prompt, user_prompt):
        _messages = []
        if system_prompt:
            _messages.append( {"role": "system", "content": system_prompt} )
        if user_prompt:
            _messages.append( {"role": "user", "content": user_prompt} )

        response = self.client.chat.completions.create(
            model= self.model,
            messages = _messages
        )
        return response.choices[0].message.content, response

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
        result = {}

        if path and os.path.isfile(path):
            with open(path, 'r', encoding='UTF-8') as f:
              result = json.load(f)
              if "system_prompt" in result:
                system_prompt = result["system_prompt"]
              if "user_prompt" in result:
                user_prompt = result["user_prompt"]

        if system_prompt or user_prompt:
            return system_prompt, user_prompt
        else:
            return result, None


class CaludeGptHelper(GptHelper):
    def __init__(self, api_key, secret_key, region="us-west-2", model="anthropic.claude-3-sonnet-20240229-v1:0"):
        if api_key and secret_key and region:
            self.client = boto3.client(
                service_name='bedrock-runtime',
                aws_access_key_id=api_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
        else:
            self.client = boto3.client(service_name='bedrock-runtime')

        self.model = model

    def query(self, system_prompt, user_prompt, max_tokens=200000):
        if self.client:
            _message = [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt
                    }
                ]
            }]

            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": 1,
                "top_p": 0.999,
                "system": system_prompt,
                "messages": _message
            })

            try:
                response = self.client.invoke_model_with_response_stream(
                    body=body,
                    modelId=self.model
                )

                result = ""
                status = {}

                for event in response.get("body"):
                    chunk = json.loads(event["chunk"]["bytes"])

                    if chunk['type'] == 'message_delta':
                        status = {
                            "stop_reason": chunk['delta']['stop_reason'],
                            "stop_sequence": chunk['delta']['stop_sequence'],
                            "output_tokens": chunk['usage']['output_tokens'],
                        }
                    if chunk['type'] == 'content_block_delta':
                        if chunk['delta']['type'] == 'text_delta':
                            result += chunk['delta']['text']

                return result, status

            except ClientError as err:
                message = err.response["Error"]["Message"]
                print(f"A client error occurred: {message}")
        return None, None


class MergeConflictSolver:
    def __init__(self, client, promptfile=None):
        self.prompts, _ = GptHelper.read_prompt_json(promptfile)
        self.client = client
        if not "resolver" in self.prompts or not "checker" in self.prompts:
            self.prompts = None

    def _query_conflict_resolution(self, conflict_section):
        content = None
        response = None

        if self.prompts and self.client:
            system_prompt = self.prompts["resolver"]["system_prompt"]
            user_prompt = self.additional_user_prompt + self.prompts["resolver"]["user_prompt"]
            user_prompt = user_prompt.replace("[MERGE_CONFLICT]", conflict_section)

            try:
                content, response = self.client.query(system_prompt, user_prompt)
            except:
                pass
            return content, response

        return None, None

    def _query_checker(self, conflict_section, resolution_diff):
        content = None
        response = None

        if self.prompts and self.client:
            system_prompt = self.prompts["checker"]["system_prompt"]
            user_prompt = self.prompts["checker"]["user_prompt"]
            user_prompt = user_prompt.replace("[DIFF_OUTPUT]", resolution_diff)
            user_prompt = user_prompt.replace("[MERGE_CONFLICT]", conflict_section)
            print("\n---2nd level LLM consideration------")
            print(user_prompt)

            try:
                content, response = self.client.query(system_prompt, user_prompt)
            except:
                pass
            return content, response

        return None, None

    def _check_valid_merge_conflict_resolution(self, lines, is_fallback=True):
        if not lines:
            return False

        _lines = lines.split('\n')

        check_items = {
            '<<<<<<< ': False,
            '=======': False,
            '>>>>>>> ': False
        }
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

    def query(self, conflict_section):
        retry_count = 0
        content = None
        response = None

        self.additional_user_prompt = ""

        while True:
            content, response = self._query_conflict_resolution(conflict_section)
            if content:
                if not self._check_valid_merge_conflict_resolution(content, False):
                    resolution_diff = self.get_code_section(content)
                    if resolution_diff:
                        content, response = self._query_checker(conflict_section, resolution_diff)
            retry_count += 1
            if self._check_valid_merge_conflict_resolution(content) or retry_count>3:
                break
            else:
                print(f"ERROR!!!: LLM didn't provide merge conflict resolution. Retry:{retry_count}")
                print(content)
                self.additional_user_prompt = "Don't forget to remove '<<<<<<<', '=======', '>>>>>>' with '-' line in the resolution diff\n"

        return content, response


def main():
    parser = argparse.ArgumentParser(description='Extract merge conflict for downloaded gerrit patch')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-w', '--download', default='.', help='Specify download path')
    parser.add_argument('-r', '--renew', default=False, action='store_true', help='Specify if re-download anyway')
    parser.add_argument('-m', '--marginline', default=10, type=int, action='store', help='Specify margin lines')

    parser.add_argument('-c', '--useclaude', action='store_true', default=False, help='specify if you want to use calude3')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-p', '--promptfile', action='store', default="./git_merge_conflict_resolution_for_upstream_integration.json", help='specify prompt.json')

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
                conflict_detector = ConflictExtractor(download_path, args.marginline)
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
