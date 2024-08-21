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
import json
import argparse
from datetime import datetime, timedelta

class GerritUtil:
    @staticmethod
    def parse_since(since):
        if since.endswith('ago'):
            num, unit = since.split()[0:2]
            num = int(num)
            if unit in ['day', 'days']:
                delta = timedelta(days=num)
            elif unit in ['week', 'weeks']:
                delta = timedelta(weeks=num)
            elif unit in ['month', 'months']:
                delta = timedelta(days=num*30)
            elif unit in ['year', 'years']:
                delta = timedelta(days=num*365)
            else:
                raise ValueError(f"Unsupported time unit: {unit}")
            date = datetime.now() - delta
        else:
            date = datetime.strptime(since, "%Y-%m-%d")
        return date.strftime("%Y-%m-%d %H:%M:%S +0900")

    @staticmethod
    def query(ssh_target_host, branch, status, since, numbers):
        result = {}
        status_query = ' OR '.join(f'status:{s}' for s in status.split('|'))
        since_date = GerritUtil.parse_since(since)

        cmd = [
            'ssh', ssh_target_host, 'gerrit', 'query', '--format=json'
        ]
        is_number = False
        for number in numbers:
            if number:
                cmd.append(number)
                is_number = True

        if not is_number:
            cmd.extend([
                f'branch:{branch}',
                f'AND ({status_query})',
                f'\'AND after:\"{since_date}\"\'',
            ])

        _result = subprocess.run(cmd, capture_output=True, text=True)
        
        for line in _result.stdout.splitlines():
            try:
                data = json.loads(line)
                if 'project' in data:
                    project = data['project']
                    branch = data['branch']
                    if not project in result:
                        result[project] = {}
                    if not branch in result[project]:
                        result[project][branch] = []

                    id = str(data[('number')])
                    url = data['url']
                    pos = url.find("/c/")
                    pos2 = project.rfind("/")
                    project_dir = project[pos2+1:]
                    theData = {
                        "number": id,
                        "Change-Id": data['id'],
                        "subject": data['subject'],
                        "status": data['status'],
                        "url": data['url'],
                        "Created": datetime.fromtimestamp(data['createdOn']),
                        "project_dir": project_dir,
                        "Last Updated": datetime.fromtimestamp(data['lastUpdated']),
                        "patchset1_ssh": f'git clone {url[0:pos]}/{project} -b {branch}; cd {project_dir}; git pull {url[0:pos]}/{project} refs/changes/{id[len(id)-2:]}/{id}/1 --rebase',
                        "patchset1_repo": f'repo download {project} {id}/1'
                    }
                    result[project][branch].append(theData)

            except json.JSONDecodeError:
                continue

        return result


def main():
    parser = argparse.ArgumentParser(description='Query Gerrit and parse results')
    parser.add_argument('-t', '--target', default=os.getenv("GERRIT_HOST", 'gerrit-ssh'), help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default=os.getenv("GERRIT_BRANCH", 'main'), help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-n', '--numbers', default="", action='store', help='Specify gerrit numbers with ,')
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

if __name__ == "__main__":
    main()