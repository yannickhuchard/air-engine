"""Executive presentation of a solution architecture, compiled from pinned baselines, in French and English.

Storyline of a senior-management deck: the answer first (management summary), then situation, complication and the
decision asked, then business, solution, implementation, resources and finance, risks and proof, and the decisions
to take. Every title is an action title computed from the dossier; every figure cites where it comes from. Nothing is
invented. One HTML file carries both languages, switched by a selector.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import html
from air.core import TEXT, URI, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema
from air.projections import SNAPSHOT

ENGINE = 'air.presentation/0.33'
LANGUAGES = ('fr', 'en')
REQUEST = record({'title': {**TEXT, 'maxLength': 200}, 'title_en': {**TEXT, 'maxLength': 200},
                  'baselines': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 16, 'uniqueItems': True},
                  'client': {**TEXT, 'maxLength': 120}, 'provider': {**TEXT, 'maxLength': 120},
                  'audience': {'enum': ['STEERING', 'SPONSOR', 'CONTRACT']}, 'language': {'enum': list(LANGUAGES)},
                  'projects': {'type': 'object', 'maxProperties': 32, 'propertyNames': {'pattern': '^[a-z][a-z0-9_.-]{0,127}$'},
                               'additionalProperties': {'oneOf': [{'type': 'string', 'minLength': 1, 'maxLength': 80},
                                   {'type': 'object', 'additionalProperties': False, 'minProperties': 1,
                                    'properties': {'fr': {'type': 'string', 'minLength': 1, 'maxLength': 80}, 'en': {'type': 'string', 'minLength': 1, 'maxLength': 80}}}]}},
                  'content': {'enum': ['OUTLINE', 'HTML']}}, ['title', 'baselines'])
H = html.escape
# Slides kept per audience: a sponsor decides on value, cost and time; a steering committee also sees the proof; a contract needs everything.
AUDIENCES = {'SPONSOR': {'cover', 'summary', 'gate', 'stakes', 'architecture', 'roadmaps', 'ai', 'finance', 'risks', 'decision'},
             'STEERING': {'cover', 'summary', 'context', 'stakes', 'streams', 'architecture', 'events', 'ui', 'security', 'roadmaps', 'gantt', 'ai',
                          'finance', 'risks', 'gate', 'decision'},
             'CONTRACT': {'cover', 'summary', 'context', 'stakes', 'streams', 'capabilities', 'journeys', 'architecture', 'events', 'ui', 'security',
                          'tech', 'roadmaps', 'gantt', 'ai', 'raci', 'finance', 'risks', 'gate', 'decision', 'pins'}}
CRITERIA = {'REFERENCE_CLOSURE': ('Références fermées', 'References closed'), 'STRUCTURE': ('Structure', 'Structure'),
            'CONSTRUCTION_CHAIN': ('Chaîne de construction', 'Construction chain'), 'EXTERNAL_DEPENDENCIES': ('Dépendances externes', 'External dependencies'),
            'KNOWLEDGE': ('Connaissance', 'Knowledge'), 'GAPS': ('Écarts acceptés et revus', 'Gaps accepted and reviewed'),
            'VERIFICATION': ('Vérifications de conception', 'Design verification'), 'PLANNING': ('Planification', 'Planning'),
            'RUNTIME': ('Architecture d’exécution', 'Runtime architecture'), 'SECURITY_ZONES': ('Zones de sécurité', 'Security zones'),
            'COMPLIANCE': ('Conformité', 'Compliance'), 'INDEPENDENT_REVIEW': ('Revue indépendante', 'Independent review')}


def criterion(code, lang):
    return CRITERIA.get(code, (code, code))[0 if lang == 'fr' else 1]


MONTHS = {'fr': ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'],
          'en': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']}


def n(value, digits=0, lang='fr'):
    if value is None: return '—'
    q = Decimal(1) if digits == 0 else Decimal(1).scaleb(-digits)
    text = '{:,}'.format(Decimal(value).quantize(q))
    return text.replace(',', '\u202f').replace('.', ',') if lang == 'fr' else text


def keur(value, lang='fr', currency='EUR'):
    v = Decimal(value)
    symbol = '€' if currency == 'EUR' else currency
    if abs(v) < 10000: return n(v, 0, lang) + '\u00a0' + symbol
    return (n(v / 1000000, 2, lang) + '\u00a0M' + symbol) if abs(v) >= 1000000 else (n(v / 1000, 0, lang) + '\u00a0k' + symbol)


MONTHS_FULL = {'fr': ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
               'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']}


def day(iso, lang='fr', full=False):
    y, m, d = iso.split('-')
    return '%d %s %s' % (int(d), (MONTHS_FULL if full else MONTHS)[lang][int(m) - 1], y)


# ------------------------------------------------------------------ inline SVG charts (no library)

def bar_chart(categories, series, width=760, height=300, unit='', lang='fr'):
    top = max([float(v) for _, vals, _ in series for v in vals] + [1]) * 1.12
    # room for two label lines, and enough width per category for about fourteen characters at the axis font size
    width = max(width, 70 + 16 + 90 * len(categories));height = max(height, int(width * 0.4))
    left, bottom, right = 70, 44, 16;plot_w, plot_h = width - left - right, height - bottom - 24
    group = plot_w / max(len(categories), 1);bar = min(34, group * 0.8 / max(len(series), 1))
    out = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (width, height)]
    for i in range(5):
        y = 24 + plot_h - plot_h * i / 4
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/>' % (left, width - right, y, y))
        out.append('<text x="%d" y="%.1f" class="axis" text-anchor="end">%s</text>' % (left - 8, y + 4, H(n(top * i / 4, 0, lang) + unit)))
    for ci, cat in enumerate(categories):
        x0 = left + group * ci + (group - bar * len(series)) / 2
        for si, (name, vals, css) in enumerate(series):
            v = float(vals[ci]);h = plot_h * v / top;x = x0 + si * bar;y = 24 + plot_h - h
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" class="%s"><title>%s : %s</title></rect>' % (x, y, bar - 3, h, css, H(name), n(v, 0, lang)))
            if h > 16: out.append('<text x="%.1f" y="%.1f" class="val" text-anchor="middle">%s</text>' % (x + (bar - 3) / 2, y - 4, n(v, 0, lang)))
        out.append('<text x="%.1f" y="%d" class="axis" text-anchor="middle">%s</text>' % (left + group * ci + group / 2, height - 26, ''.join('<tspan x="%.1f" dy="%s">%s</tspan>' % (left + group * ci + group / 2, '0' if k == 0 else '1.1em', H(part)) for k, part in enumerate(_wrap(str(cat))))))
    out.append('</svg>')
    legend = ''.join('<span class="key"><i class="%s"></i>%s</span>' % (css, H(name)) for name, _, css in series)
    return '<div class="legend">' + legend + '</div>' + ''.join(out)


def _runs(path):
    """Consecutive steps of the same project, grouped: [(namespace, [steps])]."""
    out = []
    for c in path:
        if out and out[-1][0] == c['namespace']: out[-1][1].append(c)
        else: out.append((c['namespace'], [c]))
    return out


def _wrap(text, width=14):
    lines, line = [], ''
    for word in text.split():
        if line and len(line) + 1 + len(word) > width: lines.append(line);line = word
        else: line = (line + ' ' + word).strip()
    lines.append(line)
    return lines[:2] if len(lines) <= 2 else [lines[0], (lines[1] + '…')]


def gantt(phases, critical=(), width=900, row=30, lang='fr'):
    from datetime import date
    starts = [date.fromisoformat(p['start']) for p in phases];ends = [date.fromisoformat(p['end']) for p in phases]
    t0, t1 = min(starts), max(ends);span = max((t1 - t0).days, 1)
    longest = max((len(p['name']) for p in phases), default=10);left = int(min(420, max(230, 24 + 6.6 * longest)));plot = width - left - 16
    height = 34 + row * len(phases)
    out = ['<svg viewBox="0 0 %d %d" class="chart gantt" role="img">' % (width, height)];first = date(t0.year, t0.month, 1);month = first
    while month <= t1:
        x = left + plot * max((month - t0).days, 0) / span
        out.append('<line x1="%.1f" x2="%.1f" y1="18" y2="%d" class="grid"/>' % (x, x, height))
        out.append('<text x="%.1f" y="13" class="axis">%s</text>' % (x + 2, MONTHS[lang][month.month - 1] + (' ' + str(month.year)[2:] if month.month == 1 or month == first else '')))
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    for i, p in enumerate(phases):
        s, e = date.fromisoformat(p['start']), date.fromisoformat(p['end']);y = 24 + i * row
        x = left + plot * (s - t0).days / span;w = max(plot * (e - s).days / span, 4)
        out.append('<text x="8" y="%.1f" class="label">%s</text>' % (y + row / 2 + 4, H(p['name'][:60])))
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="3" class="%s"><title>%s — %s → %s</title></rect>' % (
            x, y + 5, w, row - 10, 'crit' if p['id'] in critical else 'phase', H(p['objective']), p['start'], p['end']))
    out.append('</svg>')
    return ''.join(out)


def heatmap(counts, lang='fr'):
    out = ['<svg viewBox="0 0 330 300" class="chart heat" role="img">']
    for p in range(1, 6):
        for i in range(1, 6):
            score = p * i;x = 40 + (i - 1) * 56;y = 10 + (5 - p) * 52
            out.append('<rect x="%d" y="%d" width="52" height="48" rx="4" class="%s"/>' % (x, y, 'h-high' if score >= 15 else 'h-mid' if score >= 8 else 'h-low'))
            if counts.get((p, i)): out.append('<text x="%d" y="%d" class="heatn" text-anchor="middle">%d</text>' % (x + 26, y + 31, counts[(p, i)]))
    impact, likelihood = ('Impact →', 'Probabilité →') if lang == 'fr' else ('Impact →', 'Likelihood →')
    out.append('<text x="180" y="292" class="axis" text-anchor="middle">%s</text><text x="14" y="140" class="axis" transform="rotate(-90 14 140)" text-anchor="middle">%s</text>' % (impact, likelihood))
    out.append('</svg>')
    return ''.join(out)


# ------------------------------------------------------------------ figures shared by both languages

def figures(g, gates):
    from air.acceptance import walk
    from air.delivery_calc import chosen_by_project, compliance, estimates, programme, roadmaps, single_currency
    objects = list(g.by_id.values())
    est = estimates(objects, g.by_id);maps = roadmaps(objects, g.by_id, est)
    currency = single_currency([c['body']['amount']['currency'] for c in g.of('CostItem')]
                               + [r['currency'] for r in est] + [r['currency'] for r in maps])
    years = defaultdict(lambda: {'CAPEX': Decimal(0), 'OPEX': Decimal(0), 'LABOUR': Decimal(0)})
    for c in g.of('CostItem'):
        b = c['body'];amount = Decimal(b['amount']['value'])
        if b['recurrence'] == 'ONCE': years[int(b['start'][:4])][b['nature']] += amount;continue
        end = b.get('end') or str(int(b['start'][:4]) + 2) + b['start'][4:];y, m = map(int, b['start'].split('-'));ye, me = map(int, end.split('-'))
        per = amount if b['recurrence'] == 'MONTHLY' else amount / 12
        while (y, m) <= (ye, me):
            years[y][b['nature']] += per
            if b['nature'] == 'OPEX' and b.get('category') == 'LABOUR': years[y]['LABOUR'] += per
            m += 1
            if m > 12: y, m = y + 1, 1
    chosen = chosen_by_project(maps);prog = programme(maps)
    risks = g.of('RiskAssessment')
    return {'currency': currency, 'est': est, 'maps': maps, 'chosen': chosen, 'comp': compliance(objects, g.by_id), 'walk': walk(objects, None, owned_only=False),
            'programme': prog, 'years': years, 'opex_labour': max(years.values(), key=lambda v: v['OPEX'])['LABOUR'] if years else Decimal(0), 'capex': sum(v['CAPEX'] for v in years.values()), 'opex': max((v['OPEX'] for v in years.values()), default=Decimal(0)),
            'ai_sub': sum(r['subscription'] for r in chosen.values() if r['uses_ai']) if any(r['uses_ai'] for r in chosen.values()) else sum(r['subscription'] for r in est),
            'saving': sum(r['delta_cost'] for r in chosen.values() if r['delta_cost'] is not None), 'without': sum(r['without_ai_pd'] for r in est), 'with_ai': sum(r['with_ai_pd'] for r in est),
            'blocking': sorted({c for x in gates for c in x['blocking']}),
            'behind': [(x['namespace'], c['detail']['behind_latest']['count']) for x in gates for c in x['criteria']
                       if c['code'] == 'EXTERNAL_DEPENDENCIES' and c['detail'].get('behind_latest', {}).get('count')], 'ready': all(x['result'] == 'READY_TO_BUILD' for x in gates),
            'human': sorted({c['code'] for x in gates for c in x['criteria'] if c['status'] == 'NOT_MET' and c.get('owner') == 'human'}),
            'risks': risks, 'top_risks': sorted(risks, key=lambda a: -a['body']['likelihood'] * a['body']['impact'])[:5],
            'sims': [r for r in g.of('VerificationRun') if r['body']['method'] == 'SIMULATION']}


# ------------------------------------------------------------------ storyline

def storyline(g, gates, request, lang='fr', f=None):
    """The slides as data, in one language, written for an executive who is not an architect.

    Every title is a complete sentence in business words that states a conclusion; every slide that carries a
    consequence says it in one more sentence. The figures come from the pinned baselines; expert terms stay out.
    """
    from air.deliverables import mid
    f = f or figures(g, gates)
    T = lambda fr, en: fr if lang == 'fr' else en
    N = lambda v, d=0: n(v, d, lang)
    K = lambda v: keur(v, lang, f['currency'] or '')
    est, maps, chosen, comp, wk = f['est'], f['maps'], f['chosen'], f['comp'], f['walk']
    goals = g.of('Goal');units = g.of('ConstructionUnit');blocks = g.of('ArchitectureBlock')
    without, with_ai, capex, opex, ai_sub, blocking = f['without'], f['with_ai'], f['capex'], f['opex'], f['ai_sub'], f['blocking']
    top_risks, risks = f['top_risks'], f['risks']
    names_of = request.get('projects', {})
    def label(ns):
        value = names_of.get(ns)
        if isinstance(value, dict): return value.get(lang) or value.get('fr') or ns
        return value or ns.split('.')[-1].replace('-', ' ').capitalize()
    q = lambda text: ('« %s »' if lang == 'fr' else '“%s”') % text
    slides = []

    def slide(key, section, title, blocks_, notes='', sources=(), kind='content'):
        slides.append({'key': key, 'section': section, 'title': title, 'kind': kind, 'blocks': blocks_, 'notes': notes,
                       'sources': sorted({o['meta']['type'][4:] for o in sources if o})})

    def meaning(text):
        return {'type': 'takeaway', 'label': T('Ce que cela signifie', 'What this means'), 'text': text}

    # ---- what remains before starting, in words a sponsor can act on
    NUM = {1: T('une', 'one'), 2: T('deux', 'two'), 3: T('trois', 'three'), 4: T('quatre', 'four'), 5: T('cinq', 'five')}
    def counts(gate):
        out = {}
        for c in gate['criteria']:
            if c['status'] != 'NOT_MET': continue
            d = c.get('detail') or {}
            out[c['code']] = {'GAPS': len(d.get('accepted_pending_review', [])) or len(d.get('open', [])), 'VERIFICATION': len(d.get('design_cases_open', [])),
                              'COMPLIANCE': len(d.get('unmapped', []))}.get(c['code'], 1)
        return out
    def phrase(code, count, many=False):
        if code == 'GAPS':
            return (T('faire approuver, par une personne indépendante, le point laissé ouvert par décision', 'have an independent person approve the point left open by decision') if count == 1
                    else T('faire approuver, par une personne indépendante, les %d points laissés ouverts par décision', 'have an independent person approve the %d points left open by decision') % count)
        if code == 'VERIFICATION':
            if not count: return T('planifier les tests de réception', 'plan the acceptance tests')
            return T('faire qualifier explicitement les preuves de conception par un relecteur indépendant',
                     'obtain explicit design evidence qualification from an independent reviewer')
        if code == 'INDEPENDENT_REVIEW':
            return (T('faire relire chaque dossier par une personne qui n’a pas participé à sa conception', 'have each dossier reviewed by someone who did not take part in its design') if many
                    else T('faire relire le dossier par une personne qui n’a pas participé à sa conception', 'have the dossier reviewed by someone who did not take part in its design'))
        if code == 'COMPLIANCE':
            return (T('préciser qui met en œuvre une exigence de sécurité ou de conformité', 'state who delivers one security or compliance requirement') if count == 1
                    else T('préciser qui met en œuvre %d exigences de sécurité ou de conformité', 'state who delivers %d security or compliance requirements') % count)
        return T('compléter la conception : %s', 'complete the design: %s') % criterion(code, lang).lower()
    ORDER = ['REFERENCE_CLOSURE', 'STRUCTURE', 'CONSTRUCTION_CHAIN', 'EXTERNAL_DEPENDENCIES', 'KNOWLEDGE', 'PLANNING', 'RUNTIME', 'SECURITY_ZONES', 'COMPLIANCE',
             'VERIFICATION', 'GAPS', 'INDEPENDENT_REVIEW']
    def actions(gate):
        c = counts(gate)
        return [phrase(code, c[code]) for code in ORDER if code in c]
    total = {}
    for x in gates:
        for code, count in counts(x).items(): total[code] = total.get(code, 0) + count
    human_actions = [phrase(code, total[code], len(gates) > 1) for code in ORDER if code in total]
    design_left = [code for code in total if code not in ('GAPS', 'VERIFICATION', 'INDEPENDENT_REVIEW')]
    human_left = [code for code in total if code in ('GAPS', 'VERIFICATION', 'INDEPENDENT_REVIEW')]
    def points(count):
        return (T('un point', 'one point') if count == 1 else T('%s points', '%s points') % NUM.get(count, str(count)))
    def remaining():
        if design_left and human_left:
            return (T('la conception doit être complétée sur %s, puis %s obtenue(s)', 'the design must be completed on %s, then %s obtained')
                    % (points(len(design_left)), (T('une validation', 'one approval') if len(human_left) == 1 else T('%s validations', '%s approvals') % NUM.get(len(human_left), str(len(human_left))))))
        if design_left: return T('la conception doit encore être complétée sur %s', 'the design must still be completed on %s') % points(len(design_left))
        return approvals(len(human_left))
    def approvals(count):
        return (T('une validation, déjà identifiée', 'one approval, already identified') if count == 1
                else T('%s validations, déjà identifiées', '%s approvals, already identified') % NUM.get(count, str(count)))
    projects_of = sorted({r['namespace'] for r in maps} | {x['namespace'] for x in gates})
    project_word = lambda ns: T('le projet ', 'the ') + q(label(ns)) + T('', ' project')
    project_list = ', '.join(label(ns) for ns in projects_of)

    # ---- cover
    title = request['title'] if lang == 'fr' else request.get('title_en', request['title'])
    client = request.get('client', T('la direction', 'executive management'));provider = request.get('provider', T('l’équipe d’architecture', 'the architecture team'))
    slide('cover', '', title, [{'type': 'cover', 'subtitle': T('Architecture de la solution, plan de réalisation et décisions attendues',
                                                               'Solution architecture, delivery plan and decisions expected'),
                               'meta': T('Pour ', 'For ') + client + T(' · par ', ' · by ') + provider + T(' · établi à partir de ', ' · built from ')
                                       + str(len(request['baselines'])) + T(' versions vérifiées du dossier', ' verified versions of the dossier')}], kind='cover')

    # ---- summary: the answer first
    picks = [chosen[ns] for ns in sorted(chosen)]
    chosen_names = T(' et ', ' and ').join('%s %s' % (q(r['name']), T('pour ', 'for ') + project_word(r['namespace'])) for r in picks)
    finish = max((r['end'] for r in picks), default=None);D = lambda iso: day(iso, lang, full=True)
    zones = len(g.of('NetworkZone'))
    zone_of = {c['meta']['id']: c['body'].get('zone', {}).get('id') for c in g.of('RuntimeComponent')}
    crossings = [c for c in g.of('Connection') if zone_of.get(c['body']['source']['id']) != zone_of.get(c['body']['target']['id'])]
    clear = sum(1 for c in crossings if not c['body'].get('encrypted'))
    invest = capex + f['saving']
    low = any(r['confidence'] == 'LOW' for r in est)
    summary = [
        (T('Ce que nous construisons', 'What we build'),
         (T('%s projets (%s) : %d composants applicatifs, réalisés en %d lots de travaux, au service de %d objectifs mesurables.',
            '%s projects (%s): %d application components, delivered in %d work packages, serving %d measurable goals.')
          % (NUM.get(len(projects_of), str(len(projects_of))).capitalize(), project_list, len(blocks), len(units), len(goals))) if len(projects_of) > 1 else
         T('%d composants applicatifs, réalisés en %d lots de travaux, au service de %d objectifs mesurables.',
           '%d application components, delivered in %d work packages, serving %d measurable goals.') % (len(blocks), len(units), len(goals))),
        (T('Comment', 'How'),
         T('Les composants communiquent par des interfaces documentées et se transmettent les informations en temps réel. '
           'Les données sensibles restent dans %d zones protégées%s.', 'Components talk through documented interfaces and pass information on in real time. '
           'Sensitive data stays in %d protected zones%s.') % (zones, T(', et chaque échange entre zones est chiffré', ', and every exchange between zones is encrypted') if not clear else '')),
        (T('Quand et combien', 'When and how much'),
         (T('Fin des travaux visée le %s. ', 'Work is planned to finish on %s. ') % D(finish) if finish else T('Le calendrier reste à établir. ', 'The schedule is still to be set. '))
         + (T('L’investissement est de %s (%s sans assistance de l’IA) ; ', 'The investment is %s (%s without AI assistance); ') % (K(invest), K(capex)) if f['saving'] < 0
            else T('L’investissement est de %s ; ', 'The investment is %s; ') % K(capex))
         + T('le fonctionnement coûtera ensuite %s par an%s.', 'running costs will then be %s a year%s.')
         % (K(opex), (T(', dont %s de personnel', ', of which %s is staff') % K(f['opex_labour'])) if f['opex_labour'] else '')),
        (T('Où nous en sommes', 'Where we stand'),
         T('Le dossier est prêt : les travaux peuvent commencer.', 'The dossier is ready: work can start.') if f['ready'] else
         T('La conception est complète. Avant de lancer les travaux, il reste à %s.', 'The design is complete. Before work starts, we still need to %s.')
         % (T(' ; ', '; ').join(human_actions) if human_actions else T('corriger quelques points de conception', 'fix a few design points'))),
    ]
    if f['ready']:
        headline = T('Le programme peut démarrer : fin visée le %s pour %s d’investissement', 'The programme can start: finish planned for %s at an investment of %s') % (D(finish), K(invest))
    elif finish:
        headline = ((T('Fin visée le %s pour %s d’investissement ; le lancement attend %s', 'Finish planned for %s at an investment of %s; the start awaits %s')
                     % (D(finish), K(invest), approvals(len(human_left)))) if not design_left else
                    (T('Fin visée le %s pour %s d’investissement ; avant le lancement, %s', 'Finish planned for %s at an investment of %s; before the start, %s')
                     % (D(finish), K(invest), remaining())))
    else:
        headline = T('Avant le lancement, %s', 'Before the start, %s') % remaining()
    ask = (T('Nous vous demandons d’approuver le scénario recommandé pour chaque projet (%s), un investissement de %s et les validations nécessaires au lancement.',
             'We ask you to approve the recommended scenario for each project (%s), an investment of %s and the approvals needed to start.') % (chosen_names, K(invest))
           if picks else T('Nous vous demandons de choisir un scénario de réalisation pour chaque projet.', 'We ask you to choose a delivery scenario for each project.'))
    slide('summary', T('Synthèse', 'Management summary'), headline, [{'type': 'summary', 'rows': summary}, {'type': 'ask', 'text': ask}]
          + ([{'type': 'note', 'text': T('Les durées et les coûts reposent sur des estimations qui seront affinées au cours des premiers mois.',
                                         'Durations and costs rest on estimates that will be refined during the first months.')}] if low else []),
          notes=T('Commencer par la réponse : la suite du document justifie chaque ligne.', 'Start with the answer: the rest of the deck supports each line.'), sources=goals + units + blocks)

    # ---- where we stand: what remains before starting, per project
    rows = []
    for x in gates:
        todo = actions(x)
        rows.append([label(x['namespace']), T('oui', 'yes') if x['result'] == 'READY_TO_BUILD' else T('pas encore', 'not yet'),
                     (T(' ; ', '; ').join(todo) if todo else T('rien', 'nothing')) + '.'])
    behind = [(ns, count) for ns, count in f['behind']]
    if f['ready']: gate_title = T('Le dossier est prêt : les travaux peuvent commencer', 'The dossier is ready: work can start')
    elif design_left: gate_title = T('Avant de lancer les travaux, %s ; chaque action est identifiée', 'Before work starts, %s; each action is identified') % remaining()
    elif len(human_left) == 1: gate_title = T('Avant de lancer les travaux, une validation doit encore être obtenue ; elle est identifiée', 'Before work starts, one approval is still needed; it is identified')
    else: gate_title = T('Avant de lancer les travaux, %s validations doivent encore être obtenues ; chacune est identifiée', 'Before work starts, %s approvals are still needed; each is identified') % NUM.get(len(human_left), str(len(human_left)))
    slide('gate', T('Où nous en sommes', 'Where we stand'), gate_title,
          [{'type': 'table', 'head': [T('Projet', 'Project'), T('Prêt à lancer', 'Ready to start'), T('Ce qu’il reste à faire', 'What remains to be done')], 'rows': rows}]
          + [{'type': 'note', 'text': T('%s doit être mis à jour sur la dernière version des éléments qu’il partage avec les autres projets (%d éléments).',
                                        '%s must be brought up to date with the latest version of what it shares with other projects (%d items).') % (label(ns), c)} for ns, c in behind]
          + [meaning(T('Aucun obstacle de conception ne s’oppose au lancement : ce qui reste relève de validations par des personnes habilitées, qui peuvent être planifiées dès maintenant.',
                       'No design obstacle stands in the way: what remains are approvals by authorised people, which can be scheduled now.')
                     if not design_left else
                     T('Des points de conception restent à compléter avant les validations.', 'Some design points must be completed before the approvals.'))],
          notes=T('Ce verdict est calculé sur les versions citées en annexe ; il ne vaut ni signature ni garantie.', 'This verdict is computed on the versions listed in the appendix; it is neither a signature nor a warranty.'),
          sources=g.of('VerificationRun'))

    # ---- situation and complication
    op = {'EQ': '=', 'LTE': '≤', 'GTE': '≥'}
    slide('context', T('Contexte', 'Situation'), T('Le programme poursuit %d objectifs mesurables', 'The programme pursues %d measurable goals') % len(goals),
          [{'type': 'table', 'head': [T('Objectif', 'Goal'), T('Résultat attendu', 'Expected result'), T('Cible', 'Target')],
            'rows': [[x['meta']['name'], x['body']['outcome'], '; '.join('%s %s %s' % (op.get(tg['operator'], '?'), tg['value'].get('value', '?'), tg.get('unit', '')) for tg in x['body']['targets'])] for x in goals]},
           meaning(T('Chaque objectif a une cible chiffrée : c’est sur ces cibles que le programme sera jugé.', 'Each goal has a numeric target: the programme will be judged on these targets.'))],
          sources=goals)
    pains = [(j['meta']['name'], p) for j in g.of('CustomerJourney') for s in j['body']['steps'] for p in s.get('pain_points', [])]
    level = lambda score: T('élevé', 'high') if score >= 15 else T('moyen', 'medium') if score >= 8 else T('faible', 'low')
    slide('stakes', T('Enjeux', 'Complication'), T('Sans ce programme, %d difficultés rencontrées par les utilisateurs et %d risques identifiés resteraient sans réponse',
                                                  'Without this programme, %d difficulties met by users and %d identified risks would remain unaddressed') % (len(pains), len(risks)),
          [{'type': 'columns', 'items': [(T('Difficultés des utilisateurs', 'User difficulties'), ['%s : %s' % pp for pp in pains[:6]] or [T('aucune difficulté relevée', 'no difficulty noted')]),
                                         (T('Risques principaux', 'Main risks'), ['%s (%s %s)' % (g.name(a['body']['risk']), T('niveau', 'level'), level(a['body']['likelihood'] * a['body']['impact'])) for a in top_risks]
                                          or [T('aucun risque évalué', 'no risk assessed')])]}],
          notes=T('Ce qui arrive si rien ne change.', 'What happens if nothing changes.'), sources=g.of('CustomerJourney') + risks)

    # ---- business
    streams = g.of('ValueStream')
    slide('streams', T('Métier', 'Business'), T('La valeur est créée dans %d grands enchaînements d’activités, de la demande du client jusqu’au résultat',
                                              'Value is created in %d end-to-end chains of activities, from the customer request to the result') % len(streams),
          [{'type': 'flows', 'items': [(s['meta']['name'], [st['name'] + ((' · ' + st['lead_time']) if st.get('lead_time') else '') for st in s['body']['stages']]) for s in streams]}], sources=streams)
    caps = g.of('Capability');by_ctx = defaultdict(list)
    for c in caps: by_ctx[g.name(c['body']['context']) if 'context' in c['body'] else '—'].append(c['meta']['name'])
    slide('capabilities', T('Métier', 'Business'), T('Le programme couvre %d savoir-faire de l’entreprise, répartis en %d domaines de responsabilité',
                                                   'The programme covers %d business capabilities, grouped into %d areas of responsibility') % (len(caps), len(by_ctx)),
          [{'type': 'grid', 'items': sorted(by_ctx.items())}], sources=caps)
    journeys = g.of('CustomerJourney')
    channel = {'MOBILE': T('mobile', 'mobile'), 'WEB': 'web', 'API': T('échange entre systèmes', 'system-to-system'), 'PHONE': T('téléphone', 'phone'),
               'EMAIL': 'e-mail', 'BRANCH': T('agence', 'branch'), 'AGENT': T('assistant IA', 'AI assistant'), 'CHAT': T('conversation', 'chat')}
    slide('journeys', T('Métier', 'Business'), T('%d parcours utilisateurs ont été décrits étape par étape, avec leurs difficultés', '%d user journeys were described step by step, with their difficulties') % len(journeys),
          [{'type': 'table', 'head': [T('Parcours', 'Journey'), T('Utilisateur', 'User'), T('Canaux', 'Channels'), T('Étapes', 'Steps'), T('Difficultés', 'Difficulties')],
            'rows': [[j['meta']['name'], g.name(j['body']['persona']), ', '.join(sorted({channel.get(s['channel'], s['channel'].lower()) for s in j['body']['steps']})), len(j['body']['steps']),
                      sum(len(s.get('pain_points', [])) for s in j['body']['steps'])] for j in journeys]}], sources=journeys)

    # ---- solution
    ids = {b['meta']['id']: mid(b['meta']['id']) for b in blocks};diagram = ['flowchart LR']
    for b in blocks: diagram.append('  %s["%s"]' % (ids[b['meta']['id']], b['meta']['name'].replace('"', "'")))
    provider_of = {c['id']: b['meta']['id'] for b in blocks for c in b['body']['provided_contracts']}
    for b in blocks:
        for c in b['body']['required_contracts']:
            if c['id'] in provider_of and provider_of[c['id']] != b['meta']['id']: diagram.append('  %s --> %s' % (ids[b['meta']['id']], ids[provider_of[c['id']]]))
    slide('architecture', 'Solution', T('La solution est découpée en %d composants indépendants, chacun responsable de ses propres données',
                                        'The solution is split into %d independent components, each responsible for its own data') % len(blocks),
          [{'type': 'mermaid', 'code': '\n'.join(diagram)},
           meaning(T('Chaque composant peut évoluer ou être remplacé sans remettre en cause les autres. Une flèche indique qu’un composant utilise les services d’un autre.',
                     'Each component can change or be replaced without affecting the others. An arrow means one component uses the services of another.'))], sources=blocks)
    events = g.of('Event')
    results = [r['body']['result'] for r in f['sims']]
    if not results: verdict = T('les temps de réponse n’ont pas encore été simulés', 'response times have not been simulated yet')
    elif all(x == 'PASS' for x in results): verdict = T('les simulations enregistrées déclarent les objectifs atteints sur le modèle',
                                                       'recorded simulations declare targets met on the model')
    else: verdict = T('les résultats déclarés comprennent %d échec(s) et %d cas non conclusifs',
                     'declared results include %d failure(s) and %d inconclusive case(s)') % (results.count('FAIL'), results.count('INCONCLUSIVE'))
    labels = {'PASS': T('atteint', 'met'), 'FAIL': T('non atteint', 'not met'), 'INCONCLUSIVE': T('non conclusif', 'inconclusive')}
    sims = [T('%s : résultat déclaré %s', '%s: declared result %s') % (g.name(r['body']['scenario']) if r['body'].get('scenario') else r['meta']['name'],
                                                                    labels[r['body']['result']]) for r in f['sims'][:3]]
    slide('events', 'Solution', T('Les informations circulent en temps réel entre les composants ; %s', 'Information flows in real time between components; %s') % verdict,
          [{'type': 'bullets', 'items': [T('%d types de messages sont échangés entre les composants dès qu’un fait se produit.', '%d kinds of messages are exchanged between components as soon as something happens.') % len(events)] + sims},
           meaning(T('Un résultat enregistré et son niveau de preuve sont des déclarations ; ils ne démontrent pas les temps de réponse du système.',
                     'A recorded result and its proof level are declarations; they do not establish system response times.') if results else
                   T('Une simulation des temps de réponse est à prévoir avant le lancement.', 'A response-time simulation should be planned before the start.'))],
          notes=T('La calibration numérique ne qualifie ni la provenance ni la portée des mesures.', 'Numerical calibration does not qualify the provenance or scope of measurements.'),
          sources=events + f['sims'])
    navs = g.of('NavigationMap');s = wk['summary']
    open_ops = sorted({o for c in wk['coverage'] for o in c['operations_uncovered']} | {o for j in wk['journeys'] for o in j['not_exercised']})
    if s['scenarios'] and s['pass'] == s['scenarios']:
        ui_title = T('Les %d parcours d’utilisation testés sur plan fonctionnent ; les tests sur le logiciel suivront sa construction',
                     'All %d usage scenarios tested on the design work; tests on the software will follow its construction') % s['scenarios']
    else:
        ui_title = T('%d parcours d’utilisation sur %d fonctionnent sur plan ; les autres révèlent des défauts de conception à corriger',
                     '%d of %d usage scenarios work on the design; the others reveal design defects to fix') % (s['pass'], s['scenarios'])
    slide('ui', 'Solution', ui_title,
          [{'type': 'table', 'head': [T('Application', 'Application'), T('Écrans', 'Screens'), T('Écrans testés', 'Screens tested'), T('Enchaînements testés', 'Transitions tested'), T('Parcours de test', 'Test scenarios')],
            'rows': [[c['name'], c['screens'], c['screens_covered'], '%d / %d' % (c['transitions_covered'], c['transitions']), c['scenarios']] for c in wk['coverage']]}]
          + ([{'type': 'note', 'text': T('%d fonction(s) ne sont pas encore couvertes par un parcours de test : %s.', '%d function(s) are not yet covered by a test scenario: %s.') % (len(open_ops), ', '.join(open_ops))}] if open_ops else [])
          + [meaning(T('Les parcours ont été vérifiés sur les plans, avant toute ligne de code : les défauts de navigation sont corrigés au moment où ils coûtent le moins. '
                       'Ces mêmes parcours serviront de tests de réception puis de tests de non-régression.',
                       'The scenarios were checked on the plans, before any code is written: navigation defects are fixed when they cost least. '
                       'The same scenarios will serve as acceptance tests, then as regression tests.'))],
          sources=navs + g.of('AcceptanceScenario'))
    covered = sum(1 for r in comp if r['implemented_in'])
    stages = Counter(st for r in comp for st in r['by_project'].values() if st != 'NOT_APPLICABLE')
    state_word = {'PLANNED': T('prévue', 'planned'), 'IMPLEMENTED': T('en place', 'in place'), 'VERIFIED': T('vérifiée', 'verified')}
    if covered == len(comp) and set(stages) <= {'PLANNED'}:
        sec_title = T('Les %d exigences de sécurité et de conformité ont chacune une solution prévue et un responsable ; aucune n’est encore vérifiée',
                      'All %d security and compliance requirements have a planned solution and an owner; none is verified yet') % len(comp)
    elif covered == len(comp):
        sec_title = T('Les %d exigences de sécurité et de conformité ont chacune une solution et un responsable', 'All %d security and compliance requirements have a solution and an owner') % len(comp)
    else:
        sec_title = T('%d exigences de sécurité et de conformité sur %d ont une solution ; les autres doivent encore être attribuées',
                      '%d of %d security and compliance requirements have a solution; the others must still be assigned') % (covered, len(comp))
    def carried(r):
        parts = []
        for ns, st in r['by_project'].items():
            if ns in r['delegated']: parts.append(T('%s : confiée à %s', '%s: handled by %s') % (label(ns), ', '.join(label(x) for x in r['delegated'][ns]) or T('personne', 'nobody')))
            else: parts.append('%s : %s' % (label(ns), '+'.join(state_word.get(x, x.lower()) for x in st.split('+'))))
        return T(' ; ', '; ').join(parts) or T('non attribuée', 'not assigned')
    def owner(r):
        roles = sorted({a for o in r['ownership'].values() for a in o['accountable']})
        if roles: return ', '.join(roles)
        scopes = {o['scope'] for o in r['ownership'].values()}
        return T('équipe du projet', 'project team') if scopes & {'BUSINESS', 'BOTH'} else T('à nommer', 'to be named')
    slide('security', 'Solution', sec_title,
          [{'type': 'table', 'max': 9, 'head': [T('Exigence', 'Requirement'), T('Mise en œuvre', 'Delivery'), T('Responsable', 'Owner')],
            'rows': [[r['name'], carried(r), owner(r)] for r in comp]},
           meaning((T('Les données circulent chiffrées entre toutes les zones protégées. ', 'Data travels encrypted between all protected zones. ') if not clear else '')
                   + T('Les exigences sont définies une fois pour toute l’entreprise et chaque projet dit comment il les respecte ; leur vérification reste à faire.',
                       'Requirements are defined once for the whole company and each project states how it meets them; they are still to be verified.'))],
          sources=g.of('NetworkZone') + [r['subject'] for r in comp])
    techs = g.of('Technology');decisions = g.of('Decision')
    status_word = {'ADOPT': T('adoptée', 'adopted'), 'TRIAL': T('en essai', 'on trial'), 'ASSESS': T('à évaluer', 'to assess'), 'HOLD': T('en retrait', 'on hold')}
    slide('tech', 'Solution', T('Les choix techniques reposent sur %d technologies et %d décisions documentées', 'Technical choices rest on %d technologies and %d documented decisions') % (len(techs), len(decisions)),
          [{'type': 'columns', 'items': [(T('Technologies retenues', 'Technologies chosen'), ['%s %s (%s)' % (t['meta']['name'], t['body']['version'], status_word.get(t['body']['status'], t['body']['status'].lower())) for t in techs[:10]]),
                                         (T('Décisions principales', 'Main decisions'), [d['meta']['name'] for d in decisions[:8]])]}], sources=techs + decisions)

    # ---- delivery
    if maps:
        status_name = {'RECOMMENDED': T('recommandé', 'recommended'), 'SELECTED': T('retenu', 'selected'), 'PROPOSED': T('alternative', 'alternative'), 'REJECTED': T('écarté', 'rejected')}
        saved = max((-r['delta_months'] for r in picks if r['delta_months'] is not None), default=None)
        if picks and all(r['uses_ai'] for r in picks) and saved and saved > 0:
            road_title = (T('%d scénarios de réalisation ont été comparés ; le scénario recommandé pour chaque projet s’appuie sur l’IA et fait gagner jusqu’à %s mois',
                            '%d delivery scenarios were compared; the scenario recommended for each project relies on AI and saves up to %s months') % (len(maps), N(saved, 1)))
        elif picks:
            road_title = T('%d scénarios de réalisation ont été comparés ; un scénario est recommandé pour chaque projet', '%d delivery scenarios were compared; one scenario is recommended for each project') % len(maps)
        else:
            road_title = T('%d scénarios de réalisation ont été comparés ; il reste à en choisir un par projet', '%d delivery scenarios were compared; one must still be chosen per project') % len(maps)
        slide('roadmaps', T('Réalisation', 'Delivery'), road_title,
              [{'type': 'table', 'head': [T('Projet', 'Project'), T('Scénario', 'Scenario'), T('Avec IA', 'With AI'), T('Durée', 'Duration'), T('Gain de temps', 'Time saved'),
                                          T('Coût total', 'Total cost'), T('dont outils d’IA', 'of which AI tools'), T('Avis', 'Opinion')],
                'rows': [[label(r['namespace']), r['name'], T('oui', 'yes') if r['uses_ai'] else T('non', 'no'), N(r['months'], 1) + T(' mois', ' months'),
                          (N(-r['delta_months'], 1) + T(' mois', ' months')) if r['delta_months'] is not None else T('référence', 'reference'),
                          K(r['total_cost']) if r['total_cost'] is not None else '—', K(r['subscription']), status_name.get(r['status'], r['status'].lower()).capitalize()] for r in maps]}]
              + [{'type': 'note', 'text': (T('Pour le projet %s, nous recommandons %s : ', 'For the %s project, we recommend %s: ') % (q(label(r['namespace'])), q(r['name'])))
                                          + ((T('il termine %s mois plus tôt que le scénario sans IA', 'it finishes %s months earlier than the scenario without AI') % N(-r['delta_months'], 1))
                                             if r['delta_months'] is not None and r['delta_months'] < 0 else T('c’est le scénario de référence', 'it is the reference scenario'))
                                          + (T(', pour un coût total de %s.', ', for a total cost of %s.') % K(r['total_cost']) if r['total_cost'] is not None else '.')} for r in picks],
              notes=' '.join(label(r['namespace']) + T(' : ', ': ') + r['rationale'] for r in picks), sources=[r['roadmap'] for r in maps])
        if picks:
            merged = [{**ph, 'id': r['namespace'] + '/' + ph['id'], 'name': label(r['namespace']) + ' · ' + ph['name']} for r in picks for ph in r['phases']]
            prog = f['programme'];path = prog['critical_path']
            critical = {c['namespace'] + '/' + c['phase'] for c in path}
            drivers = []
            for c in path:
                if label(c['namespace']) not in drivers: drivers.append(label(c['namespace']))
            if prog['issues']:
                gantt_title = T('Le calendrier doit être revu : %d dépendance(s) entre projets ne sont pas respectées', 'The schedule must be revised: %d dependency(ies) between projects are not respected') % len(prog['issues'])
            else:
                lead = list(dict.fromkeys(c['namespace'] for c in path))
                gantt_title = (T('Fin des travaux visée le %s ; la date dépend surtout de l’avancement du projet %s', 'Work is planned to finish on %s; the date depends mostly on the progress of the %s project')
                               % (D(finish), T(', puis du projet ', ' project, then of the ').join(q(label(ns)) for ns in lead)))
            kind = {'FINISH_TO_START': T('commence après la fin de', 'starts after the end of'), 'START_TO_START': T('commence en même temps que', 'starts together with'),
                    'FINISH_TO_FINISH': T('se termine après', 'ends after')}
            deps = ['%s %s (%s) %s %s (%s)' % (T('L’étape', 'The step'), q(d['phase_name']), label(d['from_namespace']), kind[d['kind']], q(d['target_name'] or d['target_phase']), label(d['namespace'] or '?'))
                    for d in prog['dependencies']]
            slide('gantt', T('Réalisation', 'Delivery'), gantt_title,
                  [{'type': 'svg', 'svg': gantt(merged, critical, lang=lang)},
                   {'type': 'note', 'text': T('Les barres foncées forment l’enchaînement qui fixe la date de fin : ', 'The dark bars form the sequence that sets the end date: ')
                                            + T(', puis ', ', then ').join('%s (%s)' % (label(ns), ' → '.join(c['name'] for c in group))
                                                                           for ns, group in _runs(path)) + '.'}]
                  + ([{'type': 'note', 'text': T('Liens entre projets : ', 'Links between projects: ') + T(' ; ', '; ').join(deps) + '.'}] if deps else [])
                  + ([{'type': 'ask', 'text': T('À corriger avant de valider le calendrier : ', 'To fix before approving the schedule: ') + T(' ; ', '; ').join(
                        '%s · %s' % (label(i['from_namespace']), i['phase_name']) for i in prog['issues']) + '.'}] if prog['issues'] else []),
                  notes=T('Un retard sur une barre foncée retarde la fin du programme.', 'A delay on a dark bar delays the end of the programme.'), sources=[r['roadmap'] for r in picks])
    if est:
        pct = N((without - with_ai) / without * 100) if without else '0'
        calibrate = any(r['confidence'] == 'LOW' for r in est)
        slide('ai', T('Réalisation', 'Delivery'), (T('Les outils d’IA pourraient réduire la charge de travail d’environ %s %% (%s jours), pour %s d’abonnements ; ce gain sera mesuré dès les premiers mois',
                                                     'AI tools could cut the workload by about %s%% (%s days), for %s of subscriptions; the gain will be measured from the first months')
                                                   if calibrate else T('Les outils d’IA réduisent la charge de travail de %s %% (%s jours), pour %s d’abonnements',
                                                                       'AI tools cut the workload by %s%% (%s days), for %s of subscriptions'))
              % (pct, N(without - with_ai), K(f['ai_sub'])),
              [{'type': 'svg', 'svg': bar_chart([r['unit'].replace(' service build', '').replace(' build', '') for r in est],
                                                [(T('Sans IA', 'Without AI'), [r['without_ai_pd'] for r in est], 's1'), (T('Avec IA', 'With AI'), [r['with_ai_pd'] for r in est], 's2')],
                                                unit=T(' j', ' d'), lang=lang)},
               meaning(T('Le gain porte sur la production (écriture du code, tests, documentation). La relecture humaine et la sécurité ne sont pas réduites.',
                         'The gain comes from production work (writing code, tests, documentation). Human review and security work are not reduced.'))],
              notes=T('Les réductions sont des hypothèses par type d’activité ; elles seront recalées sur les premières semaines de travail.', 'Reductions are assumptions per kind of activity; they will be adjusted on the first weeks of work.'),
              sources=[r['estimate'] for r in est])
    raci = [r for r in g.of('RaciAssignment') if r['body']['responsibility'] == 'A']
    phase_name = {'DELIVERY': T('réalisation', 'delivery'), 'OPERATIONS': T('exploitation', 'operations'), 'DESIGN': T('conception', 'design'), 'GOVERNANCE': T('pilotage', 'governance')}
    slide('raci', T('Réalisation', 'Delivery'), T('Chaque décision a un seul responsable : %d activités, %d décideurs', 'Every decision has a single owner: %d activities, %d decision makers')
          % (len({r['body']['activity'] for r in raci}), len({r['body']['role']['id'] for r in raci})),
          [{'type': 'table', 'head': [T('Activité', 'Activity'), T('Moment', 'Stage'), T('Qui décide', 'Who decides')],
            'rows': [[r['body']['activity'], phase_name.get(r['body']['phase'], r['body']['phase'].lower()), g.name(r['body']['role'])] for r in raci]}], sources=raci)

    # ---- finance and risks
    ys = sorted(f['years'])
    finance_title = (T('Un investissement de %s (%s sans IA), puis %s par an de fonctionnement', 'An investment of %s (%s without AI), then %s a year of running costs') % (K(invest), K(capex), K(opex))
                     if f['saving'] < 0 else T('Un investissement de %s, puis %s par an de fonctionnement', 'An investment of %s, then %s a year of running costs') % (K(capex), K(opex)))
    if f['opex_labour']: finance_title += T(', dont %s de personnel', ', of which %s is staff') % K(f['opex_labour'])
    slide('finance', T('Finances', 'Finance'), finance_title,
          [{'type': 'svg', 'svg': bar_chart([str(y) for y in ys], [(T('Investissement', 'Investment'), [f['years'][y]['CAPEX'] for y in ys], 's1'),
                                                                   (T('Fonctionnement', 'Running costs'), [f['years'][y]['OPEX'] for y in ys], 's2')], unit=' ' + (f['currency'] or ''), lang=lang)},
           {'type': 'note', 'text': T('Le coût d’une journée de travail, les volumes et l’hébergement sont des hypothèses à confirmer ; les abonnements aux outils d’IA (%s) s’ajoutent.',
                                      'The cost of a working day, volumes and hosting are assumptions to confirm; subscriptions to AI tools (%s) come on top.') % K(f['ai_sub'])}],
          sources=g.of('CostItem'))
    heat = Counter((a['body']['likelihood'], a['body']['impact']) for a in risks)
    bare = sum(1 for a in top_risks if not a['body'].get('mitigations'))
    slide('risks', T('Risques', 'Risks'), (T('%d risques ont été évalués ; les plus importants ont un plan d’action et un responsable', '%d risks were assessed; the most important have an action plan and an owner') % len(risks)) if not bare
          else (T('%d risques ont été évalués ; %d des plus importants n’ont pas encore de plan d’action', '%d risks were assessed; %d of the most important have no action plan yet') % (len(risks), bare)),
          [{'type': 'split', 'svg': heatmap(heat, lang), 'items': [T('%s : niveau %s, suivi par %s%s', '%s: %s level, followed by %s%s') % (
              g.name(a['body']['risk']), level(a['body']['likelihood'] * a['body']['impact']), a['body']['owner'].split(':')[-1].replace('-', ' '),
              (T(', ramené à %s après action', ', down to %s after action') % level(a['body']['residual_likelihood'] * a['body']['residual_impact'])) if 'residual_likelihood' in a['body'] else '')
              for a in top_risks]}], sources=risks)

    # ---- decisions
    decisions_asked = []
    if picks:
        decisions_asked.append(T('Approuver le scénario recommandé pour chaque projet (%s) et un investissement de %s, dont %s d’abonnements aux outils d’IA.',
                                 'Approve the recommended scenario for each project (%s) and an investment of %s, including %s of AI tool subscriptions.') % (chosen_names, K(invest), K(f['ai_sub'])))
    else:
        decisions_asked.append(T('Choisir un scénario de réalisation pour chaque projet.', 'Choose a delivery scenario for each project.'))
    if human_actions:
        decisions_asked.append(T('Désigner les personnes chargées des validations restantes : %s.', 'Appoint the people in charge of the remaining approvals: %s.') % T(' ; ', '; ').join(human_actions))
    decisions_asked.append(T('Autoriser un premier cycle de construction, au cours duquel les gains de l’IA et les temps de réponse seront mesurés.',
                             'Authorise a first construction cycle, during which AI gains and response times will be measured.'))
    decisions_asked += [T('Faire mettre à jour %s sur la dernière version des éléments partagés avec les autres projets.', 'Have %s brought up to date with the latest version of the items shared with other projects.') % label(ns) for ns, _ in behind]
    words = {1: T('Une décision', 'One decision'), 2: T('Deux décisions', 'Two decisions'), 3: T('Trois décisions', 'Three decisions'), 4: T('Quatre décisions', 'Four decisions'), 5: T('Cinq décisions', 'Five decisions')}
    slide('decision', T('Décision', 'Decision'), T('%s sont attendues aujourd’hui', '%s are expected today') % words.get(len(decisions_asked), str(len(decisions_asked))) if len(decisions_asked) > 1
          else T('Une décision est attendue aujourd’hui', 'One decision is expected today'),
          [{'type': 'numbered', 'items': decisions_asked},
           {'type': 'note', 'text': T('Le dossier livré (documents, parcours de test et tests de non-régression) sert de référence contractuelle, dans les versions citées en annexe.',
                                      'The delivered dossier (documents, test scenarios and regression tests) is the contractual reference, in the versions listed in the appendix.')}], kind='decision')
    slide('pins', T('Annexe', 'Appendix'), T('Chaque chiffre de ce document provient d’une version datée et vérifiable du dossier', 'Every figure in this document comes from a dated, verifiable version of the dossier'),
          [{'type': 'pins', 'pins': request['baselines'], 'lang': lang, 'labels': {p['id']: label(next((x['namespace'] for x in gates if x['baseline']['id'] == p['id']), p['id'])) for p in request['baselines']}},
           {'type': 'note', 'text': T('Ce document est un support de décision : l’engagement et la signature restent des actes des personnes habilitées.',
                                      'This document supports a decision: commitment and signature remain acts of authorised people.')}])
    wanted = AUDIENCES.get(request.get('audience', 'CONTRACT'))
    gate = [s for s in slides if s['key'] == 'gate']
    ordered = [x for s in slides if s['key'] != 'gate' for x in ([s] + gate if s['key'] == 'summary' else [s])]
    return [s for s in ordered if s['key'] in wanted]


# ------------------------------------------------------------------ HTML rendering

CSS = """
:root{--ink:#14201b;--muted:#5b6862;--line:#d6ddd9;--paper:#fff;--stage:#e7ebe9;--accent:#0b6e5b;--accent2:#b4541a;--soft:#eef3f1;--bad:#b3261e;--good:#2c7a4d}
*{box-sizing:border-box}html,body{margin:0;background:var(--stage);color:var(--ink);font:16px/1.45 "IBM Plex Sans","Segoe UI",system-ui,sans-serif}
.deck{display:flex;flex-direction:column;align-items:center;gap:28px;padding:56px 16px 28px}.deck[hidden]{display:none}
.slide{position:relative;width:min(1280px,100%);aspect-ratio:16/9;background:var(--paper);box-shadow:0 1px 3px rgba(0,0,0,.12);padding:3.2% 4% 5%;overflow:hidden;display:flex;flex-direction:column}
.tracker{font:600 12px/1 "IBM Plex Sans Condensed","Arial Narrow",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
h2{font:700 clamp(18px,2.3vw,30px)/1.18 "IBM Plex Sans Condensed","Arial Narrow",sans-serif;margin:0 0 18px;max-width:92%;text-wrap:balance}
.body{flex:1;min-height:0;display:flex;flex-direction:column;gap:14px;font-size:clamp(11px,1.15vw,16px);overflow:hidden}
.foot{position:absolute;left:4%;right:4%;bottom:2.2%;display:flex;justify-content:space-between;font-size:11px;color:var(--muted);border-top:1px solid var(--line);padding-top:6px}
table{border-collapse:collapse;width:100%}th{font:600 .82em "IBM Plex Sans Condensed",sans-serif;text-align:left;background:var(--soft);padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:4px 8px;border-bottom:1px solid var(--soft);vertical-align:top;font-size:.86em}
.cover{justify-content:center;background:linear-gradient(120deg,#0b3d33 0%,#0b6e5b 70%,#12806b 100%);color:#fff}
.cover h2{font-size:clamp(26px,3.8vw,52px);max-width:80%}.cover .sub{font-size:clamp(14px,1.6vw,22px);opacity:.92;max-width:70%}.cover .meta{margin-top:28px;font-size:13px;opacity:.8}
.cover .tracker,.cover .foot{color:#cfe8e1;border-color:rgba(255,255,255,.25)}
.summary{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.summary div{border-left:4px solid var(--accent);background:var(--soft);padding:10px 14px}
.summary b{display:block;font:700 .8em "IBM Plex Sans Condensed",sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);margin-bottom:4px}
.takeaway{border-left:4px solid var(--accent);background:#f4f8f6;padding:10px 14px;font-size:.95em}.takeaway b{display:block;font:700 .78em "IBM Plex Sans Condensed",sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);margin-bottom:3px}
.ask{border:2px solid var(--accent2);color:#6e2f0c;background:#fbf1ea;padding:10px 14px;font-weight:600}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:26px}.columns h3,.grid h3{font:600 .95em "IBM Plex Sans Condensed",sans-serif;margin:0 0 6px;color:var(--accent)}
ul,ol{margin:0;padding-left:1.2em}li{margin:.2em 0}
.flows{display:flex;flex-direction:column;gap:12px}.flow{display:flex;align-items:stretch;gap:6px;flex-wrap:wrap}.flow b{min-width:180px;font-size:.9em}
.flow span{background:var(--soft);border-left:3px solid var(--accent);padding:6px 16px 6px 10px;font-size:.85em;clip-path:polygon(0 0,94% 0,100% 50%,94% 100%,0 100%)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.grid div{border:1px solid var(--line);padding:8px 10px}.grid span{display:inline-block;background:var(--soft);margin:2px;padding:2px 6px;font-size:.82em}
.chart{width:100%;max-height:100%}.chart .grid{stroke:#e2e7e5}.chart .axis{font-size:11px;fill:var(--muted)}.chart .val{font-size:10px;fill:var(--ink)}.chart .label{font-size:12px;fill:var(--ink)}
.s1{fill:#9fb7af}.s2{fill:var(--accent)}.phase{fill:#9fc9bd}.crit{fill:var(--accent)}.h-low{fill:#dcebe4}.h-mid{fill:#f3d9a7}.h-high{fill:#eda793}.heatn{font:700 16px sans-serif;fill:var(--ink)}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted)}.key i{display:inline-block;width:12px;height:12px;margin-right:6px;vertical-align:-1px}.key i.s1{background:#9fb7af}.key i.s2{background:var(--accent)}
.split{display:grid;grid-template-columns:330px 1fr;gap:26px;align-items:start}
.gate td.met{color:var(--good)}.gate td.no{color:var(--bad);font-weight:600}.gate td.na{color:var(--muted)}
.note{font-size:.85em;color:var(--muted)}.mermaid{margin:0;display:flex;justify-content:center;max-height:100%}
.notes{display:none;position:absolute;inset:auto 4% 7% 4%;background:#fffbe6;border:1px solid #e6d58a;padding:8px 12px;font-size:12px}
body.show-notes .notes{display:block}
.bar{position:fixed;top:0;left:0;right:0;display:flex;justify-content:flex-end;gap:8px;padding:10px 16px;background:rgba(231,235,233,.92);z-index:5}
.bar button{font:600 12px "IBM Plex Sans",sans-serif;border:1px solid var(--line);background:#fff;color:var(--ink);padding:5px 10px;border-radius:4px;cursor:pointer}
.bar button[aria-pressed=true]{background:var(--accent);color:#fff;border-color:var(--accent)}.bar button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.nav{position:fixed;right:14px;bottom:12px;font:12px sans-serif;color:var(--muted);background:#fff;border:1px solid var(--line);padding:6px 10px;border-radius:4px}
@media print{@page{size:1280px 720px;margin:0}body{background:#fff}.deck{padding:0;gap:0}.slide{width:1280px;height:720px;box-shadow:none;page-break-after:always}.nav,.bar{display:none}}
@media (max-width:700px){.summary,.columns,.split{grid-template-columns:1fr}.slide{aspect-ratio:auto;min-height:60vh}}
"""

JS = """
(function(){var decks={},i=0,lang,nav=document.querySelector('.nav'),labels={fr:'n : notes · l : langue',en:'n: notes · l: language'};
document.querySelectorAll('.deck').forEach(function(d){decks[d.dataset.lang]=[].slice.call(d.querySelectorAll('.slide'))});
function cur(){return decks[lang]}
function show(){nav.textContent=(i+1)+' / '+cur().length+' · '+labels[lang]}
function go(k){i=Math.max(0,Math.min(cur().length-1,k));cur()[i].scrollIntoView({behavior:'smooth',block:'center'});show()}
function setLang(l){var keep=i;lang=l;document.documentElement.lang=l;
 document.querySelectorAll('.deck').forEach(function(d){d.hidden=d.dataset.lang!==l});
 document.querySelectorAll('.bar button').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.lang===l)});
 try{localStorage.setItem('air-deck-lang',l)}catch(e){} go(keep)}
document.querySelectorAll('.bar button').forEach(function(b){b.addEventListener('click',function(){setLang(b.dataset.lang)})});
document.addEventListener('keydown',function(e){if(['ArrowRight','PageDown',' '].indexOf(e.key)>=0){e.preventDefault();go(i+1)}
 else if(['ArrowLeft','PageUp'].indexOf(e.key)>=0){e.preventDefault();go(i-1)}else if(e.key==='Home')go(0);else if(e.key==='End')go(cur().length-1);
 else if(e.key==='n')document.body.classList.toggle('show-notes');else if(e.key==='l')setLang(lang==='fr'?'en':'fr')});
var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting&&cur().indexOf(x.target)>=0){i=cur().indexOf(x.target);show()}})},{threshold:.6});
Object.keys(decks).forEach(function(k){decks[k].forEach(function(x){io.observe(x)})});
var saved=null;try{saved=localStorage.getItem('air-deck-lang')}catch(e){}
setLang(saved||document.body.dataset.lang)})();
"""

# what a footer says instead of AIR type names
PLAIN = {'fr': {'Goal': 'objectifs', 'ArchitectureBlock': 'composants', 'ConstructionUnit': 'lots de travaux', 'Roadmap': 'scénarios de réalisation',
                'DeliveryEstimate': 'estimations', 'CostItem': 'coûts', 'RiskAssessment': 'risques', 'Risk': 'risques', 'CustomerJourney': 'parcours',
                'ValueStream': 'chaînes de valeur', 'Capability': 'savoir-faire', 'Event': 'messages', 'VerificationRun': 'vérifications',
                'NavigationMap': 'écrans', 'AcceptanceScenario': 'parcours de test', 'NetworkZone': 'zones protégées', 'Control': 'exigences',
                'QualityRequirement': 'exigences', 'Technology': 'technologies', 'Decision': 'décisions', 'RaciAssignment': 'responsabilités'},
         'en': {'Goal': 'goals', 'ArchitectureBlock': 'components', 'ConstructionUnit': 'work packages', 'Roadmap': 'delivery scenarios',
                'DeliveryEstimate': 'estimates', 'CostItem': 'costs', 'RiskAssessment': 'risks', 'Risk': 'risks', 'CustomerJourney': 'journeys',
                'ValueStream': 'value chains', 'Capability': 'capabilities', 'Event': 'messages', 'VerificationRun': 'checks',
                'NavigationMap': 'screens', 'AcceptanceScenario': 'test scenarios', 'NetworkZone': 'protected zones', 'Control': 'requirements',
                'QualityRequirement': 'requirements', 'Technology': 'technologies', 'Decision': 'decisions', 'RaciAssignment': 'responsibilities'}}
WORDS = {'fr': {'criterion': 'Critère', 'met': 'tenu', 'no': 'à fermer', 'human': ' · humain', 'na': 'sans objet', 'more': '… %d lignes de plus dans les livrables.',
                'revision': 'révision', 'source': 'Source : dossier d’architecture AIR', 'dossier': 'dossier', 'version': 'version', 'fingerprint': 'empreinte de contrôle'},
         'en': {'criterion': 'Criterion', 'met': 'met', 'no': 'to close', 'human': ' · human', 'na': 'not applicable', 'more': '… %d more rows in the deliverables.',
                'revision': 'revision', 'source': 'Source: AIR architecture dossier', 'dossier': 'dossier', 'version': 'version', 'fingerprint': 'check fingerprint'}}


def _block(b, lang):
    w = WORDS[lang];kind = b['type']
    if kind == 'summary': return '<div class="summary">' + ''.join('<div><b>%s</b>%s</div>' % (H(k), H(v)) for k, v in b['rows']) + '</div>'
    if kind == 'ask': return '<div class="ask">' + H(b['text']) + '</div>'
    if kind == 'takeaway': return '<div class="takeaway"><b>' + H(b['label']) + '</b>' + H(b['text']) + '</div>'
    if kind == 'note': return '<p class="note">' + H(b['text']) + '</p>'
    if kind == 'table':
        return '<table><thead><tr>' + ''.join('<th>' + H(str(h)) + '</th>' for h in b['head']) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join('<td>' + H(str(c)) + '</td>' for c in r) + '</tr>' for r in b['rows'][:b.get('max', 12)]) + '</tbody></table>' + (
            '<p class="note">' + w['more'] % (len(b['rows']) - b.get('max', 12)) + '</p>' if len(b['rows']) > b.get('max', 12) else '')
    if kind == 'columns': return '<div class="columns">' + ''.join('<div><h3>%s</h3><ul>%s</ul></div>' % (H(t), ''.join('<li>' + H(x) + '</li>' for x in items)) for t, items in b['items']) + '</div>'
    if kind == 'bullets': return '<ul>' + ''.join('<li>' + H(x) + '</li>' for x in b['items']) + '</ul>'
    if kind == 'numbered': return '<ol>' + ''.join('<li>' + H(x) + '</li>' for x in b['items']) + '</ol>'
    if kind == 'flows': return '<div class="flows">' + ''.join('<div class="flow"><b>%s</b>%s</div>' % (H(name), ''.join('<span>' + H(x) + '</span>' for x in steps)) for name, steps in b['items']) + '</div>'
    if kind == 'grid': return '<div class="grid">' + ''.join('<div><h3>%s</h3>%s</div>' % (H(ctx), ''.join('<span>' + H(x) + '</span>' for x in items)) for ctx, items in b['items']) + '</div>'
    if kind == 'svg': return b['svg']
    if kind == 'split': return '<div class="split">' + b['svg'] + '<ul>' + ''.join('<li>' + H(x) + '</li>' for x in b['items']) + '</ul></div>'
    if kind == 'mermaid': return '<pre class="mermaid">' + H(b['code']) + '</pre>'
    if kind == 'gate':
        codes = [c['code'] for c in b['gates'][0]['criteria']] if b['gates'] else []
        rows = '<tr><th>' + w['criterion'] + '</th>' + ''.join('<th>' + H(x['namespace'].split('.')[-1]) + '</th>' for x in b['gates']) + '</tr>'
        for code in codes:
            rows += '<tr><td>' + H(criterion(code, lang)) + '</td>'
            for x in b['gates']:
                c = next(c for c in x['criteria'] if c['code'] == code)
                rows += '<td class="%s">%s</td>' % ({'MET': 'met', 'NOT_MET': 'no', 'NOT_APPLICABLE': 'na'}[c['status']],
                                                     {'MET': w['met'], 'NOT_MET': w['no'] + (w['human'] if c.get('owner') == 'human' else ''), 'NOT_APPLICABLE': w['na']}[c['status']])
            rows += '</tr>'
        return '<table class="gate">' + rows + '</table>'
    if kind == 'cover': return '<p class="sub">' + H(b['subtitle']) + '</p><p class="meta">' + H(b['meta']) + '</p>'
    if kind == 'pins': return '<ul>' + ''.join('<li><b>%s</b> : %s %d <span class="note">(%s <code>%s</code>)</span></li>' % (
        H(b.get('labels', {}).get(p['id'], p['id'])), w['version'], p['revision'], w['fingerprint'], H(p['digest'][7:19] + '…')) for p in b['pins']) + '</ul>'
    return ''


def _french(value):
    if isinstance(value, str):
        for a, b in ((' ;', '\u202f;'), (' :', '\u00a0:'), (' ?', '\u202f?'), (' !', '\u202f!'), ('« ', '«\u00a0'), (' »', '\u00a0»'), (' %', '\u202f%')):
            value = value.replace(a, b)
        return value
    if isinstance(value, list): return [_french(v) for v in value]
    if isinstance(value, tuple): return tuple(_french(v) for v in value)
    if isinstance(value, dict): return {k: (v if k in ('svg', 'code', 'gates', 'pins') else _french(v)) for k, v in value.items()}
    return value


def render(decks, request):
    default = request.get('language', 'fr')
    out = ['<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' % default,
           '<title>' + H(request['title']) + '</title>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;600&display=swap">',
           '<style>' + CSS + '</style></head><body data-lang="%s">' % default,
           '<div class="bar" role="group" aria-label="Langue / Language"><button type="button" data-lang="fr">FR</button><button type="button" data-lang="en">EN</button></div>']
    for lang in LANGUAGES:
        out.append('<main class="deck" data-lang="%s" lang="%s"%s>' % (lang, lang, '' if lang == default else ' hidden'))
        for i, s in enumerate(decks[lang], 1):
            if lang == 'fr': s = {**s, 'title': _french(s['title']), 'blocks': _french(s['blocks']), 'notes': _french(s['notes'])}
            out.append('<section class="%s" id="%s-s%d"><div class="tracker">%s</div><h2>%s</h2><div class="body">%s</div>' % (
                'slide cover' if s['kind'] == 'cover' else 'slide', lang, i, H(s['section']), H(s['title']), ''.join(_block(b, lang) for b in s['blocks'])))
            if s['notes']: out.append('<div class="notes">' + H(s['notes']) + '</div>')
            plain = sorted({PLAIN[lang].get(x) for x in s['sources']} - {None})
            out.append('<div class="foot"><span>' + WORDS[lang]['source'] + ((' (' + H(', '.join(plain[:5])) + ')') if plain else '') + '</span><span>' + str(i) + '</span></div></section>')
        out.append('</main>')
    out += ['<div class="nav"></div>',
            '<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";mermaid.initialize({startOnLoad:true,theme:"neutral"});</script>',
            '<script>' + JS + '</script></body></html>']
    return '\n'.join(out)


def build(g, gates, request):
    f = figures(g, gates)
    decks = {lang: storyline(g, gates, request, lang, f) for lang in LANGUAGES}
    return decks[request.get('language', 'fr')], render(decks, request)


def compile_presentation(store, principal, policy, request):
    check_schema(request, REQUEST)
    from air.access import ScopedStore
    from air.deliverables import Graph
    from air.projections import snapshot
    from air.readiness import assess_readiness
    guarded = ScopedStore(store, principal, policy)
    exports = [snapshot(guarded, ref) for ref in request['baselines']]
    if sum(len(e['objects']) for e in exports) > 20000: raise InvalidModel('Presentation context exceeds 20,000 objects')
    gates = [assess_readiness(store, principal, policy, {'baseline': ref}) for ref in request['baselines']]
    slides, page = build(Graph(exports), gates, request)
    report = {'engine': ENGINE, 'title': request['title'], 'baselines': request['baselines'], 'slides': len(slides), 'languages': list(LANGUAGES),
              'language': request.get('language', 'fr'),
              'audience': request.get('audience', 'CONTRACT'),
              'outline': [{'n': i, 'key': s['key'], 'section': s['section'], 'title': s['title'], 'sources': s['sources']} for i, s in enumerate(slides, 1)],
              'registry_written': False, 'authorization_granted': False,
              'limits': ['Titles and figures are computed from the pinned baselines; assumptions stay assumptions',
                         'The deck is a support for a human presenter; it is neither an approval nor a signed commitment',
                         'Object names and statements appear in the language they were modelled in']}
    if request.get('content') == 'HTML': report['html'] = page
    report['page_digest'] = artifact_digest({'html': page})
    report['report_digest'] = artifact_digest(report)
    return report
