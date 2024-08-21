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

class ApplierUtil:
    def _find_front(input_src_lines, replace_lines, pre_margin_index):
        replace_start_index = 0
        new_pre_margin_index = pre_margin_index

        replace_search_end_index = len(replace_lines) - 1

        is_found = False
        for m in range(0, pre_margin_index):
            _input_search_index = pre_margin_index - m
            _input_line = input_src_lines[_input_search_index].strip()
            _is_found = False
            for i in range(0, replace_search_end_index+1):
                _replace_search_index = replace_search_end_index - i
                _replace_line = replace_lines[_replace_search_index].strip()
                if _input_line == _replace_line:
                    is_found = True
                    _is_found = True
                    replace_start_index = _replace_search_index
                    replace_search_end_index = _replace_search_index
                    new_pre_margin_index = _input_search_index
                    break
            if not _is_found:
                break

        if not is_found:
            new_pre_margin_index = None
            replace_start_index = None

        return new_pre_margin_index, replace_start_index


    def _find_tail(input_src_lines, replace_lines, replace_start_index, post_margin_index):
        replace_end_index = len(replace_lines) - 1
        new_replace_end_index = replace_start_index
        new_post_margin_index = post_margin_index

        is_found = False
        for _input_search_index in range(post_margin_index, len(input_src_lines)):
            _input_line = input_src_lines[_input_search_index].strip()
            _is_found = False
            for _replace_search_index in range(new_replace_end_index, replace_end_index):
                _replace_line = replace_lines[_replace_search_index].strip()
                if _input_line == _replace_line:
                    is_found = True
                    _is_found = True
                    new_replace_end_index = _replace_search_index
                    new_post_margin_index = _input_search_index
                    break
            if not _is_found:
                break

        if not is_found:
            new_post_margin_index = None
            new_replace_end_index = None

        return new_post_margin_index, new_replace_end_index


    def replace_conflict_section(input_src_lines, replace_lines):
        """
        Replace the conflict section in input_src_lines with the resolved lines from replace_lines, considering margin lines.

        :param input_src_lines: List of strings representing the lines of the input source code with merge conflicts
        
        :param replace_lines: List of strings representing the resolved lines that replace the conflict section

        :return: List of strings
        """
        start_index = None
        end_index = None

        # Identify conflict start and end
        for i, line in enumerate(input_src_lines):
            if line.startswith("<<<<<<<"):
                start_index = i
            elif line.startswith(">>>>>>>"):
                end_index = i
                break

        print(f"[ApplierUtil]:start_index={start_index}, end_index={end_index}")

        # Ensure conflict markers are found
        if start_index is None or end_index is None:
            return input_src_lines

        # Scan for common margin lines at the beginning and end
        pre_margin_index = start_index - 1
        post_margin_index = end_index + 1

        # Find the first and last common margin lines
        pre_margin_index, replace_start_index = ApplierUtil._find_front(input_src_lines, replace_lines, pre_margin_index)
        print(f"[ApplierUtil]:pre_margin_index={pre_margin_index}, post_margin_index={post_margin_index}")
        if pre_margin_index == None or replace_start_index == None:
            return input_src_lines
        post_margin_index, replace_end_index = ApplierUtil._find_tail(input_src_lines, replace_lines, replace_start_index, post_margin_index)
        print(f"[ApplierUtil]:replace_start_index={replace_start_index}, replace_end_index={replace_end_index}")
        if post_margin_index == None or replace_end_index == None:
            return input_src_lines

        # Replace the conflict section with the resolved lines
        output_lines = (
            input_src_lines[:pre_margin_index] +
            replace_lines[replace_start_index:replace_end_index] +
            input_src_lines[post_margin_index:]
        )

        #print(f"[ApplierUtil]:SUCCESS to replace")

        return output_lines