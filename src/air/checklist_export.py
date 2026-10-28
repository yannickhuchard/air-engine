"""Dependency-free CSV/OOXML tracking exports of an exact architecture baseline."""
import base64
import csv
import io
import json
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from xml.sax.saxutils import escape
from air.core import record, digest
from air.foundation import check_schema, exact, check_budget
from air.access import ScopedStore
from air.projections import SNAPSHOT, snapshot
from air import delivery_assurance as assurance
from air.editorial import prose

REQUEST = record({'baseline': SNAPSHOT, 'as_of': assurance.DAY, 'format': {'enum': ['CSV', 'XLSX']} })
HEADERS = ['Section', 'ID', 'Revision', 'Nom', 'Statut', 'Détail', 'Empreinte']


def rows(exported, coverage, gates, dashboard):
    result = []
    for r in gates['gates']:
        result.append(['Gate', r['gate']['id'], r['gate']['revision'], r['name'], r['result'],
            ', '.join(x['code'] for x in r['blockers']), r['gate']['digest']])
    for r in coverage['requirements']:
        result.append(['Traçabilité', r['requirement']['id'], r['requirement']['revision'], r['name'], r['status'],
            ', '.join(g['missing_layer'] + ': ' + g['reason'] for g in r['gaps']), r['requirement']['digest']])
    for r in dashboard['tasks']:
        result.append(['Livraison', r['task']['id'], r['task']['revision'], r['name'], r['status'],
            json.dumps({k: r[k] for k in ('team', 'members', 'due', 'late', 'blockers', 'blocker_reason', 'unresolved_prerequisites')}, ensure_ascii=False), r['task']['digest']])
    for o in sorted(exported['objects'], key=lambda o: (o['meta']['type'], o['meta']['id'], o['meta']['revision'])):
        participation = o['meta']['type'] == 'air.StakeholderParticipation'
        result.append([o['meta']['type'], o['meta']['id'], o['meta']['revision'], o['meta']['name'],
            o['body']['state'] if participation else o['body'].get('status', o['body'].get('result', 'DECLARED_NOT_QUALIFIED')),
            json.dumps({k: o['body'][k] for k in ('reason', 'responsibilities', 'staffing_action', 'engagement_plan', 'coordination_owner')}, ensure_ascii=False) if participation else o['meta'].get('description', ''), digest(o)])
    b = exported['baseline']
    result.insert(0, ['Source', b['meta']['id'], b['meta']['revision'], b['meta']['name'], 'PINNED_BASELINE',
        'Statuts déclarés et contrôles de conception ; aucune réception métier implicite. Date de suivi : ' + dashboard['as_of'], exported['digest']])
    return result


def safe_csv(value):
    text = prose(str(value))
    # Quote alone does not prevent Excel formula execution, including leading controls.
    return "'" + text if text.lstrip('\ufeff \t\r\n').startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text


def csv_bytes(data):
    s = io.StringIO(newline=''); writer = csv.writer(s, lineterminator='\r\n')
    writer.writerow(HEADERS)
    writer.writerows([[safe_csv(c) for c in row] for row in data])
    return ('\ufeff' + s.getvalue()).encode('utf-8')


def xlsx_bytes(data):
    """Fixed timestamps, inline strings, no macros, formulas or external relationships."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    xml = lambda value: escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', prose(str(value))))
    all_rows = [HEADERS, *data]; cells = []
    for i, row in enumerate(all_rows, 1):
        cells.append('<row r="' + str(i) + '">' + ''.join('<c r="' + chr(65+j) + str(i) + '" t="inlineStr" s="' + ('1' if i == 1 else '0') + '"><is><t xml:space="preserve">' + xml(c) + '</t></is></c>' for j, c in enumerate(row)) + '</row>')
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<workbook xmlns="' + ns + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Suivi AIR" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': '<styleSheet xmlns="' + ns + '"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF173F4F"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"/></cellXfs></styleSheet>',
        'xl/worksheets/sheet1.xml': '<worksheet xmlns="' + ns + '"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>' + ''.join('<col min="' + str(i) + '" max="' + str(i) + '" width="' + str(w) + '" customWidth="1"/>' for i,w in enumerate([22,55,12,42,30,80,72],1)) + '</cols><sheetData>' + ''.join(cells) + '</sheetData><autoFilter ref="A1:G' + str(len(all_rows)) + '"/></worksheet>',
    }
    output = io.BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as z:
        for name, content in sorted(files.items()):
            info = ZipInfo(name, (2000, 1, 1, 0, 0, 0)); info.compress_type = ZIP_DEFLATED
            z.writestr(info, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + content)
    return output.getvalue()


def compile_export(store, principal, policy, request):
    check_schema(request, REQUEST)
    e = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    trace = assurance.coverage_project(e)
    gates = assurance.assess_gates(store, principal, policy, {'baseline': request['baseline']})
    work = assurance.dashboard_project([e], {'baselines': [request['baseline']], 'as_of': request['as_of']})
    data = rows(e, trace, gates, work)
    raw = csv_bytes(data) if request['format'] == 'CSV' else xlsx_bytes(data)
    import hashlib
    result = {'baseline': request['baseline'], 'as_of': request['as_of'], 'format': request['format'],
        'filename': 'checklist.' + request['format'].lower(), 'content_base64': base64.b64encode(raw).decode('ascii'),
        'content_digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'rows': len(data),
        'registry_written': False, 'readiness_inferred': False}
    check_budget(result)
    return result
