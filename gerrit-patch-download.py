import os
import subprocess
import json
import argparse
import shutil
from datetime import datetime, timedelta
from gerrit_query import GerritUtil

def download_git(base_dir, id, download_cmd, force_renew = False):
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
            subprocess.run(command, shell=True, check=True, cwd=current_dir)

GerritUtil.download_git = download_git

def main():
    parser = argparse.ArgumentParser(description='Download gerrit patch')
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
                GerritUtil.download(args.download, _data["id]"], _data["patchset1_ssh"], args.renew)

if __name__ == "__main__":
    main()