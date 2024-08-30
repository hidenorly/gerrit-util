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

    def _find_front_fallback(input_src_lines, replace_lines, pre_margin_index):
        return ApplierUtil._find_tail_fallback(input_src_lines, replace_lines, -1, -1)

    def _find_tail_fallback(input_src_lines, replace_lines, replace_start_index, post_margin_index):
        new_replace_end_index = None
        new_post_margin_index = None

        replace_lines_length = len(replace_lines)
        input_src_lines_length = len(input_src_lines)

        is_found = False
        found_count = 0
        for i in range(replace_start_index+1, replace_lines_length):
            _replace_line = replace_lines[i]
            if not _replace_line.strip():
                continue
            _is_found = False
            for m in range(post_margin_index+1, input_src_lines_length):
                _input_line = input_src_lines[m]
                if not _input_line.strip():
                    continue
                if _input_line == _replace_line:
                    is_found = True
                    _is_found = True
                    new_replace_end_index = i
                    new_post_margin_index = m
                    found_count += 1
                    break
            if not _is_found and is_found:
                break

        if not is_found or found_count<2:
            new_post_margin_index = None
            new_replace_end_index = None

        return new_post_margin_index, new_replace_end_index


    def _replace_conflict_section_fallback(input_src_lines, replace_lines, start_index, end_index, _find_front, _find_tail):
        # fallback mode
        pre_margin_index = start_index - 1
        post_margin_index = end_index + 1

        # Find the first and last common margin lines
        pre_margin_index, replace_start_index = _find_front(input_src_lines, replace_lines, pre_margin_index)
        print(f"[ApplierUtil]:pre_margin_index={pre_margin_index}, len(input_src_lines)={len(input_src_lines)}, replace_start_index={replace_start_index}, len(replace_lines)={len(replace_lines)}")
        if pre_margin_index == None or replace_start_index == None:
            print(f"[ApplierUtil]:NOT FOUND pre_margin_index/replace_start_index!!!!")
            return input_src_lines, replace_lines, False

        post_margin_index, replace_end_index = _find_tail(input_src_lines, replace_lines, replace_start_index, max(pre_margin_index, post_margin_index))
        print(f"[ApplierUtil]:post_margin_index={post_margin_index}, replace_end_index={replace_end_index}")
        if post_margin_index == None or replace_end_index == None:
            print(f"[ApplierUtil]:NOT FOUND post_margin_index/replace_end_index!!!!")
            return input_src_lines, replace_lines, False

        if pre_margin_index>post_margin_index or replace_start_index>replace_end_index:
            print(f"[ApplierUtil]:Error. incompatible found index")
            return input_src_lines, replace_lines, False

        # Replace the conflict section with the resolved lines
        output_lines = (
            input_src_lines[:pre_margin_index] +
            replace_lines[replace_start_index:replace_end_index] +
            input_src_lines[post_margin_index:]
        )
        _replace_lines = replace_lines[:replace_start_index] + replace_lines[replace_end_index+1:]

        print(f"[ApplierUtil]:SUCCESS to replace (PARTIAL REPLACE)")

        return output_lines, _replace_lines, len(replace_lines)!=0


    def _search_start_end_pos(input_src_lines, info):
        start_index = None
        end_index = None
        margined_start_index = None
        margined_end_index = None

        # Identify conflict start and end
        start_markers = ["<<<<<<<"]
        end_markers = [">>>>>>>"]
        if len(info) == 6:
            start_markers = info[4]
            end_markers = info[5]
        #print(f"{start_markers=}")
        #print(f"{end_markers=}")

        start_markers_index = 0
        start_markers_length = len(start_markers)
        is_found_start_marker = False

        end_markers_index = 0
        end_markers_length = len(end_markers)
        is_found_end_marker = False

        for i, line in enumerate(input_src_lines):
            if not is_found_start_marker: # mode to search start markers
                if start_markers_index<start_markers_length and line.startswith(start_markers[start_markers_index]):
                    start_index = i
                    start_markers_index += 1
                    if start_markers_index == start_markers_length:
                        is_found_start_marker = True
                else:
                    start_markers_index = 0
            elif is_found_start_marker: # mode to search end markers
                if end_markers_index<end_markers_length and line.startswith(end_markers[end_markers_index]):
                    end_index = i
                    end_markers_index += 1
                    if end_markers_index == end_markers_length:
                        is_found_end_marker = True
                        break
                else:
                    end_markers_index = 0

        if is_found_start_marker and is_found_end_marker:
            margined_start_index = start_index - start_markers_length + 1
            margined_end_index = end_index + 1
            end_index = end_index - end_markers_length + 1
        else:
            if start_markers_index==0:
                start_index = None
            if end_markers_index==0:
                end_index = None
            margined_start_index = None
            margined_end_index = None

        return start_index, end_index, margined_start_index, margined_end_index

    def _replace_conflict_section(input_src_lines, replace_lines, info = None):
        start_index, end_index, pre_margin_index, post_margin_index = ApplierUtil._search_start_end_pos(input_src_lines, info)
        print(f"[ApplierUtil]:start_index={start_index}, end_index={end_index}")
        print(f"[ApplierUtil]:pre_margin_index={pre_margin_index}, post_margin_index={post_margin_index}")

        # Ensure conflict markers are found
        if start_index is None or end_index is None:
            print(f"[ApplierUtil]:NOT FOUND start_index/end_index!!!!")
            return input_src_lines, replace_lines, True

        if pre_margin_index!=None and post_margin_index!=None and pre_margin_index<start_index and end_index<post_margin_index:
            input_src_lines_length = len(input_src_lines)
            replace_lines_length = len(replace_lines)
            if input_src_lines_length and replace_lines_length and input_src_lines[min(pre_margin_index+1, input_src_lines_length)].split() == replace_lines[0].split() and input_src_lines[max(post_margin_index-1,0)].split() == replace_lines[replace_lines_length].split():
                # Replace the conflict section with the resolved lines
                output_lines = (
                    input_src_lines[:pre_margin_index] +
                    replace_lines +
                    input_src_lines[post_margin_index:]
                )
                print(f"[ApplierUtil]:SUCCESS to replace (FULL REPLACE)")

                return output_lines, [], False

        return ApplierUtil._replace_conflict_section_fallback(input_src_lines, replace_lines, start_index, end_index, ApplierUtil._find_front, ApplierUtil._find_tail)


    def replace_conflict_section(input_src_lines, replace_lines, info = None):
        """
        Replace the conflict section in input_src_lines with the resolved lines from replace_lines, considering margin lines.

        :param input_src_lines: List of strings representing the lines of the input source code with merge conflicts
        
        :param replace_lines: List of strings representing the resolved lines that replace the conflict section

        :return: List of strings
        """
        result, _, _ = ApplierUtil._replace_conflict_section(input_src_lines, replace_lines, info)
        return result


    def replace_conflict_section_ex(input_src_lines, replace_lines, info = None):
        input_src_lines, replace_lines, may_next = ApplierUtil._replace_conflict_section(input_src_lines, replace_lines, info)
        #may_next = True # for debug
        count = 0
        while(may_next):
            print(f"[ApplierUtil]fallback {count=}")
            #_ = "\n".join(input_src_lines)
            #print("input_src_lines:\n"+_)
            __ = "\n".join(replace_lines)
            print("replace_lines:\n"+__)
            input_src_lines, replace_lines, may_next = ApplierUtil._replace_conflict_section_fallback(input_src_lines, replace_lines, 0, 0, ApplierUtil._find_front_fallback, ApplierUtil._find_tail_fallback)
            count += 1
        return input_src_lines

