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
import re
import argparse
from GerritUtil import GerritUtil
from GitUtil import GitUtil
from FileUtil import FileUtil
from gerrit_comment_extractor import CommentExtractor
from GptHelper import GptClientFactory, IGpt, GptQueryWithCheck

class ModifierWithLLM(GptQueryWithCheck):
    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "git_comment_modifier.json")

    def __init__(self, client=None, promptfile=None):
        if not promptfile:
            promptfile = self.PROMPT_FILE
        super().__init__(client, promptfile)

    def is_ok_query_result(self, query_result):
        query_result = str(query_result).strip()
        if not query_result:
            return False
        return True

    def query(self, lines, comment, relative_pos):
        if isinstance(lines, list):
            lines = "\n".join(lines)

        replace_keydata={
            "[COMMENT]": comment,
            "[RELATIVE_POSITION]": relative_pos,
            "[TARGET_LINES]": lines,
        }
        return super().query(replace_keydata)


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
    parser.add_argument('-g', '--gpt', action='store', default="openai", help='specify openai or calude3 or openaicompatible')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-p', '--promptfile', action='store', default=ModifierWithLLM.PROMPT_FILE, help='specify prompt.json')

    args = parser.parse_args()

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","), ["--comments", "--current-patch-set"])

    gpt_client = GptClientFactory.new_client(args)
    modifier = ModifierWithLLM(gpt_client, args.promptfile)

    for project, data in result.items():
        for branch, theData in data.items():
            for _data in theData:
                print(f'project:{project}')
                print(f'branch:{branch}')
                for key, value in _data.items():
                    print(f'{key}:{value}')
                print("")
                if "number" in _data and "current_patchset_ssh" in _data and _data["comments"]:
                    download_path = GerritUtil.download(args.download, _data["number"], _data["current_patchset_ssh"], args.renew)
                    comment_extractor = CommentExtractor(download_path, _data["comments"], args.marginline)
                    comment_sections = comment_extractor.get_comments()
                    for file_name, comments in comment_sections.items():
                        print(file_name)
                        for i,comment in enumerate(comments):
                            print(f'absolute_pos={comment["line_number"]}:comment={comment["message"]}:the_line={comment["target_line"]}\nrelative_pos={comment["relative_pos"]}')
                            print("\n".join(comment["section_lines"]))

                            result, response = modifier.query(comment["section_lines"], comment["message"], comment["relative_pos"])
                            print(result)


if __name__ == "__main__":
    main()
