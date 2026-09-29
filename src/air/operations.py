"""Bounded HTTP admission and process-local metrics without business data or free-text labels."""
import os
import asyncio
import math
import threading
import time
from air.parsing import MAX_BYTES


class State:
    def __init__(self, maximum=None):
        self.maximum = int(os.environ.get('AIR_MAX_INFLIGHT', '32')) if maximum is None else maximum
        if type(self.maximum) is not int or not 1 <= self.maximum <= 1024:
            raise ValueError('AIR_MAX_INFLIGHT must be an integer from 1 to 1024')
        self.per_subject = int(os.environ.get('AIR_MAX_INFLIGHT_PER_SUBJECT', '8'))
        self.body_timeout = float(os.environ.get('AIR_BODY_TIMEOUT_SECONDS', '30'))
        if not 1 <= self.per_subject <= 1024:
            raise ValueError('AIR_MAX_INFLIGHT_PER_SUBJECT must be an integer from 1 to 1024')
        if not math.isfinite(self.body_timeout) or not 1 <= self.body_timeout <= 300:
            raise ValueError('AIR_BODY_TIMEOUT_SECONDS must be from 1 to 300')
        self.lock = threading.Lock()
        self.subjects = {}
        self.subject_rejected = 0
        self.input_rejected = {reason: 0 for reason in ('too_large', 'invalid_length', 'timeout', 'disconnected')}
        self.active = self.accepted = self.rejected = self.finished = 0
        self.total_seconds = self.max_seconds = 0.0
        self.statuses = {s: 0 for s in ('2xx', '3xx', '4xx', '5xx', 'other')}
        self.buckets = {str(v): 0 for v in (.01, .05, .1, .5, 1, 5, 30)}
        self.started = time.monotonic()

    def enter(self):
        with self.lock:
            if self.active >= self.maximum:
                self.rejected += 1
                return False
            self.active += 1;self.accepted += 1
            return True

    def leave(self, status, elapsed):
        with self.lock:
            self.active -= 1;self.finished += 1
            category = str(status // 100) + 'xx'
            self.statuses[category if category in self.statuses else 'other'] += 1
            self.total_seconds += elapsed;self.max_seconds = max(self.max_seconds, elapsed)
            for limit in self.buckets:
                if elapsed <= float(limit): self.buckets[limit] += 1

    def enter_subject(self, subject):
        with self.lock:
            active = self.subjects.get(subject, 0)
            if active >= self.per_subject:
                self.subject_rejected += 1
                return False
            self.subjects[subject] = active + 1
            return True

    def leave_subject(self, subject):
        with self.lock:
            remaining = self.subjects[subject] - 1
            if remaining: self.subjects[subject] = remaining
            else: del self.subjects[subject]

    def reject_input(self, reason):
        with self.lock: self.input_rejected[reason] += 1

    def snapshot(self):
        with self.lock:
            return {'engine': 'air.operations/0.34', 'scope': 'PROCESS_LOCAL_HTTP',
                'uptime_seconds': round(time.monotonic() - self.started, 3), 'max_inflight': self.maximum,
                'active_requests': self.active, 'accepted_requests': self.accepted, 'rejected_busy': self.rejected,
                'finished_requests': self.finished, 'http_status_classes': dict(self.statuses),
                'identity_admission': {'max_inflight_per_subject': self.per_subject,
                    'active_subjects': len(self.subjects), 'rejected_busy': self.subject_rejected},
                'input_limits': {'max_document_bytes': MAX_BYTES, 'body_timeout_seconds': self.body_timeout,
                    'rejections': dict(self.input_rejected)},
                'duration_seconds': {'sum': round(self.total_seconds, 6), 'max': round(self.max_seconds, 6),
                    'cumulative_buckets': dict(self.buckets)},
                'contains_business_data': False, 'persistent': False}


async def read_document_bytes(request, state):
    """Bound the entire reception, before parsing or any mutation; never reset the clock per chunk."""
    from fastapi import HTTPException
    from starlette.requests import ClientDisconnect
    def reject(reason, status, code):
        state.reject_input(reason)
        raise HTTPException(status, detail={'code': code})
    lengths = request.headers.getlist('content-length')
    declared = None
    if lengths:
        value = lengths[0]
        if len(lengths) != 1 or not value.isascii() or not value.isdecimal() or len(value) > 20:
            reject('invalid_length', 400, 'AIR_INVALID_CONTENT_LENGTH')
        declared = int(value)
        if declared > MAX_BYTES: reject('too_large', 413, 'AIR_INPUT_TOO_LARGE')
    data = bytearray()
    try:
        async with asyncio.timeout(state.body_timeout):
            async for chunk in request.stream():
                if len(chunk) > MAX_BYTES - len(data): reject('too_large', 413, 'AIR_INPUT_TOO_LARGE')
                data.extend(chunk)
    except TimeoutError: reject('timeout', 408, 'AIR_INPUT_TIMEOUT')
    except ClientDisconnect: reject('disconnected', 400, 'AIR_CLIENT_DISCONNECTED')
    if declared is not None and len(data) != declared:
        reject('invalid_length', 400, 'AIR_INVALID_CONTENT_LENGTH')
    return bytes(data)


class AdmissionGuard:
    def __init__(self, app, state): self.app, self.state = app, state

    async def __call__(self, scope, receive, send):
        # Probes remain available during overload; they never contain business data.
        if scope['type'] != 'http' or scope.get('path') in ('/health', '/ready'):
            return await self.app(scope, receive, send)
        if not self.state.enter():
            await send({'type': 'http.response.start', 'status': 503,
                'headers': [(b'content-type', b'application/json'), (b'retry-after', b'1')]})
            await send({'type': 'http.response.body', 'body': b'{"detail":{"code":"AIR_BUSY"}}'})
            return
        start = time.monotonic();status = 500
        async def observed(message):
            nonlocal status
            if message['type'] == 'http.response.start': status = message['status']
            await send(message)
        try: await self.app(scope, receive, observed)
        finally: self.state.leave(status, time.monotonic() - start)
