"""Extract completed MCP calls from native CLI event streams, never model prose."""
import json


def calls(client, rows):
    found = []
    pending = {}
    def result(value):
        if not isinstance(value,dict): return None
        structured = value.get('structured_content',value.get('structuredContent'))
        if isinstance(structured,dict): return structured
        content = value.get('content',[])
        if not isinstance(content,list): return None
        for item in content:
            if isinstance(item,dict) and item.get('type') == 'text':
                try:
                    parsed = json.loads(item['text'])
                    if isinstance(parsed,dict): return parsed
                except (ValueError,TypeError): pass
        return None
    for row in rows:
        if not isinstance(row,dict): continue
        if client == 'codex':
            # Native app-server and CLI encode the same completed MCP event
            # differently. Never accept partial items or assistant prose.
            if row.get('method') == 'item/completed':
                native = row.get('params', {}).get('item', {}) if isinstance(row.get('params'), dict) else {}
                if isinstance(native, dict) and native.get('type') == 'mcpToolCall':
                    row = {'type': 'item.completed', 'item': {**native, 'type': 'mcp_tool_call'}}
            item = row.get('item',{})
            if row.get('type') == 'item.completed' and isinstance(item,dict) and item.get('type') == 'mcp_tool_call' and item.get('server') == 'air' and not item.get('error'):
                payload = result(item.get('result'))
                # Codex marks an actual MCP isError response as failed. Preserve
                # this observed refusal; a transport error is not an AIR verdict.
                refusal = isinstance(payload,dict) and str(payload.get('error','')).startswith('AIR_') and type(payload.get('http_status')) is int and 400 <= payload['http_status'] < 600
                if payload is not None and (item.get('status') == 'completed' or (item.get('status') == 'failed' and refusal)):
                    found.append({'tool':item.get('tool'),'arguments':item.get('arguments'),'result':payload})
        elif client == 'claude-code':
            message = row.get('message',{})
            if not isinstance(message,dict): continue
            content = message.get('content',[])
            if not isinstance(content,list): continue
            for item in content:
                if not isinstance(item,dict): continue
                if row.get('type') == 'assistant' and item.get('type') == 'tool_use' and isinstance(item.get('id'),str) and str(item.get('name','')).startswith('mcp__air__'):
                    pending[item.get('id')] = item
                elif row.get('type') == 'user' and item.get('type') == 'tool_result' and isinstance(item.get('tool_use_id'),str):
                    original = pending.pop(item.get('tool_use_id'),None)
                    value = item.get('content')
                    if isinstance(value,str):
                        try: value = json.loads(value)
                        except ValueError: value = None
                    if isinstance(value,list): value = result({'content':value})
                    if isinstance(value,dict) and original:
                        found.append({'tool':original['name'][len('mcp__air__'):],
                                      'arguments':original.get('input'), 'result':value})
    return found
