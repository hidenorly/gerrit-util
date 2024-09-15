# gerrit-util

```
python3 gerrit_merge_conflict_resolution_applier_with_upload.py --help
usage: gerrit_merge_conflict_resolution_applier_with_upload.py
       [-h] [-t TARGET] [-b BRANCH] [-s STATUS] [--since SINCE] [-n NUMBERS]
       [-w DOWNLOAD] [-r] [-m MARGINLINE] [-l] [-c] [-g GPT] [-k APIKEY]
       [-y SECRETKEY] [-e ENDPOINT] [-d DEPLOYMENT] [-p PROMPTFILE] [-a] [-u]

Extract merge conflict for downloaded gerrit patch

options:
  -h, --help            show this help message and exit
  -t TARGET, --target TARGET
                        Specify ssh target host
  -b BRANCH, --branch BRANCH
                        Branch to query
  -s STATUS, --status STATUS
                        Status to query (merged|open)
  --since SINCE         Since when to query
  -n NUMBERS, --numbers NUMBERS
                        Specify gerrit numbers with ,
  -w DOWNLOAD, --download DOWNLOAD
                        Specify download path
  -r, --renew           Specify if re-download anyway
  -m MARGINLINE, --marginline MARGINLINE
                        Specify margin lines
  -l, --largerconflictsection
                        Specify if unify overwrapped sections
  -c, --useclaude       specify if you want to use calude3 (force to use
                        claude3 for option backward compatibiliy)
  -g GPT, --gpt GPT     specify openai or calude3 or openaicompatible
  -k APIKEY, --apikey APIKEY
                        specify your API key or set it in AZURE_OPENAI_API_KEY
                        env
  -y SECRETKEY, --secretkey SECRETKEY
                        specify your secret key or set it in
                        AWS_SECRET_ACCESS_KEY env (for claude3)
  -e ENDPOINT, --endpoint ENDPOINT
                        specify your end point or set it in
                        AZURE_OPENAI_ENDPOINT env
  -d DEPLOYMENT, --deployment DEPLOYMENT
                        specify deployment name or set it in
                        AZURE_OPENAI_DEPLOYMENT_NAME env
  -p PROMPTFILE, --promptfile PROMPTFILE
                        specify prompt.json
  -a, --apply           Specify if apply the modification for the conflicted
                        file
  -u, --upload          Specify if upload the the conflict resolved result
```
