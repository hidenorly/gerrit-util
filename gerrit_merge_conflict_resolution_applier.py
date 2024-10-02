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
from GptHelper import GptClientFactory
from gerrit_merge_conflict_extractor import ConflictExtractor
from gerrit_merge_conflict_solver import MergeConflictSolver
from ApplierUtil import ApplierUtil
from FileUtil import FileUtil

class MergeConflictResolutionApplier:
    def __init__(self, margin_line_count):
        self.margin_line_count = margin_line_count
        pass

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


    def just_in_case_cleanup(self, resolved_lines):
        isModified = False
        result = []
        for line in resolved_lines:
            _line = line.strip()
            if _line.startswith("+") or _line.startswith("-"):
                _line = _line[1:].strip()
            if _line.startswith(">>>>>>> ") or _line.strip()=="=======" or _line.startswith("<<<<<<< "):
                isModified = True
                pass
            else:
                result.append(line)
        return result, isModified

    def is_diff(self, diff_lines):
        result = False
        for line in diff_lines:
            if line.startswith(("+","-")):
                result = True
                break
        return result


    def solve_merge_conflict(self, current_file_lines, conflicted_sections, resolution_diff_lines, resolutions, resolutions_mapper):
        result = None

        # clean up unnecessary markers such as @, etc.
        resolution_diff_lines = self.clean_up_diff(resolution_diff_lines)

        # --- try with diff
        resolved_lines_as_entire_diff = self.apply_true_diff(current_file_lines, resolution_diff_lines)
        _, is_modified_resolved_lines_as_entire_diff = self.just_in_case_cleanup(resolved_lines_as_entire_diff)

        # --- try with replacer per section
        # create replace sections
        is_diff_section_found = False
        replace_sections=[]
        length_resolutions = len(resolutions)
        length_conflicted_sections = len(conflicted_sections)
        if length_resolutions == length_conflicted_sections:
            for i in range(0, length_resolutions):
                _resolution_lines = resolutions[i]
                _conflict_section = conflicted_sections[i]

                if self.is_diff(_resolution_lines):
                    # if diff_case (+/-), convert it to replace_section
                    #print(f"solve_merge_conflict: FOUND DIFF\n{_resolution_lines}")
                    replace_sections.append( self.apply_true_diff(_conflict_section, _resolution_lines) )
                    is_diff_section_found = True
                else:
                    # no diff, it should be replace_section
                    #print(f"solve_merge_conflict: FOUND REPLACE SECTION\n{_resolution_lines}")
                    replace_sections.append( _resolution_lines )

        # replace current_file_lines with replace_sections
        for replace_section_lines in replace_sections:
            #print(f"solve_merge_conflict: TRY to REPLACE the SECTION:\n{replace_section_lines}")
            info = None
            flatten_replace_section_lines = str(replace_section_lines)
            if flatten_replace_section_lines in resolutions_mapper:
                info = resolutions_mapper[flatten_replace_section_lines]
            _replace_section_lines = self.clean_up_diff(replace_section_lines)
            current_file_lines = ApplierUtil.replace_conflict_section_ex(current_file_lines, _replace_section_lines, info)
            #print("\nRESOLVED CODE is ")
            #print("\n".join(current_file_lines))
        resolved_lines_as_replacer = current_file_lines
        _, is_modified_resolved_lines_as_replacer = self.just_in_case_cleanup(resolved_lines_as_replacer)

        result = resolved_lines_as_replacer # default

        # check with the best result
        if not is_modified_resolved_lines_as_entire_diff:
            result = resolved_lines_as_entire_diff
            if is_diff_section_found:
                return result
        if not is_modified_resolved_lines_as_replacer:
            result = resolved_lines_as_replacer
        # TODO: If not full, result should be None as failure...

        return result


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
    parser.add_argument('-g', '--gpt', action='store', default="openai", help='specify openai or calude3 or openaicompatible')
    parser.add_argument('-k', '--apikey', action='store', default=None, help='specify your API key or set it in AZURE_OPENAI_API_KEY env')
    parser.add_argument('-y', '--secretkey', action='store', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)')
    parser.add_argument('-e', '--endpoint', action='store', default=None, help='specify your end point or set it in AZURE_OPENAI_ENDPOINT env')
    parser.add_argument('-d', '--deployment', action='store', default=None, help='specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env')
    parser.add_argument('-p', '--promptfile', action='store', default="./git_merge_conflict_resolution_for_upstream_integration.json", help='specify prompt.json')

    parser.add_argument('-a', '--apply', action='store_true', default=False, help='Specify if apply the modification for the conflicted file')

    args = parser.parse_args()

    gpt_client = GptClientFactory.new_client(args)
    solver = MergeConflictSolver(gpt_client, args.promptfile)
    applier = MergeConflictResolutionApplier(args.marginline)

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
                    target_file_lines = FileUtil.read_file(file_name)
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
                        #break
                        #the following is for debug
                        #target_file_lines = _

                    #print(f'---resolved_full_file---{file_name}')
                    #print('\n'.join(target_file_lines))
                    if args.apply:
                        FileUtil.save_modified_code(file_name, target_file_lines)
                #exit()


if __name__ == "__main__":
    main()
