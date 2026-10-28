"""Read version-bound qualification facts without promoting historical evidence."""
import argparse
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def status(root=ROOT):
    root = Path(root).resolve()
    def read(path):
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Release evidence must stay inside the repository')
        return json.loads(target.read_text(encoding='utf-8'))
    matrix = read('docs/traceability/client-release-matrix.json')
    package = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    if matrix['candidate_version'] != package['version']:
        raise ValueError('Client matrix does not describe the current candidate')
    decision = read(matrix['qualified_local_decision'])
    for route in matrix['routes']:
        setup = (root / route['setup']).resolve()
        if not setup.is_relative_to(root) or not setup.is_file():
            raise ValueError('Missing client setup guide')
    if set(matrix['required_clients']) != {r['client'] for r in matrix['routes']}:
        raise ValueError('Every required client needs a documented route')
    observation = matrix['historical_publication_observation']
    read(observation['evidence'])
    return {**matrix, 'historically_qualified_version': decision['candidate_version'],
            'historical_platform': decision['platform'], 'license': package['license'],
            'historical_support': decision['support'],
            'current_candidate_g1_received': bool(decision['g1_received'] and decision['candidate_version'] == package['version']),
            'qualification_inherited': False, 'external_services_contacted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(status(), ensure_ascii=False, indent=2))
