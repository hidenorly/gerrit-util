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
import subprocess
import json
import shutil
from datetime import datetime, timedelta
from ExecUtil import ExecUtil

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
    def _parse_gerrt_result(result_lines):
        project = None
        branch = None
        theData = {}

        try:
            data = json.loads(result_lines)
            if 'project' in data:
                project = data['project']
                branch = data['branch']

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
                    "patchset1_repo": f'repo download {project} {id}/1',
                    "comments": {}
                }
                if "currentPatchSet" in data and "ref" in data["currentPatchSet"]:
                    current_patch_set_ref = data["currentPatchSet"]["ref"]
                    theData["current_patchset_ssh"] = f'git clone {url[0:pos]}/{project} -b {branch}; cd {project_dir}; git pull {url[0:pos]}/{project} {current_patch_set_ref} --rebase'

                    if "comments" in data["currentPatchSet"]:
                        _comments = data["currentPatchSet"]["comments"]
                        comments = theData["comments"]
                        for comment in _comments:
                            filename = comment["file"]
                            if not filename in comments:
                                comments[filename] = {}
                            line = comment["line"]
                            if not line in comments[filename]:
                                comments[filename][line] = []
                            comments[filename][line].append(
                                {
                                    "message": comment["message"],
                                    "reviewer": comment["reviewer"]
                                }
                            )


        except json.JSONDecodeError:
            pass

        return project, branch, theData


    @staticmethod
    def query(ssh_target_host, branch, status, since, numbers, extra_commands=[], connection="http"):
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

        if extra_commands:
            cmd.extend(extra_commands)

        _result = subprocess.run(cmd, capture_output=True, text=True)
        
        for line in _result.stdout.splitlines():
            project, branch, theData = GerritUtil._parse_gerrt_result(line)
            if project:
                if not project in result:
                    result[project] = {}
                if not branch in result[project]:
                    result[project][branch] = []

                if "current_patchset_ssh" in theData:
                    current_patchset_ssh = theData["current_patchset_ssh"]
                    if not connection in current_patchset_ssh:
                        # mismatch case
                        theData["current_patchset_ssh"] = re.sub(r'http://[^/]+/', "ssh://"+ssh_target_host + '/', current_patchset_ssh)
                if "patchset1_ssh" in theData:
                    patchset1_ssh = theData["patchset1_ssh"]
                    if not connection in patchset1_ssh:
                        # mismatch case
                        theData["patchset1_ssh"] = re.sub(r'http://[^/]+/', "ssh://"+ssh_target_host + '/', patchset1_ssh)
                result[project][branch].append(theData)

        return result

    @staticmethod
    def download(base_dir, id, download_cmd, force_renew = False):
        target_folder = os.path.join(base_dir, str(id))

        # remove folder if force_renew
        if force_renew and os.path.exists(target_folder):
            shutil.rmtree(target_folder)

        # ensure target_folder
        os.makedirs(target_folder, exist_ok=True)
        current_dir = target_folder

        current_dir = ExecUtil.exec_cmd_with_cd(download_cmd, target_folder)

        return current_dir

    @staticmethod
    def upload(target_folder, branch):
        upload_cmd = f"git add *; git commit --amend --no-edit; git push origin HEAD:refs/for/{branch}"

        # check the target_folder is git folder
        if os.path.exists(os.path.join(target_folder+"/.git")):
            ExecUtil.exec_cmd_with_cd(upload_cmd, target_folder)

        return target_folder
