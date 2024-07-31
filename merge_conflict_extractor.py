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

def main():
    parser = argparse.ArgumentParser(description='Extract merge conflict for downloaded gerrit patch')
    parser.add_argument('-t', '--target', default='gerrit-ssh', help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default='main', help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-d', '--download', default='.', help='Specify download path')
    parser.add_argument('-r', '--renew', default=False, action='store_true', help='Specify if re-download anyway')
    args = parser.parse_args()

    result = GerritUtil.query(args.target, args.branch, args.status, args.since)
    for project, data in result.items():
        for branch, theData in data.items():
            for _data in theData:
                print(f'project:{project}')
                print(f'branch:{branch}')
                for key, value in _data.items():
                    print(f'{key}:{value}')
                print("")
                GitUtil.download(args.download, _data["number"], _data["patchset1_ssh"], args.renew)

if __name__ == "__main__":
    main()
