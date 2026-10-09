"""Deterministic financial projection of exact dossier declarations, no payment effects."""
from collections import defaultdict
from decimal import Decimal, localcontext
from air.core import digest
from air.expr import artifact_digest
from air.foundation import exact

ENGINE = 'air.financial-view/1'
ALLOCATION_ORDER = ['ENGINEERING', 'HARDWARE', 'STARTUP', 'CONTINGENCY', 'OPERATIONS', 'OTHER']


def month_index(month):
    y, m = map(int, month.split('-'))
    return y * 12 + m - 1


def month_name(index):
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def source(obj):
    return {**exact(obj), 'digest': digest(obj)}


def _project(g):
    rows = []; years = defaultdict(lambda: defaultdict(Decimal)); categories = defaultdict(Decimal)
    for o in g.of('CostItem'):
        b = o['body']; value = Decimal(b['amount']['value']); start = month_index(b['start'])
        end = start if b['recurrence'] == 'ONCE' else month_index(b['end']) if 'end' in b else start + 35
        monthly = value if b['recurrence'] != 'YEARLY' else value / 12
        months = 1 if b['recurrence'] == 'ONCE' else end - start + 1
        total = value if b['recurrence'] == 'ONCE' else monthly * months
        for month in range(start, end + 1):
            years[(month // 12, b['amount']['currency'])][b['nature']] += monthly
        categories[(b['nature'], b['category'], b['amount']['currency'])] += total
        calculation = b.get('calculation')
        parts = [{**p, 'subtotal': str(Decimal(p['quantity']) * Decimal(p['unit_price']))} for p in calculation['parts']] if calculation else []
        rows.append({'reference': source(o), 'name': o['meta']['name'], **b, 'parts': parts,
            'period_end': month_name(end), 'months': months, 'period_total': str(total),
            'horizon_assumed': b['recurrence'] != 'ONCE' and 'end' not in b,
            'detail_status': 'CALCULATED' if calculation else 'CALCULATION_MISSING',
            'sources': [source(g.get(r)) for r in calculation['sources'] if g.get(r)] if calculation else [],
            'cost_authenticity_verified': False})
    by_ref = {(r['reference']['id'], r['reference']['revision']): r for r in rows}
    plans = []
    for p in g.of('FinancialPlan'):
        b = p['body']; selected = [by_ref[(r['id'], r['revision'])] for r in b['cost_items']]
        total = sum((Decimal(r['period_total']) for r in selected), Decimal(0))
        envelope = Decimal(b['programme_envelope']['value']); vat = Decimal(b['vat_bridge']['value'])
        months = month_index(b['end']) - month_index(b['start']) + 1
        operating = sum((Decimal(r['period_total']) for r in selected if r.get('allocation') == 'OPERATIONS'), Decimal(0))
        allocations = defaultdict(Decimal)
        for row in selected: allocations[row.get('allocation','OTHER')] += Decimal(row['period_total'])
        contingency = sum((Decimal(r['period_total']) for r in selected if r['category'] == 'CONTINGENCY'), Decimal(0))
        plans.append({'reference': source(p), 'name': p['meta']['name'], **b,
            'calculated_cost': str(total), 'headroom': str(envelope - total), 'treasury_envelope': str(envelope + vat),
            'months': months, 'operating_total': str(operating),
            'contingency_total': str(contingency),
            'allocations': [{'allocation': key, 'amount': str(allocations[key])} for key in ALLOCATION_ORDER if key in allocations],
            'revenue_scenario_deducted_from_envelope': False,
            'operating_deficit_scenario': str(operating - Decimal(b['monthly_revenue_assumption']['value']) * months)
                if 'monthly_revenue_assumption' in b and all('allocation' in r for r in selected) else None,
            'sources_exact': [source(g.get(r)) for r in b['sources'] if g.get(r)]})
    currencies = sorted({r['amount']['currency'] for r in rows})
    result = {'engine': ENGINE, 'rows': rows, 'plans': plans,
        'annual': [{'year': y, 'currency': c, 'capex': str(v['CAPEX']), 'opex': str(v['OPEX']), 'total': str(v['CAPEX'] + v['OPEX'])}
            for (y, c), v in sorted(years.items())],
        'categories': [{'nature': n, 'category': cat, 'currency': c, 'amount': str(v)} for (n, cat, c), v in sorted(categories.items())],
        'totals': [{'currency': c, 'amount': str(sum((Decimal(r['period_total']) for r in rows if r['amount']['currency'] == c), Decimal(0)))} for c in currencies],
        'missing': {'calculations': sum(not r['parts'] for r in rows), 'contingency': not any(r['category'] == 'CONTINGENCY' for r in rows), 'plan': not plans},
        'funding_or_purchase_performed': False, 'accounting_classification_certified': False}
    result['projection_digest'] = artifact_digest(result)
    return result


def project(g):
    with localcontext() as ctx:
        ctx.prec = 64
        return _project(g)


def fmt(value):
    with localcontext() as ctx:
        ctx.prec = 64
        return f'{Decimal(value):,.2f}'.replace(',', ' ').removesuffix('.00')


def lines(view):
    from air.deliverables import table
    out = ['Dimension financière : synthèse et décomposition des postes exacts. Les montants sont des déclarations, pas des factures vérifiées.', '',
        'Un poste récurrent sans fin utilise une hypothèse de 36 mois, signalée dans son détail. Les devises ne sont pas additionnées.', '']
    for p in view['plans']:
        cur = p['programme_envelope']['currency']
        out += ['## ' + p['name'], '', p['basis'], '',
            'Référence : ' + p['reference_status'] + '. Financement : ' + p['funding_status'] + '. Horizon : ' + p['start'] + ' à ' + p['end'] + '.', '']
        labels = {'ENGINEERING':'Ingénierie', 'HARDWARE':'Matériel rendu au dépôt', 'STARTUP':'Préparation et mise en service',
            'OPERATIONS':'Exploitation sur la période', 'CONTINGENCY':'Contingence de planification', 'OTHER':'Autres ou affectation à préciser'}
        out += table(['Affectation', 'Montant (' + cur + ')'], [[labels[r['allocation']], fmt(r['amount'])] for r in p['allocations']]) + ['']
        out += table(['Décomposition', 'Montant (' + cur + ')'], [
            ['Coûts sur la période, contingence incluse', fmt(p['calculated_cost'])],
            ['Marge restante dans l’enveloppe', fmt(p['headroom'])], ['Enveloppe programme', fmt(p['programme_envelope']['value'])],
            ['Réserve de trésorerie TVA', fmt(p['vat_bridge']['value'])], ['Enveloppe de trésorerie', fmt(p['treasury_envelope'])]])
        if p['operating_deficit_scenario'] is not None:
            out += ['', 'Scénario commercial : ' + p['revenue_basis'], 'Déficit d’exploitation estimé sur la période : ' + fmt(p['operating_deficit_scenario']) + ' ' + cur + '. Les recettes futures ne réduisent pas l’enveloppe à financer.']
    out += ['', '## Synthèse annuelle', ''] + table(['Année', 'Devise', 'CAPEX', 'OPEX', 'Total'],
        [[r['year'], r['currency'], fmt(r['capex']), fmt(r['opex']), fmt(r['total'])] for r in view['annual']])
    out += ['', '## Par nature et catégorie (sur l’horizon)', ''] + table(['Nature', 'Catégorie', 'Devise', 'Montant'],
        [[r['nature'], r['category'], r['currency'], fmt(r['amount'])] for r in view['categories']])
    for r in view['rows']:
        cur = r['amount']['currency']
        out += ['', '## ' + r['name'], '', r['nature'] + ' / ' + r['category'] + ' / ' + r.get('allocation', 'Affectation à préciser') + '.',
            'Montant : ' + fmt(r['amount']['value']) + ' ' + cur + ' ; ' + r['recurrence'] + ' ; ' + r['start'] + ' à ' + r['period_end'] +
            ' ; total sur la période : ' + fmt(r['period_total']) + ' ' + cur + '.', r['basis'],
            'Confiance : ' + r['confidence'] + '. ' + ('Horizon supposé de 36 mois.' if r['horizon_assumed'] else 'Période explicite.'), '']
        if r['parts']:
            out += table(['Élément', 'Quantité', 'Unité', 'Prix unitaire (' + cur + ')', 'Sous-total', 'Explication'],
                [[p['label'], p['quantity'], p['unit'], fmt(p['unit_price']), fmt(p['subtotal']), p['explanation']] for p in r['parts']])
            out += ['Statut des bases : ' + r['calculation']['evidence_status'] + '.']
        else: out += ['Détail quantitatif non documenté : recueillir quantité, unité, prix unitaire et justificatif.']
        out += ['Référence exacte : `' + r['reference']['id'] + '` r' + str(r['reference']['revision']) + ' ; `' + r['reference']['digest'] + '`.']
        out += ['Source de calcul : `' + s['id'] + '` r' + str(s['revision']) + ' ; `' + s['digest'] + '`.' for s in r['sources']]
    if view['missing']['contingency']: out += ['', 'Contingence non documentée. Définir son assiette, son taux et ses conditions d’utilisation.']
    if view['missing']['plan']: out += ['', 'Enveloppe, réserve TVA, horizon du programme et statut de financement non documentés dans un FinancialPlan.']
    out += ['', 'CAPEX/OPEX sont des catégories de planification déclarées. Leur traitement comptable, la TVA récupérable et les taux douaniers restent à qualifier.']
    return out
