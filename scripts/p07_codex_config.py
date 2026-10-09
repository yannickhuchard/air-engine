"""Read Codex's effective project layers without changing trust or exposing config values."""
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time


def summarize(response, workspace):
    """Only allowlisted facts leave the native configuration response."""
    if not isinstance(response, dict) or not isinstance(response.get('result'), dict):
        return {'status': 'INCOMPLETE', 'reason': 'CONFIG_READ_FAILED'}
    result = response['result']
    target = (workspace/'.codex').resolve()
    layers = result.get('layers')
    if not isinstance(layers, list):
        return {'status': 'INCOMPLETE', 'reason': 'CONFIG_LAYERS_UNAVAILABLE'}
    matching = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        name = layer.get('name', {})
        folder = name.get('dotCodexFolder') if isinstance(name, dict) else None
        if isinstance(folder, str) and Path(folder).resolve() == target:
            matching.append(layer)
    if len(matching) != 1:
        return {'status': 'INCOMPLETE', 'reason': 'PROJECT_LAYER_NOT_FOUND'}
    layer = matching[0]
    reason = layer.get('disabledReason')
    config = result.get('config', {})
    servers = config.get('mcp_servers', {}) if isinstance(config, dict) else {}
    configured = isinstance(servers, dict) and isinstance(servers.get('air'), dict)
    disabled = reason is not None
    return {'status': 'PROJECT_CONFIG_LOADED' if configured and not disabled else 'INCOMPLETE',
            'reason': 'PROJECT_TRUST_REQUIRED' if isinstance(reason, str) and 'trusted project' in reason.lower()
                      else 'PROJECT_LAYER_DISABLED' if disabled else 'AIR_SERVER_NOT_CONFIGURED' if not configured else None,
            'project_layer_found': True, 'project_layer_disabled': disabled,
            'effective_air_server': configured,
            'project_config_sha256': hashlib.sha256((target/'config.toml').read_bytes()).hexdigest(),
            'trust_modified': False, 'native_tools_tested': False}


def diagnose(executable, workspace, timeout=30):
    """config/read is read-only; never answer approval or other server requests."""
    workspace = Path(workspace).resolve()
    process = subprocess.Popen([executable, 'app-server', '--stdio'], cwd=workspace,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding='utf-8')
    pending = queue.Queue()
    def consume():
        try:
            for line in process.stdout:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                pending.put(value)
        finally:
            pending.put(None)
    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    deadline = time.monotonic()+timeout
    def send(value):
        process.stdin.write(json.dumps(value)+'\n')
        process.stdin.flush()
    def receive(identifier):
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise queue.Empty
            value = pending.get(timeout=remaining)
            if value is None:
                raise EOFError
            if isinstance(value, dict) and value.get('id') == identifier and ('result' in value or 'error' in value):
                return value
    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'air_p07_config_diagnostic', 'version': '1'},
            'capabilities': {'experimentalApi': True}}})
        if 'result' not in receive(1):
            return {'status': 'INCOMPLETE', 'reason': 'CONFIG_PROTOCOL_UNAVAILABLE'}
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'config/read', 'params': {'cwd': str(workspace), 'includeLayers': True}})
        return summarize(receive(2), workspace)
    except queue.Empty:
        return {'status': 'INCOMPLETE', 'reason': 'CONFIG_READ_TIMEOUT'}
    except (EOFError, OSError):
        return {'status': 'INCOMPLETE', 'reason': 'CONFIG_READ_FAILED'}
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=1)
        process.stdin.close()
        process.stdout.close()
