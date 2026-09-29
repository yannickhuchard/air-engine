"""Read-only checks for a private, autonomous SQLite/local workstation."""
import ipaddress
import json
import os
from pathlib import Path
import stat
import subprocess
from sqlalchemy.exc import SQLAlchemyError

from air.config import Settings, windows_persistent_acls
from air.transport import ServerBinding


def private_paths(home):
    paths = [home, home/'config.json', home/'credentials.json', home/'air.db']
    for name in ('access-policy.json', 'air.db-wal', 'air.db-shm'):
        if (home/name).exists(): paths.append(home/name)
    for path in paths:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            return False
        if path == home:
            if not stat.S_ISDIR(info.st_mode): return False
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: return False
    if os.name != 'nt':
        # Private directory traversal protects SQLite files created with the user's
        # umask. Secrets themselves must also be private and owned by this account.
        return all(p.stat().st_uid == os.getuid() for p in paths) and all(
            p.stat().st_mode & 0o077 == 0 for p in (home, home/'credentials.json', home/'config.json'))
    if not windows_persistent_acls(home): return False
    program = """$ErrorActionPreference='Stop'
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
foreach ($path in (ConvertFrom-Json $env:AIR_WORKSTATION_CHECK_PATHS)) {
 if ([System.IO.Directory]::Exists($path)) { $acl=[System.IO.Directory]::GetAccessControl($path) }
 else { $acl=[System.IO.File]::GetAccessControl($path) }
 $rules=@($acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]))
 if ($rules.Count -eq 0) { exit 1 }
 foreach ($rule in $rules) {
  if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin @($sid,'S-1-5-18')) { exit 1 }
 }
}
exit 0
"""
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',program],
        env={**os.environ,'AIR_WORKSTATION_CHECK_PATHS':json.dumps([str(p) for p in paths])},
        capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    return result.returncode == 0


def inspect(home):
    """No server required. Never echo paths, database URLs or credential contents."""
    from air import __version__
    from air.resource_usage import status as resources
    from air.storage import Store
    home = Path(home).absolute()
    checks = {}
    try:
        checks['private_storage'] = private_paths(home)
        if checks['private_storage']:
            settings = Settings.load(home)
            binding = ServerBinding.load(home, settings.server)
            checks['local_identity'] = settings.auth_mode == 'local'
            checks['loopback_only'] = ipaddress.ip_address(binding.host).is_loopback
            # No remote SQL connection, and no token read, before profile verification.
            expected = 'sqlite:///' + (home.resolve()/'air.db').as_posix()
            checks['sqlite_in_private_home'] = settings.database_url == expected
            if all(checks.values()):
                credential = json.loads((home/'credentials.json').read_text(encoding='utf-8'))
                store = Store(settings.database_url)
                try:
                    store.check_version()
                    raw = credential.get('access_token') if isinstance(credential,dict) else None
                    checks['credential_valid'] = isinstance(raw,str) and store.authenticate(raw) is not None
                    with store.engine.connect() as conn:
                        checks['database_integrity'] = conn.exec_driver_sql('PRAGMA quick_check').all() == [('ok',)]
                finally: store.engine.dispose()
                measured = resources(home)
                checks['free_space_margin'] = not measured['home_volume_low']
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, SQLAlchemyError):
        checks['inspection_completed'] = False
    required = ('private_storage','local_identity','loopback_only','sqlite_in_private_home',
                'credential_valid','database_integrity','free_space_margin')
    for key in required: checks.setdefault(key, False)
    return {'format':'air.workstation-inspection/1','version':__version__,
            'profile':'LOCAL_ARCHITECT_WORKSTATION','status':'PASS' if all(checks.values()) else 'FAILED',
            'checks':checks,'contains_secrets':False,'runtime_listener_verified':False,
            'backup_recency_verified':False,'production_ready':False}
