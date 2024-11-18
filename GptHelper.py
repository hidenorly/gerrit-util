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
import requests
from openai import AzureOpenAI
import logging
import boto3
from botocore.exceptions import ClientError

class IGpt:
    def query(self, system_prompt, user_prompt):
        return None, None

    @staticmethod
    def add_code_section(the_flatten_lines, path=None):
        if path==None or path.endswith(('.cpp', '.c', '.cxx', '.h', 'hpp', '.hxx', '.py', '.asm', '.java', '.rs', '.kt', '.rb')):
            the_flatten_lines = "```\n" + the_flatten_lines + "\n```"
        return the_flatten_lines

    @staticmethod
    def files_reader(files, margin_lines=10, code_section_if_sourcecode=True):
        result = ""

        for path in files:
            _path = path.split(":")
            target_line = None
            if len(_path)==2:
                path = _path[0]
                try:
                    target_line = int(_path[1])
                except:
                    pass
            if os.path.exists( path ):
                the_file_content = ""
                with open(path, 'r', encoding='UTF-8') as f:
                    the_file_content = f.read()
                    if target_line:
                        # in case of target_line with margin_lines
                        lines = the_file_content.splitlines()
                        start_pos = max(target_line-margin_lines, 0)
                        end_pos = min(target_line+margin_lines, len(lines))
                        the_file_content = "\n".join(lines[start_pos:end_pos])
                    if code_section_if_sourcecode:
                        the_file_content = IGpt.add_code_section(the_file_content, path)
                    result += the_file_content

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


class OpenAIGptHelper(IGpt):
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


class OpenAICompatibleGptHelper(IGpt):
    def __init__(self, api_key, endpoint, model=None, is_streaming = False, headers={}):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.is_streaming = is_streaming
        self.headers = headers
        self.headers['accept'] = 'application/json'
        self.headers['Content-Type'] = 'application/json'
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'

    def _create_payload(self, messages):
        # payload
        payload = {
            "messages": messages,
        }
        if self.is_streaming:
            payload["stream"] = True
        if self.model:
            models = self.model.split(",")
            if len(models)==1:
                payload["model"] = self.model
            else:
                payload["models"] = models

        return payload

    def query(self, system_prompt, user_prompt):
        _messages = []
        if system_prompt:
            _messages.append( {"role": "system", "content": system_prompt} )
        if user_prompt:
            _messages.append( {"role": "user", "content": user_prompt} )

        payload  = self._create_payload(_messages)
        #print(payload)

        if self.is_streaming:
            # streaming mode (ollama mode)
            r = requests.post(self.endpoint, headers=self.headers, json=payload, stream=True)
            r.raise_for_status()
            output = ""
            for line in r.iter_lines():
                body = json.loads(line)
                if "error" in body:
                    raise Exception(body["error"])
                if body.get("done") is False:
                    message = body.get("message", "")
                    content = message.get("content", "")
                    output += content

                if body.get("done", False):
                    message = body
                    message["content"] = output
                    return output, message

        else:
            # non-streaming mode
            response = requests.post(self.endpoint, headers=self.headers, json=payload)
            if response.status_code == 200:
                responses = response_json = response.json()
                if isinstance(responses, dict):
                    responses = [responses]
                main_messages = []
                for a_response in responses:
                    main_messages.append( a_response['choices'][0]['message']['content'] )
                if len(main_messages)==1:
                    main_messages = main_messages[0]
                return main_messages, response_json
            else:
                raise Exception(f"Error: {response.status_code} - {response.text}")

        return None, None



class ClaudeGptHelper(IGpt):
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

            _body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": 1,
                "top_p": 0.999,
                "messages": _message
            }
            if system_prompt:
                _body["system"] = system_prompt
            body = json.dumps(_body)

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

class GptClientFactory:
    @staticmethod
    def new_client(args):
        gpt_client = None

        if args.useclaude or args.gpt=="calude3":
            apikey = os.getenv('AWS_ACCESS_KEY_ID') if not args.apikey else args.apikey
            endpoint = "us-west-2" if not args.endpoint else args.endpoint
            deployment = "anthropic.claude-3-sonnet-20240229-v1:0" if not args.deployment else args.deployment
            secretkey = os.getenv("AWS_SECRET_ACCESS_KEY") if not args.secretkey else args.secretkey
            gpt_client = ClaudeGptHelper(apikey, secretkey, endpoint, deployment)
        elif args.gpt=="openaicompatible" or args.gpt=="local" or args.gpt=="others":
            apikey = os.getenv("LLM_API_KEY") if not args.apikey else args.apikey
            endpoint = os.getenv("LLM_ENDPOINT") if not args.endpoint else args.endpoint
            deployment = os.getenv("LLM_DEPLOYMENT_NAME") if not args.deployment else args.deployment
            is_streaming = True if "/api/chat" in endpoint else False
            headers = {}
            if "header" in args:
                for header in args.header:
                    pos = header.find(":")
                    if pos!=None:
                        headers[header[0:pos]] = header[pos+1:].strip()

            gpt_client = OpenAICompatibleGptHelper(apikey, endpoint, deployment, is_streaming, headers)
        else:
            apikey = os.getenv("AZURE_OPENAI_API_KEY") if not args.apikey else args.apikey
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") if not args.endpoint else args.endpoint
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") if not args.deployment else args.deployment
            gpt_client = OpenAIGptHelper(apikey, endpoint, "2024-02-01", deployment)

        return gpt_client



class GptQueryWithCheck:
    def __init__(self, client=None, promptfile=None):
        self.client = client
        self.system_prompt = None
        self.user_prompt = None
        if promptfile:
            self.system_prompt, self.user_prompt = IGpt.read_prompt_json(promptfile)

    def _generate_prompt(self, replace_keydata={}):
        system_prompt = self.system_prompt
        user_prompt = self.user_prompt

        for replace_keyword, replace_data in replace_keydata.items():
            user_prompt = user_prompt.replace(str(replace_keyword), str(replace_data))

        return system_prompt, user_prompt

    def _query(self, system_prompt, user_prompt):
        content = None
        response = None

        if self.client and user_prompt:
            try:
                content, response = self.client.query(system_prompt, user_prompt)
            except:
                pass
            return content, response

        return None, None

    def is_ok_query_result(self, query_result):
        if not query_result:
            # TODO: override this to check the query_result
            return False
        return True

    def query(self, replace_keydata={}):
        content = None
        response = None

        system_prompt, user_prompt = self._generate_prompt(replace_keydata)
        #print(system_prompt)
        #print(user_prompt)

        retry_count = 0
        while retry_count<3:
            # 1st level
            content, response = self._query(system_prompt, user_prompt)
            retry_count += 1
            if self.is_ok_query_result(content):
                break
            else:
                print(f"ERROR!!!: LLM didn't expected anser. Retry:{retry_count}")
                print(content)

        return content, response
