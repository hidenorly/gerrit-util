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

class CommentExtractor:
    def __init__(self, path, comments, margin_line_count=10):
        self.path = path
        self.comments = comments
        self.margin_line_count = margin_line_count

    def get_margined_lines(self, file_lines, pos):
        start_pos = max(0, pos - self.margin_line_count)
        end_pos = min(pos + self.margin_line_count, len(file_lines))
        return file_lines[start_pos:end_pos], pos-start_pos, file_lines[pos], start_pos, end_pos

    def _remove_comments(self, input_comments, exclude_filename, exclude_line_number, exclude_target_pos):
        result_comments = {}
        for filename, comments in input_comments.items():
            if filename!=exclude_filename:
                result_comments[filename] = comments
            else:
                for comment in comments:
                    if comment[0] != exclude_line_number or comment[2] != exclude_target_pos:
                        if not filename in result_comments:
                            result_comments[filename] = []
                        result_comments[filename].append(comment)
        return result_comments

    def get_comments(self, exclude_done = True):
        comments = {}
        exclude_targets = []

        for filename, comment in self.comments.items():
            if filename != '/PATCHSET_LEVEL':
                file_lines = FileUtil.read_file(os.path.join(self.path, filename))
                for line_number, _comments in comment.items():
                    if not filename in comments:
                        comments[filename] = []
                    for _comment in _comments:
                        message = _comment["message"]
                        focused_lines, target_pos, target_line, start_pos, end_pos = self.get_margined_lines(file_lines, int(line_number))
                        if exclude_done and str(message).strip().upper()=="DONE":
                            exclude_targets.append([filename, line_number, target_pos])
                        else:
                            comments[filename].append({
                                "line_number":line_number,
                                "message":message,
                                "relative_pos":target_pos,
                                "target_line":target_line,
                                "section_lines":focused_lines,
                                "start_pos":start_pos,
                                "end_pos":end_pos
                            })

        if exclude_done:
            for an_exclude in exclude_targets:
                comments = self._remove_comments(comments, an_exclude[0], an_exclude[1], an_exclude[2])

        return comments

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
    args = parser.parse_args()

    result = GerritUtil.query(args.target, args.branch, args.status, args.since, args.numbers.split(","), ["--comments", "--current-patch-set"])
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

if __name__ == "__main__":
    main()
