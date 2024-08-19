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
        replace_start_index = 0
        replace_end_index = len(replace_lines) - 1

        #while (
        #    replace_start_index <= replace_end_index and 
        #    pre_margin_index >= 0 and 
        #    input_src_lines[pre_margin_index].strip() == replace_lines[replace_start_index].strip()
        #):
        #    pre_margin_index -= 1
        #    replace_start_index += 1

        for i in range(0, len(replace_lines)):
            if input_src_lines[pre_margin_index].strip() == replace_lines[i].strip():
                replace_start_index = i
                break

        #while (
        #    replace_start_index <= replace_end_index and 
        #    post_margin_index < len(input_src_lines) and 
        #    input_src_lines[post_margin_index].strip() == replace_lines[replace_end_index].strip()
        #):
        #    post_margin_index += 1
        #    replace_end_index -= 1

        for i in range(replace_start_index, len(replace_lines)):
            if input_src_lines[post_margin_index].strip() == replace_lines[i].strip():
                replace_end_index = i

        print(f"[ApplierUtil]:pre_margin_index={pre_margin_index}, post_margin_index={post_margin_index}")
        print(f"[ApplierUtil]:replace_start_index={replace_start_index}, replace_end_index={replace_end_index}")

        ## Check if any conflict markers remain in the replacement lines
        #if any(
        #    line.startswith("<<<<<<<") or line.startswith("=======") or line.startswith(">>>>>>>") 
        #    for line in replace_lines[replace_start_index:replace_end_index + 1]
        #):
        #    return input_src_lines

        # Replace the conflict section with the resolved lines
        output_lines = (
            input_src_lines[:pre_margin_index] +
            replace_lines[replace_start_index:replace_end_index] +
            input_src_lines[post_margin_index:]
        )

        print(f"[ApplierUtil]:SUCCESS to replace")

        return output_lines