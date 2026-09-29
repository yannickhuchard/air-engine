"""Opt-in local runner for an explicitly selected, trusted Python unittest file.

This command executes code chosen by the operator, never commands found in AIR sources.
The signing key stays outside the test process; stdout/stderr and test exception text are not exported.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import rfc8785
from air.config import protect_directory, write_private
from air.external_proofs import ADAPTER, ENGINE, ENVELOPE
from air.foundation import check_schema


def keygen(directory):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if directory.exists(): raise ValueError('Choose a new private key directory')
    protect_directory(directory)
    key = Ed25519PrivateKey.generate()
    write_private(directory / 'private.json', {'private_key': base64.b64encode(key.private_bytes_raw()).decode()})
    write_private(directory / 'public.json', {'public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode()})
    return {'created': True, 'private_key_printed': False}


def execute_child(suite):
    """Child output is a bounded test ledger, never arbitrary captured test logs."""
    import contextlib
    import importlib.util
    import unittest
    rows = []
    class Result(unittest.TestResult):
        def addSuccess(self, test): super().addSuccess(test);rows.append({'id': test.id(), 'status': 'PASS'})
        def addFailure(self, test, err): super().addFailure(test, err);rows.append({'id': test.id(), 'status': 'FAIL'})
        def addError(self, test, err): super().addError(test, err);rows.append({'id': test.id(), 'status': 'ERROR'})
        def addSkip(self, test, reason): super().addSkip(test, reason);rows.append({'id': test.id(), 'status': 'SKIP'})
        def addExpectedFailure(self, test, err): super().addExpectedFailure(test, err);rows.append({'id': test.id(), 'status': 'EXPECTED_FAILURE'})
        def addUnexpectedSuccess(self, test): super().addUnexpectedSuccess(test);rows.append({'id': test.id(), 'status': 'UNEXPECTED_SUCCESS'})
        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            if err is not None: rows.append({'id': str(subtest), 'status': 'FAIL'})
    # A selected suite is trusted code. It runs without the signing key in its arguments or environment.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        spec = importlib.util.spec_from_file_location('air_attested_suite', suite)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        tests = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = Result();tests.run(result)
    if not rows or len(rows) > 4096: raise ValueError('Empty or oversized test execution')
    return rows


def run(challenge_file, suite, key_file, output, timeout=300):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from air.parsing import parse
    challenge = parse(challenge_file.read_bytes());binding = challenge['binding'];req = binding['request']
    checksum = 'sha256:' + hashlib.sha256(suite.read_bytes()).hexdigest()
    if binding['format'] != ENGINE or binding['adapter'] != ADAPTER or checksum != req['suite_digest']:
        raise ValueError('Selected test file does not match the pinned challenge suite')
    started = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    # File-backed output bounds memory use even if a faulty suite writes directly to the process streams.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        completed = subprocess.run([sys.executable, '-m', 'air.proof_runner', '_child', str(suite.resolve())],
            stdout=stdout, stderr=stderr, timeout=timeout, **({'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}))
        if completed.returncode: raise ValueError('External test process failed; no attestation was signed')
        stdout.seek(0);raw = stdout.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024: raise ValueError('External test output exceeds its budget')
        tests = parse(raw)
    if 'sha256:' + hashlib.sha256(suite.read_bytes()).hexdigest() != checksum:
        raise ValueError('Test file changed during execution')
    result = {'format': ENGINE, 'adapter': ADAPTER, 'challenge': challenge['challenge'], 'nonce': binding['nonce'],
        'executor': binding['executor'], 'key_id': req['key_id'], 'suite_digest': checksum,
        'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'tests': tests}
    secret = parse(key_file.read_bytes())
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret['private_key'], validate=True))
    envelope = {'result': result, 'signature': base64.b64encode(key.sign(rfc8785.dumps(result))).decode()}
    check_schema(envelope, ENVELOPE)
    write_private(output, {'attestation': envelope})
    return {'attestation_written': True, 'tests': len(tests), 'all_passed': all(t['status'] == 'PASS' for t in tests)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    generate = commands.add_parser('keygen');generate.add_argument('directory', type=Path)
    child = commands.add_parser('_child');child.add_argument('suite', type=Path)
    runner = commands.add_parser('run')
    for name in ('challenge', 'suite', 'key', 'output'): runner.add_argument('--' + name, type=Path, required=True)
    runner.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    try:
        if args.command == 'keygen': result = keygen(args.directory)
        elif args.command == '_child': result = execute_child(args.suite)
        else: result = run(args.challenge, args.suite, args.key, args.output, args.timeout)
        print(json.dumps(result));return 0
    except Exception:
        print('Proof runner failed; no key or test diagnostics are disclosed', file=sys.stderr);return 1


if __name__ == '__main__': raise SystemExit(main())
