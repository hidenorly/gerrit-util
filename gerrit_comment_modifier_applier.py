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
from GptHelper import GptClientFactory, IGpt, GptQueryWithCheck
from gerrit_comment_extractor import CommentExtractor
from gerrit_comment_modifier import ModifierWithLLM
from ApplierUtil import ApplierUtil

class ResolutionApplier:
    def __init__(self, margin_line_count):
        self.margin_line_count = margin_line_count

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
                results.append( lines[start_pos+1:i] )
                start_pos = None
        if start_pos!=None:
            results.append( lines[start_pos+1:len(lines)] )
        if not results and not lines:
            print("ERROR!!!!!")
            print("\n".join(lines))
            #exit()
            results = [lines]

        return results

    def print_few_tail_lines(self, marker, lines, count):
        length = len(lines)
        start_pos = max(length-count, 0)
        print(marker)
        print("\n".join(lines[start_pos:length]))

    def clean_up_diff(self, diff_lines):
        results = []
        for line in diff_lines:
            _line = line.strip()
            if not _line.startswith(("@@@ ", "@@ ", "--- ", "+++ ")):
                results.append(line)
        return results

    def _indent_adjusted_line(self, line, prev_line):
        result = line
        line_strip = line.strip()
        line_indent = len(line) - len(line_strip)
        prev_indent = len(prev_line) - len(prev_line.strip())
        if abs(prev_indent - line_indent) <= 1:
            result = " " * prev_indent + line_strip
        return result

    def apply_true_diff(self, target_lines, diff_lines, is_prioritize_diff=False, is_loose_apply=False):
        result = []

        target_index = 0
        diff_index = 0
        target_length = len(target_lines)
        diff_length = len(diff_lines)

        is_found = False
        prev_line = ""
        while target_index < target_length and diff_index < diff_length:
            _target_line = target_lines[target_index]
            target_line = _target_line.strip()
            _diff_line = diff_lines[diff_index]
            diff_line = _diff_line.strip()

            if not diff_line.startswith(('+', '-')) and target_line == diff_line:
                # found common line
                is_found = True
                if target_line:
                    prev_line = _target_line
                result.append(_target_line)
                target_index += 1
                diff_index += 1
            elif diff_line.startswith('+') and is_found:
                # case : +
                addition = diff_lines[diff_index][1:]
                addition_strip = addition.strip()
                adjusted_line = self._indent_adjusted_line(addition, prev_line)
                result.append(adjusted_line)
                if addition_strip:
                    prev_line = adjusted_line
                diff_index += 1
            elif diff_line.startswith('-') and (is_found or is_loose_apply) and target_line == diff_line[1:].strip():
                diff_index += 1
                target_index += 1
            else:
                # case : not common line, not diff +/-
                if is_prioritize_diff and (target_index+1 < target_length) and (diff_index+1 < diff_length) and target_lines[target_index+1].strip()==diff_lines[diff_index+1].strip():
                    # Replace current target_line with the diff_line if the next lines match
                    adjusted_line = self._indent_adjusted_line(diff_lines[diff_index], prev_line)
                    result.append(adjusted_line)
                    if adjusted_line.strip():
                        prev_line = adjusted_line
                    diff_index += 1
                    target_index += 1
                    is_found = False
                else:
                    if target_line:
                        is_found = False # keep is_found=True if target_line[target_index].strip == """
                    result.append(_target_line)
                    prev_line = _target_line
                    target_index += 1

        # remaining diff_lines
        while diff_index < diff_length:
            if diff_lines[diff_index].startswith('+') and (is_found or is_loose_apply):
                adjusted_line = self._indent_adjusted_line(diff_lines[diff_index][1:], prev_line)
                result.append(adjusted_line)
                if adjusted_line.strip():
                    prev_line = adjusted_line

            diff_index += 1

        # remaining target_lines
        while target_index < target_length:
            result.append(target_lines[target_index])
            target_index += 1

        return result


    def is_diff(self, diff_lines):
        result = False
        for line in diff_lines:
            if line.startswith(("+","-")):
                result = True
                break
        return result


    def apply(self, target_file_lines, resolutions):
        result = None

        # create replace sections
        replace_sections=[]
        for resolution in resolutions:
            _target_section = resolution["target"]
            _resolution_lines = resolution["resolution"]
            _info = resolution["info"]

            if self.is_diff(_resolution_lines):
                # if diff_case (+/-), convert it to replace_section
                #print(f"solve_merge_conflict: FOUND DIFF\n{_resolution_lines}")
                replace_sections.append( [self.apply_true_diff(_target_section, _resolution_lines), _info] )
            else:
                # no diff, it should be replace_section
                #print(f"solve_merge_conflict: FOUND REPLACE SECTION\n{_resolution_lines}")
                replace_sections.append( [_resolution_lines, _info] )

        # replace target_file_lines with replace_sections
        for _replace_section in replace_sections:
            replace_section_lines = _replace_section[0]
            info = _replace_section[1]
            # Just in case
            _replace_section_lines = self.clean_up_diff(replace_section_lines)
            target_file_lines = ApplierUtil.replace_conflict_section_ex(target_file_lines, _replace_section_lines, info)

        result = target_file_lines

        return result

    def add_to_resolutions(self, target_file_lines, start_pos, end_pos, resolution, resolutions = None):
        if resolutions==None:
            resolutions = []

        if start_pos<end_pos and end_pos<=len(target_file_lines):
            target_lines = target_file_lines[start_pos:end_pos]
            code_extraced_resolutions = self.get_code_section(resolution)

            start_pos_without_margins = min(start_pos+int(self.margin_line_count/2), len(target_file_lines))
            end_pos_without_margins = max(end_pos-int(self.margin_line_count/2),0)

            info = [
                start_pos, # 0
                end_pos, # 1
                start_pos_without_margins, #2
                end_pos_without_margins # 3
            ]
            # 4: start_markers
            if start_pos<start_pos_without_margins:
                info.append(target_file_lines[start_pos:start_pos_without_margins])
            else:
                info.append([ target_file_lines[start_pos] ] )
            # 5: end_markers
            if end_pos_without_margins<end_pos:
                info.append(target_file_lines[end_pos_without_margins:end_pos])
            else:
                info.append([ target_file_lines[end_pos] ] )

            for code_resolution in code_extraced_resolutions:
                resolutions.append({
                    "target": target_lines,
                    "resolution": code_resolution,
                    "info": info
                })

        return resolutions


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

    parser.add_argument('-a', '--apply', action='store_true', default=False, help='Specify if apply the modification for the conflicted file')
    parser.add_argument('-u', '--upload', action='store_true', default=False, help='Specify if upload the the conflict resolved result')

    args = parser.parse_args()

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","), ["--comments", "--current-patch-set"])

    gpt_client = GptClientFactory.new_client(args)
    modifier = ModifierWithLLM(gpt_client, args.promptfile)
    applier = ResolutionApplier(args.marginline)

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
                        resolutions = []
                        file_full_path = os.path.join(download_path,file_name)
                        target_file_lines = FileUtil.read_file(file_full_path)
                        for i,comment in enumerate(comments):
                            print(f'absolute_pos={comment["line_number"]}:comment={comment["message"]}:the_line={comment["target_line"]}\nrelative_pos={comment["relative_pos"]}')

                            result, response = modifier.query(comment["section_lines"], comment["message"], comment["relative_pos"])
                            print(result)

                            resolutions = applier.add_to_resolutions(target_file_lines, comment["start_pos"], comment["end_pos"], result, resolutions)

                        target_file_lines = applier.apply(target_file_lines, resolutions)
                        print("applied filed:")
                        print("\n".join(target_file_lines))

                        if args.apply:
                            FileUtil.save_modified_code(file_full_path, target_file_lines)

                    if args.upload:
                        GerritUtil.upload(download_path, branch)


if __name__ == "__main__":
    main()
