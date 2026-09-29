"""Request-scoped authority, rechecked at every transaction and before emitting a successful response."""
from contextvars import ContextVar
from air.access import AccessPolicy, Forbidden, PolicyUnavailable

current = ContextVar('air_request_authority', default=None)


def check(store, conn, authority, writing=False):
    original_store, principal, policy, settings = authority
    if store.engine.url != original_store.engine.url: raise Forbidden('Request cannot access another registry')
    if writing:
        from air.packages import lock_registry
        lock_registry(conn)
    from air.jobs import check_identity
    check_identity(store, conn, principal, settings)
    if AccessPolicy.load(settings.home).digest != policy.digest:
        raise Forbidden('Authority changed during the request')


def guard_write(store, conn):
    authority = current.get()
    if authority is not None: check(store, conn, authority, writing=True)


class ResponseAuthority:
    def __init__(self, app, store): self.app, self.store = app, store

    async def __call__(self, scope, receive, send):
        from starlette.concurrency import run_in_threadpool
        if scope['type'] != 'http': return await self.app(scope, receive, send)
        refused = False
        async def guarded_send(message):
            nonlocal refused
            if message['type'] == 'http.response.start' and message['status'] < 400:
                authority = scope.get('state', {}).get('air_authority')
                if authority is not None:
                    def verify():
                        with self.store.engine.connect() as conn: check(self.store, conn, authority)
                    try: await run_in_threadpool(verify)
                    except (Forbidden, PolicyUnavailable):
                        refused = True
                        await send({'type': 'http.response.start', 'status': 403,
                                    'headers': [(b'content-type', b'application/json')]})
                        await send({'type': 'http.response.body',
                                    'body': b'{"detail":{"code":"AIR_AUTHORITY_CHANGED"}}', 'more_body': False})
                        return
            if not refused: await send(message)
        await self.app(scope, receive, guarded_send)
