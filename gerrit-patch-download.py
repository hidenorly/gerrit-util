import subprocess
import json
import argparse
from datetime import datetime, timedelta
from gerrit_query import GerritUtil


def main():
    parser = argparse.ArgumentParser(description='Query Gerrit and parse results')
    parser.add_argument('-t', '--target', default='gerrit-ssh', help='Specify ssh target host')
    parser.add_argument('-b', '--branch', default='main', help='Branch to query')
    parser.add_argument('-s', '--status', default='merged|open', help='Status to query (merged|open)')
    parser.add_argument('--since', default='1 week ago', help='Since when to query')
    parser.add_argument('-d', '--download', default='.', help='Specify')
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

if __name__ == "__main__":
    main()