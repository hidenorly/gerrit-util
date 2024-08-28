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

class IGpt:
    def query(self, system_prompt, user_prompt):
        return None, None

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

class GptClientFactory:
    @staticmethod
    def new_client(args):
        gpt_client = None

        if args.useclaude:
            if not args.apikey:
                args.apikey = os.getenv('AWS_ACCESS_KEY_ID')
            if not args.endpoint:
                args.endpoint = "us-west-2"
            if not args.deployment:
                args.deployment = "anthropic.claude-3-sonnet-20240229-v1:0"
            gpt_client = ClaudeGptHelper(args.apikey, args.secretkey, args.endpoint, args.deployment)
        else:
            if not args.apikey:
                args.apikey = os.getenv("AZURE_OPENAI_API_KEY")
            if not args.endpoint:
                args.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            if not args.deployment:
                args.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            gpt_client = OpenAIGptHelper(args.apikey, args.endpoint, "2024-02-01", args.deployment)

        return gpt_client
