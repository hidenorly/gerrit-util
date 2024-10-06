# gerrit-util

Utilities for gerrit.

* gerrit_query. gerrit_comment_query : query the specific number or the condition and dump the info. incl. how to download.
* gerrit_commt_* : utilities for gerrit's comment such as extractor, modifier as the comment with LLM
* gerrit_merge_conflict_* : utilities for merge conflict in gerrit

* You can use gerrit_comment_modifier_applier.py and gerrit_merge_conflict_resolution_applier_with_upload.py for full functionalities.

* Note that ApplierUtil is under PoC then it's needed to be improved. Please contribute to improve.

# gerrit comment utility

# This is an early PoC level.

## comment query

````
$ python3 gerrit_comment_query.py --help
usage: gerrit_comment_query.py [-h] [-t TARGET] [-b BRANCH] [-s STATUS] [--since SINCE] [-n NUMBERS]

Query Gerrit and parse results

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
```

## modify as comment

```
python3 gerrit_comment_modifier_applier.py --help                                                          
usage: gerrit_comment_modifier_applier.py [-h] [-t TARGET] [-b BRANCH] [-s STATUS] [--since SINCE] [-n NUMBERS] [--connection CONNECTION]
                                          [-w DOWNLOAD] [-r] [-m MARGINLINE] [-c] [-g GPT] [-k APIKEY] [-y SECRETKEY] [-e ENDPOINT] [-d DEPLOYMENT]
                                          [-p PROMPTFILE] [-a] [-u]

Gerrit comment AI helper

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
  --connection CONNECTION
                        Specify ssh or http
  -w DOWNLOAD, --download DOWNLOAD
                        Specify download path
  -r, --renew           Specify if re-download anyway
  -m MARGINLINE, --marginline MARGINLINE
                        Specify margin lines
  -c, --useclaude       specify if you want to use calude3
  -g GPT, --gpt GPT     specify openai or calude3 or openaicompatible
  -k APIKEY, --apikey APIKEY
                        specify your API key or set it in AZURE_OPENAI_API_KEY env
  -y SECRETKEY, --secretkey SECRETKEY
                        specify your secret key or set it in AWS_SECRET_ACCESS_KEY env (for claude3)
  -e ENDPOINT, --endpoint ENDPOINT
                        specify your end point or set it in AZURE_OPENAI_ENDPOINT env
  -d DEPLOYMENT, --deployment DEPLOYMENT
                        specify deployment name or set it in AZURE_OPENAI_DEPLOYMENT_NAME env
  -p PROMPTFILE, --promptfile PROMPTFILE
                        specify prompt.json
  -a, --apply           Specify if apply the modification for the conflicted file
  -u, --upload          Specify if upload the the conflict resolved result
```

example

```
python3 gerrit_comment_modifier_applier.py -t gerrit -n 1 -r -a -m 10 -c -p git_comment_modifier.json --connection=ssh -u
```


# merge conflict resolver for gerrit

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

## Use Claude3, margin 10 lines, apply the resolution, Specifying the prompt

```
python3 gerrit_merge_conflict_resolution_applier_with_upload.py -n ChangeNumber -a -r -m 10 -c -p git_merge_conflict_resolution_for_upstream_integration_keep_downstream.json -l -u
```

## Use OpenAI Compatible LLM, margin 3 lines, apply the resolution, Specifying the prompt

```
python3 gerrit_merge_conflict_resolution_applier_with_upload.py -n ChangeNumber -a --gpt="local" -r -m 3 -p git_merge_conflict_resolution_for_upstream_integration_keep_downstream.json 
```

## Use oolama with codegemma

```
ollama run codegemma

python3 gerrit_merge_conflict_resolution_applier_with_upload.py -n ChangeNumber -a --gpt="local" -r -m 3 -p git_merge_conflict_resolution_for_upstream_integration_keep_downstream.json -e "http://localhost:11434/api/chat" -d "codegemma"
```
