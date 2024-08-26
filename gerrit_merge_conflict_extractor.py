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
import subprocess
import re
import argparse
import shutil
from datetime import datetime, timedelta
from gerrit_query import GerritUtil
from gerrit_patch_downloader import GitUtil

class ConflictExtractor:
    def __init__(self, path, margin_line_count=10, merge_overwrapped_conflict_section=True):
        self.path = path
        self.margin_line_count = margin_line_count
        self.merge_overwrapped_conflict_section = merge_overwrapped_conflict_section
        self.conflict_start_pattern = re.compile(r'^<{7}')
        self.conflict_end_pattern = re.compile(r'^>{7}')

    def _find_margin_without_another_conflict_section_forward(self, lines, i):
        target = max(0, i - self.margin_line_count)
        while i>target:
            if self.conflict_end_pattern.search(lines[i]):
                return i+1
            i -= 1
        return i

    def _find_margin_without_another_conflict_section_backward(self, lines, i, line_counts):
        target = min(line_counts, i + self.margin_line_count + 1)
        while i<target:
            if self.conflict_start_pattern.search(lines[i]):
                return i-1
            i += 1
        return i

    def _find_conflict_end(self, lines, start, line_counts):
        for i in range(start + 1, line_counts):
            if self.conflict_end_pattern.search(lines[i]):
                return i
        return None

    def _merge_sections(self, conflict_section_pos):
        merged_conflict_section_pos = []
        sorted_conflict_section_pos = sorted(conflict_section_pos, key=lambda x: x[0])
        if len(sorted_conflict_section_pos)>=2:
            merged_conflict_section_pos.append(sorted_conflict_section_pos[0])
            
            for pos in sorted_conflict_section_pos[1:]:
                if pos[0] <= merged_conflict_section_pos[-1][1]:
                    merged_conflict_section_pos[-1][1] = max(pos[1], merged_conflict_section_pos[-1][1])
                    merged_conflict_section_pos[-1][2] = min(pos[2], merged_conflict_section_pos[-1][2]) # orig_start
                    merged_conflict_section_pos[-1][3] = max(pos[3], merged_conflict_section_pos[-1][3]) # orig_end
                else:
                    merged_conflict_section_pos.append(pos)
        else:
            merged_conflict_section_pos = sorted_conflict_section_pos
        
        return merged_conflict_section_pos

    def _extract_conflicts(self, file_path):
        lines = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                pass

        conflicts = []
        i = 0
        line_counts = len(lines)
        conflict_section_pos = []
        _original_conflict_start = None
        _original_conflict_end = None
        while i < line_counts:
            if self.conflict_start_pattern.search(lines[i]):
                if not _original_conflict_start:
                    _original_conflict_start = i
                conflict_start = self._find_margin_without_another_conflict_section_forward(lines, i)
                conflict_end = self._find_conflict_end(lines, i, line_counts)
                if not _original_conflict_end:
                    _original_conflict_end = conflict_end
                if conflict_end is not None:
                    conflict_end = self._find_margin_without_another_conflict_section_backward(lines, conflict_end, line_counts)
                    conflict_section_pos.append([conflict_start, conflict_end, _original_conflict_start, _original_conflict_end])
                    _original_conflict_start = None
                    _original_conflict_end = None
                    i = conflict_end
                else:
                    i += 1
            else:
                i += 1

        if self.merge_overwrapped_conflict_section:
            conflict_section_pos = self._merge_sections(conflict_section_pos)

        for pos in conflict_section_pos:
            conflict_section = ''.join(lines[pos[0]:pos[1]])
            conflicts.append({"start":pos[0], "end":pos[1], "section": conflict_section, "orig_start":pos[2], "orig_end":pos[3]})

        return conflicts

    def get_conflicts(self):
        conflicts = {}
        for root, _, files in os.walk(self.path):
            for file in files:
                file_path = os.path.join(root, file)
                file_conflicts = self._extract_conflicts(file_path)
                if file_conflicts:
                    conflicts[file_path] = file_conflicts
        return conflicts

def main():
    parser = argparse.ArgumentParser(description='Extract merge conflict for downloaded gerrit patch')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-n', '--numbers', default="", action='store', help='Specify gerrit numbers with ,')

    parser.add_argument('-d', '--download', default='.', help='Specify download path')
    parser.add_argument('-r', '--renew', default=False, action='store_true', help='Specify if re-download anyway')
    parser.add_argument('-m', '--marginline', default=10, type=int, action='store', help='Specify margin lines')
    parser.add_argument('-l', '--largerconflictsection', default=False, action='store_true', help='Specify if unify overwrapped sections')
    args = parser.parse_args()

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","))
    for project, data in result.items():
        for branch, theData in data.items():
            for _data in theData:
                print(f'project:{project}')
                print(f'branch:{branch}')
                for key, value in _data.items():
                    print(f'{key}:{value}')
                print("")
                download_path = GitUtil.download(args.download, _data["number"], _data["patchset1_ssh"], args.renew)
                conflict_detector = ConflictExtractor(download_path, args.marginline, args.largerconflictsection)
                conflict_sections = conflict_detector.get_conflicts()
                for file_name, sections in conflict_sections.items():
                    print(file_name)
                    for i,section in enumerate(sections):
                        print(f'---section----{i}')
                        print(section["section]"])

if __name__ == "__main__":
    main()
