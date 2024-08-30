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

class FileUtil:
    def read_file(file_path):
        lines = []
        with open(file_path, 'r') as f:
            lines = f.read().splitlines()
        return lines

    def get_file_line_end_code(file_path):
        result = '\n'
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                data = file.read()

            newline_counts = {
                '\n': 0,
                '\r': 0,
                '\r\n': 0
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
        line_end_code = FileUtil.get_file_line_end_code(file_path)
        with open(file_path, 'w') as file:
            file.write(line_end_code.join(modified_lines))
