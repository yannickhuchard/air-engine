import pytest
from air.expr import evaluate


def evaluate_conversion(source='s', target='ms', value='1.5', version='0.2', state=None):
    expression = {'language': 'AIR-Expr', 'language_version': version, 'result_type': 'Quantity[' + target + ']',
        'required_inputs': [{'name': 'amount', 'type': 'Quantity[' + source + ']'}],
        'ast': {'op': 'convert', 'args': [{'ref': 'amount'}, {'literal': {'type': 'Text', 'value': target}}]}}
    typed = {'type': 'Quantity[' + source + ']', **({'state': state} if state else {'value': value})}
    return evaluate({'expression': expression, 'inputs': {'amount': typed}})


@pytest.mark.parametrize('source,target,value,oracle', [('s', 'ms', '1.5', '1500'),
    ('KiB', 'B', '2', '2048'), ('kB', 'B', '2', '2000'), ('km', 'm', '0.005', '5'), ('ms', 's', '1', '0.001')])
def test_exact_versioned_conversion(source, target, value, oracle):
    report = evaluate_conversion(source, target, value)
    assert report['execution'] == 'EXECUTED' and report['engine'] == 'air.expr/0.4'
    assert report['value'] == {'type': 'Quantity[' + target + ']', 'value': oracle}


@pytest.mark.parametrize('source,target', [('m', 's'), ('FTE', 'h'), ('person_day', 'day'), ('USD', 'EUR'), ('millis', 's')])
def test_incompatible_units_need_an_explicit_different_model(source, target):
    report = evaluate_conversion(source, target)
    assert report['execution'] == 'ERROR' and report['result'] == 'UNKNOWN'
    assert report['diagnostics'][0]['code'] == 'AIR_EXPR_UNIT'


def test_language_01_and_rounding_do_not_change_silently():
    assert evaluate_conversion(version='0.1')['execution'] == 'ERROR'
    assert evaluate_conversion(source='s', target='min', value='1')['execution'] == 'ERROR'
    for state in ('UNKNOWN', 'CONFLICTING'):
        report = evaluate_conversion(state=state)
        assert report['result'] == state and report['value'] == {'type': 'Quantity[ms]', 'state': state}


@pytest.mark.parametrize('state', ['UNKNOWN', 'CONFLICTING'])
def test_uncertain_target_unit_returns_a_diagnostic_instead_of_crashing(state):
    expression = {'language': 'AIR-Expr', 'language_version': '0.2', 'result_type': 'Quantity[ms]',
        'ast': {'op': 'convert', 'args': [{'literal': {'type': 'Quantity[s]', 'value': '1'}},
                                        {'literal': {'type': 'Text', 'state': state}}]}}
    report = evaluate({'expression': expression, 'inputs': {}})
    assert report['execution'] == 'ERROR' and report['result'] == 'UNKNOWN'
    assert report['diagnostics'][0]['code'] == 'AIR_EXPR_INVALID'
