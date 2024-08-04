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

from gerrit_query import GerritUtil
from gerrit_patch_downloader import GitUtil
from gerrit_merge_conflict_extractor import ConflictExtractor
from gerrit_merge_conflict_solver import MergeConflictSolver

class MergeConflictResolutionApplier:
    def __init__(self):
        pass

    def read_file(self, file_path):
        lines = []
        with open(file_path, 'r') as f:
            lines = f.read().splitlines()
        return lines

    def get_code_section(self, lines):
        results = []

        if not isinstance(lines, list):
            lines = lines.split("\n")

        start_pos = None
        for i in range(0, len(lines)):
            line = lines[i]
            if start_pos==None and (line.startswith("```") or line.startswith("++ b/")):
                start_pos = i
            elif start_pos!=None and line.startswith("```"):
                results.append( lines[start_pos+1:i] )
                start_pos = None
        if not results:
            results = [lines]

        return results

    def get_conflicted_pos_sections(self, lines):
        conflicted_sections = []

        conflict_start = None
        for i, line in enumerate(lines):
            if line.startswith('<<<<<<< '):
                conflict_start = i
            elif line.startswith('>>>>>>> '):
                if conflict_start!=None:
                    conflicted_sections.append([conflict_start, i])
                    conflict_start = None

        return conflicted_sections


    def check_conflicted_section_with_target_diff(self, conflicted_section_lines, diff_lines):
        stripped_conflict_section = [re.sub(r'<<<<<<<\s*\w*|=======|>>>>>>> \s*\w*', '', line) for line in conflicted_section_lines]
        stripped_diff_section = [line[1:].strip('\n') if line.startswith('-') else line.strip('\n') for line in diff_lines]

        if any(line in ''.join(stripped_conflict_section) for line in stripped_diff_section):
            return True

        return False

    def apply_diff(self, conflicted_section_lines, diff_lines):
        resolved_lines = []

        for line in diff_lines:
            _line = None
            if line.startswith('+'):
                _line = " "+line[1:]
            elif line.startswith('-'):
                pass
            else:
                _line = line
            if _line!=None:
                resolved_lines.append(_line)

        return resolved_lines

    def clean_up_resolution_diff(self, resolution_diff_lines, merge_conflict_lines, conflicted_sections, margin=50):
        _resolution_diff_lines = resolution_diff_lines
        if conflicted_sections:
            for conflict_start, conflict_end in conflicted_sections:
                start_pos = max(0, conflict_start-margin)
                end_pos = min(len(merge_conflict_lines), conflict_end+margin)

                # for front
                last_found = None
                for d in range(0, len(resolution_diff_lines)):
                    diff_start_line = resolution_diff_lines[d].strip()
                    for i in range(start_pos, conflict_start):
                        if merge_conflict_lines[i].strip() == diff_start_line:
                            last_found = d
                            start_pos = i
                    if last_found == None:
                        break
                if last_found!=None:
                    last_found=min(len(resolution_diff_lines), last_found+1)
                    resolution_diff_lines = resolution_diff_lines[last_found:]

                # for last
                last_found = None
                for d in range(0, len(resolution_diff_lines)):
                    diff_start_line = resolution_diff_lines[d].strip()
                    for i in range(conflict_end, end_pos):
                        if merge_conflict_lines[i].strip() == diff_start_line:
                            last_found = d
                            break
                    if last_found!=None:
                        break
                if last_found!=None:
                    resolution_diff_lines = resolution_diff_lines[:last_found]

        return resolution_diff_lines

    def solve_merge_conflict(self, current_file_line, conflicted_sections, resolution_diff_lines):
        resolved_lines = []

        if conflicted_sections:
            length_conflict_lines = len(current_file_line)
            _conflicted_sections = self.get_conflicted_pos_sections(current_file_line)
            _resolution_diff_lines = self.clean_up_resolution_diff(resolution_diff_lines, current_file_line, _conflicted_sections)

            last_conflicted_section = 0
            for conflict_start, conflict_end in _conflicted_sections:
                # last_conflicted_section - conflict_start
                resolved_lines.extend( current_file_line[last_conflicted_section:conflict_start] )

                last_conflicted_section = conflict_end = min(conflict_end+1, length_conflict_lines)
                conflicted_section_lines = current_file_line[conflict_start:conflict_end]

                # add resolved conflicted section
                if self.check_conflicted_section_with_target_diff(conflicted_section_lines, resolution_diff_lines):
                    # found target diff section
                    resolved_section = self.apply_diff(conflicted_section_lines, _resolution_diff_lines)
                    resolved_lines.extend(resolved_section)
                else:
                    # this is not target section
                    resolved_lines.extend(conflicted_section_lines)

            # add remaining part (last_conflicted_section-end)
            resolved_lines.extend(current_file_line[last_conflicted_section:])
        else:
            resolved_lines = current_file_line

        return resolved_lines


class FileUtils:
    def get_file_line_end_code(file_path):
        result = '\n'
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                data = file.read()

            newline_counts = {
                '\r\n': 0,
                '\r': 0,
                '\n': 0
            }

            i = 0
            _length = len(data)
            while i < _length:
                if data[i:i+2] == b'\r\n':
                    newline_counts['\r\n'] += 1
                    i += 2
                    if i >= _length:
                        break
                elif data[i] == 0x0d:
                    newline_counts['\r'] += 1
                    i += 1
                elif data[i] == 0x0a:
                    newline_counts['\n'] += 1
                    i += 1
                else:
                    i += 1

            result = max(newline_counts, key=newline_counts.get)
        return result

    def save_modified_code(file_path, modified_lines):
        line_end_code = FileUtils.get_file_line_end_code(file_path)
        with open(file_path, 'w') as file:
            file.write(line_end_code.join(modified_lines))


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
    parser.add_argument('-a', '--apply', action='store_true', default=False, help='Specify if apply the modification for the conflicted file')

    args = parser.parse_args()

    solver = MergeConflictSolver(args.apikey, args.endpoint, "2024-02-01", args.deployment, args.promptfile)
    applier = MergeConflictResolutionApplier()

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
                    # get resolutions for each conflicted area
                    resolutions = []
                    for i,section in enumerate(sections):
                        print(f'---conflict_section---{i}')
                        print(section)
                        resolution, _full_response = solver.query(section)
                        print(f'---resolution---{i}')
                        print(resolution)
                        codes = applier.get_code_section(resolution)
                        resolutions.extend( codes )

                    # apply resolutions for the file
                    target_file_lines = applier.read_file(file_name)
                    for resolution in resolutions:
                        target_file_lines = applier.solve_merge_conflict(target_file_lines, sections, resolution)
                    print(f'---resolved_full_file---{file_name}')
                    print('\n'.join(target_file_lines))
                    if args.apply:
                        FileUtils.save_modified_code(file_name, target_file_lines)


if __name__ == "__main__":
    main()
