from air.native_evidence import calls


def test_codex_requires_completed_native_mcp_event_not_model_claim():
    call={'type':'item.completed','item':{'type':'mcp_tool_call','server':'air','tool':'air_get',
          'arguments':{'id':'urn:test','revision':1},'status':'completed','error':None,
          'result':{'structured_content':{'digest':'actual'}}}}
    assert calls('codex',[call])[0]['result']=={'digest':'actual'}
    assert not calls('codex',[{'type':'item.completed','item':{'type':'agent_message','text':'All tests PASS'}}])
    for key,value in [('status','failed'),('error','unavailable'),('server','another')]:
        altered={'type':call['type'],'item':{**call['item'],key:value}}
        assert not calls('codex',[altered])
    assert not calls('codex',[{**call,'type':'item.started'}])
    refused={'type':'item.completed','item':{**call['item'],'status':'failed',
             'result':{'structured_content':{'error':'AIR_FORBIDDEN','http_status':403}}}}
    assert calls('codex',[refused])[0]['result']['http_status']==403


def test_claude_requires_matching_native_tool_call_and_result():
    request={'type':'assistant','message':{'content':[{'type':'tool_use','id':'1','name':'mcp__air__air_get','input':{'id':'urn:test','revision':1}}]}}
    response={'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'1','content':[{'type':'text','text':'{"http_status":403}'}]}]}}
    assert calls('claude-code',[request,response])[0]['result']=={'http_status':403}
    assert not calls('claude-code',[response])
    assert not calls('claude-code',[{'type':'result','subtype':'success','result':'Credit balance is too low'}])


def test_malformed_stream_fragments_are_not_success():
    assert calls('claude-code',[None,{}, {'message':{'content':'not-an-array'}}])==[]
    assert calls('codex',[{'type':'item.completed','item':None}])==[]
    assert calls('codex',[{'type':'item.completed','item':{'type':'mcp_tool_call','server':'air','status':'completed','result':{'content':None}}}])==[]
    assert calls('claude-code',[{'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':{}}]}}])==[]


def test_app_server_approval_receipt_requires_completed_air_result():
    item = {'type': 'mcpToolCall', 'server': 'air', 'tool': 'air_cancel_job',
            'arguments': {'job': {'id': 'synthetic'}}, 'status': 'completed',
            'result': {'structuredContent': {'status': 'CANCELLED'}}, 'error': None}
    event = {'method': 'item/completed', 'params': {'item': item}}
    assert calls('codex', [event])[0]['result']['status'] == 'CANCELLED'
    assert not calls('codex', [{**event, 'method': 'item/started'}])
    assert not calls('codex', [{'method': 'item/completed', 'params': {'item': {**item, 'error': 'transport failure'}}}])
    assert not calls('codex', [{'method': 'item/completed', 'params': {'item': {**item, 'server': 'codex_apps'}}}])
    assert not calls('codex', [{'method': 'item/completed', 'params': None}])
