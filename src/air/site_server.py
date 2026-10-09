"""Serve one generated static architecture site, on loopback, with Python alone.

No directories, registry, credentials, arbitrary files, or business API. Export
resources are pinned at startup; restart after a new generation replaces them.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
from air.atelier import safe_path
from air.architecture_site import CSP


def load_site(directory):
    root = Path(directory).resolve(strict=True)
    manifest_path = root / 'site-manifest.json'
    if manifest_path.is_symlink(): raise ValueError('Site manifest must not be a symlink')
    if manifest_path.stat().st_size > 4194304: raise ValueError('Site manifest too large')
    raw = manifest_path.read_bytes();manifest = json.loads(raw)
    if manifest.get('engine') != 'air.architecture-site/1': raise ValueError('Not an AIR architecture site')
    pwa = manifest['pwa'];items = pwa['resources']
    if not items or len(items) > 10000: raise ValueError('Invalid static resource budget')
    pinned = {}
    for item in items:
        name = safe_path(item['path'])
        if name in pinned: raise ValueError('Duplicate static resource')
        pinned[name] = (item['digest'], item['media_type'])
    pinned['sw.js'] = (pwa['worker_digest'], 'text/javascript')
    pinned['site-manifest.json'] = ('sha256:' + hashlib.sha256(raw).hexdigest(), 'application/json')
    return root, pinned


def make_server(directory, port=8741):
    root, pinned = load_site(directory)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass  # No private paths in logs.

        def do_HEAD(self): self.serve(False)
        def do_GET(self): self.serve(True)

        def serve(self, body):
            expected = str(self.server.server_port)
            if self.headers.get('Host') not in ('127.0.0.1:' + expected, 'localhost:' + expected):
                self.send_error(403);return
            url = urlsplit(self.path)
            name = unquote(url.path).lstrip('/') or 'index.html'
            if url.scheme or url.netloc or url.query or name not in pinned:
                self.send_error(404);return
            target = root.joinpath(name)
            # Check every path component, including symlinked subdirectories.
            current = root
            for part in name.split('/'):
                current = current / part
                if current.is_symlink(): self.send_error(403);return
            try:
                if not target.resolve(strict=True).is_relative_to(root) or target.stat().st_size > 4194304:
                    self.send_error(403);return
                raw = target.read_bytes()
            except OSError:
                self.send_error(404);return
            sha, media = pinned[name]
            if 'sha256:' + hashlib.sha256(raw).hexdigest() != sha:
                self.send_error(409, 'Regenerate then restart the site server');return
            self.send_response(200)
            self.send_header('Content-Type', media + '; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', CSP + "; frame-ancestors 'none'")
            self.end_headers()
            if body: self.wfile.write(raw)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read one generated AIR site on this workstation')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--port', type=int, default=8741)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('port must be between 1 and 65535')
    server = make_server(args.directory, args.port)
    print(f'http://127.0.0.1:{server.server_port}/index.html', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
