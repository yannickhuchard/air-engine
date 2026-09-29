"""Single-process bounded server events. Never format arbitrary logging messages."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime, timezone
from pathlib import Path


class EventFormatter(logging.Formatter):
    def format(self, record):
        # Do not call getMessage/formatException: URLs, driver errors and args may contain secrets.
        severity = 'ERROR' if record.levelno >= logging.ERROR else 'WARNING' if record.levelno >= logging.WARNING else 'INFO'
        return json.dumps({'time': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                           'level': severity, 'event': 'AIR_SERVER_' + severity}, separators=(',', ':'))


class EventLog(RotatingFileHandler):
    def __init__(self, home, maximum=None, backups=None):
        maximum = int(os.environ.get('AIR_LOG_MAX_BYTES', '1048576')) if maximum is None else maximum
        backups = int(os.environ.get('AIR_LOG_BACKUPS', '5')) if backups is None else backups
        if type(maximum) is not int or not 1024 <= maximum <= 104857600:
            raise ValueError('AIR_LOG_MAX_BYTES must be 1024..104857600')
        if type(backups) is not int or not 1 <= backups <= 20:
            raise ValueError('AIR_LOG_BACKUPS must be 1..20')
        self.failures = 0
        self.last_write_ok = True
        self.path = Path(home) / 'server-events.jsonl'
        self.backupCount = backups
        self.validate_paths()
        super().__init__(self.path, maxBytes=maximum, backupCount=backups, encoding='utf-8')
        self.setFormatter(EventFormatter())

    def validate_paths(self):
        for path in [self.path, *(self.path.with_name(self.path.name + '.' + str(i)) for i in range(1, self.backupCount + 1))]:
            if path.is_symlink() or path.exists() and (not path.is_file() or path.stat().st_nlink > 1):
                raise ValueError('Server event log requires private regular files')

    def _open(self):
        self.validate_paths()
        stream = super()._open()
        if os.name != 'nt': os.fchmod(stream.fileno(), 0o600)
        return stream

    def emit(self, record):
        before = self.failures
        try:
            self.validate_paths()
            super().emit(record)
        except Exception:
            self.handleError(record)
        self.last_write_ok = self.failures == before

    def handleError(self, record):
        # logging's default error handler prints the original message and traceback to stderr.
        self.failures += 1
        self.last_write_ok = False

    def snapshot(self):
        with self.lock:
            return {'write_failures': self.failures, 'last_write_ok': self.last_write_ok,
                    'max_bytes_per_file': self.maxBytes, 'retained_files': self.backupCount + 1}


def configuration(handler):
    return {'version': 1, 'disable_existing_loggers': False,
            'handlers': {'events': {'()': lambda: handler}},
            'loggers': {name: {'handlers': ['events'], 'level': 'INFO', 'propagate': False}
                        for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access')}}
