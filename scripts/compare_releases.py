"""Fail unless two independently built release artifact sets are byte-identical."""
import argparse
import json
from pathlib import Path
from qualify_release import verified_set


def compare(first, second):
    a, b = verified_set(first), verified_set(second)
    for field in ('git_commit', 'dirty', 'source_sha256', 'version', 'artifacts'):
        if a[field] != b[field]: raise ValueError('Release reproducibility mismatch: ' + field)
    return {'status': 'PASS', 'source_sha256': a['source_sha256'], 'artifacts': a['artifacts']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first', type=Path);parser.add_argument('second', type=Path)
    args = parser.parse_args();print(json.dumps(compare(args.first, args.second)))
