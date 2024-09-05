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
import argparse
from GerritUtil import GerritUtil

def main():
    parser = argparse.ArgumentParser(description='Query Gerrit and parse results')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-n', '--numbers', default="", action='store', help='Specify gerrit numbers with ,')
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

if __name__ == "__main__":
    main()