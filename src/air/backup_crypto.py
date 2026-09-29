"""Optional authenticated backup envelopes. Authentication completes before any content is parsed."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import uuid

from air.backup import checksum, validate_backup
from air.config import protect_directory, windows_persistent_acls

MAGIC = b'AIR-ENCRYPTED-BACKUP/1\n'
HEADER_SIZE = len(MAGIC) + 32 + 12
BLOCK = 1024 * 1024
MAX_BYTES = 16 * 1024**3
MANDATORY = {'air.db', 'config.json', 'manifest.json'}


def crypto():
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidTag
    except ImportError:
        raise ValueError('Encrypted backups require the optional air-engine[backup] extra') from None
    return Cipher, algorithms, modes, HKDF, hashes, InvalidTag


def create_key(directory):
    directory = Path(directory).absolute()
    directory.mkdir(parents=True, exist_ok=False)
    protect_directory(directory)
    path = directory/'backup.key'
    with path.open('xb') as stream:
        if os.name != 'nt': os.fchmod(stream.fileno(), 0o600)
        stream.write(os.urandom(32))
        stream.flush();os.fsync(stream.fileno())
    return {'status':'CREATED', 'key_file':str(path), 'key_contents_displayed':False}


def read_key(path):
    path = Path(path).absolute()
    if path.is_symlink(): raise ValueError('Backup key must be a private regular file')
    if os.name == 'nt':
        if not windows_persistent_acls(path.parent): raise ValueError('Backup key requires persistent ACLs')
        # Constant program; paths go through the environment, never PowerShell interpolation.
        program = """$ErrorActionPreference='Stop'
$acl=[System.IO.File]::GetAccessControl($env:AIR_KEY_CHECK_PATH)
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$rules=@($acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]))
if ($rules.Count -eq 0) { exit 1 }
foreach ($rule in $rules) {
 if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin @($sid,'S-1-5-18')) { exit 1 }
}
exit 0
"""
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',program],
            env={**os.environ, 'AIR_KEY_CHECK_PATH':str(path)}, capture_output=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise ValueError('Backup key permissions must restrict access to the current account and SYSTEM')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (os.name != 'nt' and info.st_mode & 0o077):
            raise ValueError('Backup key must be a private regular file')
        key = stream.read(33)
    if len(key) != 32: raise ValueError('Backup key must contain exactly 32 bytes')
    return key


def pending_for(destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink(): raise ValueError('A new destination is required')
    pending = destination.with_name(destination.name + '.pending-' + uuid.uuid4().hex)
    pending.mkdir(parents=True, exist_ok=False);protect_directory(pending)
    return destination, pending


def derived_key(master, salt):
    _, _, _, HKDF, hashes, _ = crypto()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=MAGIC).derive(master)


def encrypt(backup, destination, key_file):
    Cipher, algorithms, modes, _, _, _ = crypto()
    master = read_key(key_file)
    backup = Path(backup)
    manifest = validate_backup(backup)
    if Path(key_file).resolve().is_relative_to(backup.resolve()): raise ValueError('Keep the key outside the backup')
    files = [{'name':name, 'bytes':(backup/name).stat().st_size, 'sha256':checksum(backup/name)[7:]}
             for name in sorted(set(manifest['files']) | {'manifest.json'})]
    if sum(f['bytes'] for f in files) > MAX_BYTES: raise ValueError('Encrypted backup payload exceeds 16 GiB')
    catalog = json.dumps({'format':'air.backup-payload/1','files':files},sort_keys=True,separators=(',',':')).encode()
    if len(catalog) > 8192: raise ValueError('Backup catalog exceeds its size limit')
    destination, pending = pending_for(destination)
    salt, nonce = os.urandom(32), os.urandom(12)
    header = MAGIC + salt + nonce
    encryptor = Cipher(algorithms.AES(derived_key(master,salt)),modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    path = pending/'snapshot.airenc'
    with path.open('xb') as output:
        if os.name != 'nt': os.fchmod(output.fileno(),0o600)
        output.write(header)
        output.write(encryptor.update(len(catalog).to_bytes(4,'big') + catalog))
        for entry in files:
            count = 0;digest = hashlib.sha256()
            if (backup/entry['name']).is_symlink(): raise ValueError('Backup changed during encryption')
            with (backup/entry['name']).open('rb') as source:
                for block in iter(lambda: source.read(BLOCK), b''):
                    count += len(block)
                    if count > entry['bytes']: raise ValueError('Backup changed during encryption')
                    digest.update(block);output.write(encryptor.update(block))
            if count != entry['bytes'] or digest.hexdigest() != entry['sha256']:
                raise ValueError('Backup changed during encryption')
        output.write(encryptor.finalize());output.write(encryptor.tag)
        output.flush();os.fsync(output.fileno())
    pending.rename(destination)
    return {'status':'PASS','format':'air.encrypted-backup/1','encrypted_backup':str(destination),
            'sha256':checksum(destination/'snapshot.airenc'), 'key_included':False}


def unpack_authenticated(stream, pending):
    length = int.from_bytes(stream.read(4),'big')
    if not 1 <= length <= 8192: raise ValueError('Invalid backup catalog size')
    catalog = json.loads(stream.read(length))
    if not isinstance(catalog,dict) or set(catalog) != {'format','files'} or catalog['format'] != 'air.backup-payload/1':
        raise ValueError('Unsupported backup payload')
    files = catalog['files']
    if not isinstance(files,list) or len(files) not in (3,4): raise ValueError('Invalid backup file set')
    names = []
    for entry in files:
        if not isinstance(entry,dict) or set(entry) != {'name','bytes','sha256'}:
            raise ValueError('Invalid backup entry')
        if not isinstance(entry['name'],str) or type(entry['bytes']) is not int or not 0 <= entry['bytes'] <= MAX_BYTES or not isinstance(entry['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',entry['sha256']):
            raise ValueError('Invalid backup entry')
        names.append(entry['name'])
    if len(set(names)) != len(names) or set(names) not in (MANDATORY, MANDATORY | {'access-policy.json'}) or sum(e['bytes'] for e in files) > MAX_BYTES:
        raise ValueError('Invalid backup file set')
    for entry in files:
        remaining = entry['bytes'];digest = hashlib.sha256()
        with (pending/entry['name']).open('xb') as output:
            if os.name != 'nt': os.fchmod(output.fileno(),0o600)
            while remaining:
                block = stream.read(min(BLOCK,remaining))
                if not block: raise ValueError('Truncated backup payload')
                remaining -= len(block);digest.update(block);output.write(block)
        if digest.hexdigest() != entry['sha256']: raise ValueError('Backup payload checksum mismatch')
    if stream.read(1): raise ValueError('Unexpected trailing backup payload')
    validate_backup(pending)


def decrypt(encrypted, destination, key_file):
    Cipher, algorithms, modes, _, _, InvalidTag = crypto()
    master = read_key(key_file)
    path = Path(encrypted)/'snapshot.airenc'
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode): raise ValueError('Encrypted backup must be a regular file')
    with path.open('rb') as source:
        size = os.fstat(source.fileno()).st_size
        if not HEADER_SIZE+20 <= size <= MAX_BYTES+HEADER_SIZE+8192+20:
            raise ValueError('Encrypted backup size is outside supported bounds')
        header = source.read(HEADER_SIZE)
        if not header.startswith(MAGIC): raise ValueError('Unsupported encrypted backup format')
        salt, nonce = header[len(MAGIC):len(MAGIC)+32], header[-12:]
        source.seek(-16,os.SEEK_END);tag = source.read(16);source.seek(HEADER_SIZE)
        destination, pending = pending_for(destination)
        decryptor = Cipher(algorithms.AES(derived_key(master,salt)),modes.GCM(nonce,tag)).decryptor()
        decryptor.authenticate_additional_data(header)
        # Unauthenticated bytes are never parsed or published. TemporaryFile is private and closed on failure.
        with tempfile.TemporaryFile(mode='w+b',dir=pending) as plaintext:
            remaining = size-HEADER_SIZE-16
            while remaining:
                block = source.read(min(BLOCK,remaining))
                if not block: raise ValueError('Truncated encrypted backup')
                remaining -= len(block);plaintext.write(decryptor.update(block))
            if source.read(16) != tag or source.read(1): raise ValueError('Encrypted backup changed during decryption')
            try: plaintext.write(decryptor.finalize())
            except InvalidTag: raise ValueError('Encrypted backup authentication failed') from None
            plaintext.seek(0);unpack_authenticated(plaintext,pending)
    pending.rename(destination)
    return {'status':'PASS','backup':str(destination),'authenticated':True,'key_included':False}
