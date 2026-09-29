"""Declared constraints, controls and policies; no authorization from declarations."""
from air.expr import Program, bounded, typed, wire, ExprError
from air.knowledge_schema import literal_values

PROFILE = 'air.governance/0.25'
NAMES = ['Constraint', 'Control', 'Obligation', 'Policy', 'Risk', 'Waiver']


def bodies(record, text, uri, ref, refs, nonempty, instant):
    expression = record({'language': {'const': 'AIR-Expr'}, 'language_version': {'const': '0.1'}, 'ast': {'type': 'object'},
        'result_type': {'const': 'Boolean'}, 'required_inputs': {'type': 'array', 'items': record({'name': text, 'type': text}), 'maxItems': 128}},
        ['language', 'language_version', 'ast', 'result_type'])
    condition = {'oneOf': [text, expression]}
    many = {**nonempty, 'maxItems': 128};optional = {**refs, 'maxItems': 128}
    texts = {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 128, 'uniqueItems': True}
    return {
        'air.Constraint': record({'mode': {'enum': ['hard', 'soft']}, 'scope': ref, 'condition': condition, 'source': many, 'exception_policy': text, 'verification': many}),
        'air.Control': record({'objective': text, 'mechanism': text, 'scope': ref, 'owner': uri, 'verification': many, 'evidence_requirements': texts}),
        'air.Obligation': record({'source_text': ref, 'interpretation': text, 'applicability_decision': ref, 'controls': optional, 'review_due': instant}),
        'air.Policy': record({'intent': text, 'issuer': uri, 'applicability': condition, 'constraints': many, 'review_policy': text}),
        'air.Risk': record({'scenario': text, 'causes': optional, 'consequences': texts, 'assessment_method': text, 'treatment': many, 'residual_assessment': text}),
        'air.Waiver': record({'rule': ref, 'permitted_basis': text, 'scope': ref, 'expires_at': instant, 'approval': ref, 'compensating_controls': optional}),
    }


def expressions(obj):
    field = {'air.Constraint': 'condition', 'air.Policy': 'applicability'}.get(obj['meta']['type'])
    if field and isinstance(obj['body'][field], dict): yield 'body/' + field, obj['body'][field]


def slots(obj, data_types):
    body, kind = obj['body'], obj['meta']['type']
    fields = {
        'air.Constraint': {'scope': ['air.Scope'], 'source': data_types, 'verification': ['air.VerificationCase']},
        'air.Control': {'scope': ['air.Scope'], 'verification': ['air.VerificationCase']},
        'air.Obligation': {'source_text': ['air.Source'], 'applicability_decision': ['air.Decision'], 'controls': ['air.Control']},
        'air.Policy': {'constraints': ['air.Constraint']},
        'air.Risk': {'causes': data_types, 'treatment': ['air.Control', 'air.Decision']},
        'air.Waiver': {'rule': ['air.Constraint', 'air.Policy'], 'scope': ['air.Scope'], 'approval': ['air.Decision'], 'compensating_controls': ['air.Control']},
    }.get(kind, {})
    for field, targets in fields.items():
        for reference in body[field] if isinstance(body[field], list) else [body[field]]: yield 'body/' + field, reference, targets
    for path, expression in expressions(obj):
        try: Program(expression)
        except ExprError: continue
        for value in literal_values(expression):
            checked = typed(value)
            if checked.type == 'Reference' and checked.state == 'KNOWN': yield path + '/ast/literal', checked.value, data_types
            elif checked.type == 'Collection[Reference]' and checked.state == 'KNOWN':
                for item in checked.value:
                    if item.state == 'KNOWN': yield path + '/ast/literal', item.value, data_types


def local_issues(obj):
    for path, expression in expressions(obj):
        try: bounded(expression);Program(expression)
        except ExprError as exc: yield exc.code, str(exc)


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type'];refkey = lambda r: (r['id'], r['revision'])
    for field in {'air.Constraint': ['source', 'verification'], 'air.Control': ['verification'], 'air.Obligation': ['controls'],
                  'air.Policy': ['constraints'], 'air.Risk': ['causes', 'treatment'], 'air.Waiver': ['compensating_controls']}.get(kind, []): body[field].sort(key=refkey)
    for field in {'air.Control': ['evidence_requirements'], 'air.Risk': ['consequences']}.get(kind, []): body[field].sort()
    for path, expression in expressions(obj):
        if 'required_inputs' in expression: expression['required_inputs'].sort(key=lambda p: p['name'])
        for value in literal_values(expression):
            normalized = wire(typed(value));value.clear();value.update(normalized)
