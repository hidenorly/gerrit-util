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
import argparse
import shutil
from datetime import datetime, timedelta
from gerrit_query import GerritUtil

class GitUtil:
    def download(base_dir, id, download_cmd, force_renew = False):
        target_folder = os.path.join(base_dir, str(id))

        # remove folder if force_renew
        if force_renew and os.path.exists(target_folder):
            shutil.rmtree(target_folder)

        # ensure target_folder
        os.makedirs(target_folder, exist_ok=True)
        current_dir = target_folder

        commands = download_cmd.split(';')
        for command in commands:
            command = command.strip()
            if command.startswith('cd'):
                # Change directory command
                new_dir = command[3:].strip()
                current_dir = os.path.join(current_dir, new_dir)
            else:
                # Execute other commands
                try:
                    subprocess.run(command, shell=True, check=True, cwd=current_dir)
                except:
                    pass

        return target_folder

def main():
    parser = argparse.ArgumentParser(description='Download gerrit patch')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
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