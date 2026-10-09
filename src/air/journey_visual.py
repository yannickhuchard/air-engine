"""A source-linked SVG journey, enhanced locally without changing its design data."""
from html import escape
from textwrap import wrap
from air.editorial import prose
from air.deliverables import mid

ENGINE = 'air.journey-visual/1'
STEP_WIDTH = 320
LEFT = 154
HEIGHT = 726


def h(v): return escape(prose(str(v)), quote=True)
def anchor(j): return mid(j['reference']['id'] + ':' + str(j['reference']['revision']))
def unique(items): return list({(x['reference']['id'], x['reference']['revision']): x for x in items}.values())


def text(value, x, y, cls='', width=32, lines=2):
    parts = wrap(prose(str(value)), width, break_long_words=True) or ['']
    if len(parts) > lines: parts = parts[:lines]; parts[-1] = parts[-1].rstrip(' .') + '…'
    return f'<text x="{x}" y="{y}" class="{cls}"><title>{h(value)}</title>' + ''.join(
        f'<tspan x="{x}" dy="{0 if i == 0 else 21}">{h(part)}</tspan>' for i, part in enumerate(parts)) + '</text>'


def icon(kind, x, y):
    paths = {
        'person': '<circle cx="12" cy="6" r="4"/><path d="M4 23v-4a8 8 0 0 1 16 0v4"/>',
        'contact': '<rect x="3" y="2" width="18" height="23" rx="3"/><path d="M9 20h6M7 7h10M7 12h10"/>',
        'system': '<path d="M2 8l10-6 10 6v12l-10 6-10-6zM2 8l10 6 10-6M12 14v12"/>',
        'place': '<path d="M12 26S3 15 3 10a9 9 0 0 1 18 0c0 5-9 16-9 16z"/><circle cx="12" cy="10" r="3"/>',
        'flag': '<path d="M5 26V2h14l-3 5 3 5H5"/>',
    }
    return f'<g class="jv-icon" transform="translate({x} {y})">{paths[kind]}</g>'


def face(score, x, y):
    mouth = 'M-7 5Q0 12 7 5' if score >= 4 else 'M-7 9Q0 2 7 9' if score <= 2 else 'M-7 7H7'
    return f'<g transform="translate({x} {y})"><circle class="jv-face" r="19"/><circle class="jv-eye" cx="-6" cy="-4" r="1.5"/><circle class="jv-eye" cx="6" cy="-4" r="1.5"/><path class="jv-mouth" d="{mouth}"/></g>'


def svg(j, profile=None, href_prefix=''):
    """Complete declarative SVG. Connectors show journey order, never technical calls."""
    ident = anchor(j); n = len(j['steps']); width = max(780, LEFT + STEP_WIDTH * n + 24)
    colors = (profile or {}).get('colors', {})
    palette = {k: colors.get(source, default) for k, source, default in [
        ('ink','text','#17333c'),('paper','surface','#ffffff'),('ground','background','#f4f7f8'),
        ('blue','link','#245b88'),('header','header','#172d4a'),('accent','accent','#a9e2cc')]}
    # Standalone SVG has its own palette; inline SVG inherits the dossier tokens.
    custom = '--jv-native-width:' + str(width) + 'px;'
    if profile:
        custom += ''.join('--' + k + ':' + h(v) + ';' for k, v in palette.items())
        custom += 'font-family:' + h('"' + profile.get('fonts', {}).get('body','Segoe UI') + '",system-ui,sans-serif') + ';'
    style = '''.jv-svg{font-family:inherit;color:var(--ink,#17333c)}.jv-svg text{fill:var(--ink,#17333c);font-size:15px}.jv-svg .jv-phase{font-size:12px;fill:var(--blue,#245b88)}.jv-svg .jv-title{font-size:18px;font-weight:650}.jv-svg .jv-small{font-size:12px;fill:var(--muted,#536b74)}.jv-svg .jv-number{fill:var(--paper,#fff);font-size:15px;font-weight:700}.jv-svg .jv-label{font-size:13px;fill:var(--muted,#536b74)}.jv-rail{fill:none;stroke:var(--blue,#245b88);stroke-width:4}.jv-connector{fill:none;stroke:var(--blue,#245b88);stroke-width:2}.jv-card{fill:var(--paper,#fff);stroke:var(--line,#d0dfe4);stroke-width:1.5}.jv-disc{fill:var(--blue,#245b88)}.jv-band{fill:var(--ground,#f4f7f8)}.jv-chip{fill:var(--paper,#fff);stroke:var(--line,#d0dfe4)}.jv-icon{fill:none;stroke:var(--blue,#245b88);stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}.jv-face{fill:var(--paper,#fff);stroke:var(--blue,#245b88);stroke-width:2}.jv-eye{fill:var(--ink,#17333c)}.jv-mouth{fill:none;stroke:var(--ink,#17333c);stroke-width:1.5}.jv-mood-guide{stroke:var(--line,#d0dfe4);stroke-width:1}.jv-mood-line{fill:none;stroke:var(--blue,#245b88);stroke-width:3}.jv-hypothesis{stroke-dasharray:6 5}.jv-unknown{fill:var(--paper,#fff);stroke:var(--line,#d0dfe4);stroke-dasharray:4 4}.jv-svg a{text-decoration:none}.jv-svg a:hover .jv-card,.jv-svg a:focus .jv-card,.jv-svg a.is-selected .jv-card{stroke:var(--blue,#245b88);stroke-width:3}.jv-svg a:focus{outline:none}.jv-svg a:focus .jv-disc{stroke:var(--ink,#17333c);stroke-width:3}.jv-svg a.is-muted{opacity:.16}.jv-svg a{transition:opacity .18s}.jv-svg .jv-flag{fill:#85500c;font-size:12px}@media(prefers-reduced-motion:reduce){.jv-svg a{transition:none}}'''
    out = f'<svg xmlns="http://www.w3.org/2000/svg" class="jv-svg" viewBox="0 0 {width} {HEIGHT}" width="{width}" height="{HEIGHT}" role="group" aria-labelledby="jv-title-{ident} jv-desc-{ident}" style="{custom}">'
    out += '<title id="jv-title-' + ident + '">' + h(j['name']) + '</title><desc id="jv-desc-' + ident + '">Étapes de gauche à droite, contacts, acteurs, systèmes et émotions. Les liens ouvrent les fiches. Les traits représentent l’ordre déclaré, sans appel technique inféré.</desc><style>' + style + '</style>'
    for label, y in [('Parcours',80),('Contacts',277),('Acteurs',386),('Systèmes',493),('Ressenti',615)]:
        out += text(label,20,y,'jv-label',16,1)
    for y, height in [(236,103),(347,105),(460,103),(578,136)]:
        out += f'<rect class="jv-band" x="{LEFT-14}" y="{y}" width="{width-LEFT}" height="{height}" rx="14"/>'
    for i in range(max(0,n-1)):
        x = LEFT + i*STEP_WIDTH + 284
        out += f'<path class="jv-rail" d="M{x} 139H{x+36}"/><path class="jv-connector" d="M{x+24} 133l6 6-6 6"/>'
    previous = None
    for i, s in enumerate(j['steps']):
        x = LEFT + i*STEP_WIDTH; cx = x+142; emotion=s.get('emotion',{}); status=emotion.get('status','UNKNOWN'); score=emotion.get('score')
        if status!='UNKNOWN' and score is not None:
            y=675-(score-1)*15
            if previous and previous[2]==status:
                out+=f'<path class="jv-mood-line jv-mood-part {"jv-hypothesis" if status=="HYPOTHESIS" else ""}" d="M{previous[0]+22} {previous[1]}C{previous[0]+120} {previous[1]} {cx-120} {y} {cx-22} {y}"/>'
            previous=(cx,y,status)
        else: previous=None
        out+=f'<a href="{h(href_prefix)}#jv-{ident}-step-{i}" data-jv-step="{i}" aria-label="Étape {i+1} : {h(s["name"])}" aria-current="{"step" if i==0 else "false"}" class="{"is-selected" if i==0 else ""}">'
        out+=f'<rect x="{x}" y="20" width="284" height="690" fill="transparent" pointer-events="all"/>'
        out+=text(s.get('phase','Phase à préciser'),x+6,35,'jv-phase',34,1)
        out+=f'<rect class="jv-card" x="{x}" y="65" width="284" height="146" rx="18"/><circle class="jv-disc" cx="{x+25}" cy="91" r="15"/>'
        out+=text(str(i+1).zfill(2),x+17,96,'jv-number',2,1)+text(s['name'],x+20,129,'jv-title',27,3)
        out+=text((str(len(s.get('pain_points',[])))+' irritant(s) déclaré(s)') if s.get('pain_points') else 'Irritants à préciser',x+20,195,'jv-flag',34,1)
        out+='<g class="jv-contact-part">'+f'<path class="jv-connector" d="M{cx} 211V248"/>'+icon('contact',x+14,254)
        out+=text(s['touchpoint'],x+50,266,'',28,2)+text(s['channel'],x+50,308,'jv-small',32,1)
        kinds={p.get('kind') for p in s['usage_points']}
        contexts=[label for kind,label in [('DIGITAL','Digital'),('PHYSICAL','Physique'),('GEOGRAPHIC','Géographique')] if kind in kinds]
        out+=text(' · '.join(contexts) or 'Usages à préciser',x+50,329,'jv-small',33,1)+'</g>'
        actors=unique([j['persona'],*s['participants']])
        out+='<g class="jv-actors-part">'+icon('person',x+14,368)
        out+=text(actors[0]['name'] if actors else 'Acteur à préciser',x+50,384,'',28,1)
        out+=text(actors[1]['name'] if len(actors)>1 else 'Persona principal',x+50,408,'jv-small',32,1)
        if len(actors)>2: out+=text('+'+str(len(actors)-2)+' autre(s) intervenant(s)',x+50,432,'jv-small',32,1)
        out+='</g>'; systems=unique(s.get('systems',[]))
        out+='<g class="jv-systems-part">'+icon('system',x+14,476)+text(systems[0]['name'] if systems else 'Système à affecter',x+50,493,'',27,2)
        linked=len(unique(s.get('linked_systems',[])))
        out+=text(('+'+str(len(systems)-1)+' système(s). ' if len(systems)>1 else '')+str(linked)+' bloc(s) associé(s)',x+50,542,'jv-small',33,1)+'</g><g class="jv-mood-part">'
        if status=='UNKNOWN' or score is None:
            out+=f'<rect class="jv-unknown" x="{x+24}" y="608" width="236" height="70" rx="12"/>'
            out+=text(emotion.get('label') or 'Émotion non renseignée',x+39,634,'',26,1)
            out+=text('Score non attribué' if status=='UNKNOWN' else ('Hypothèse sans score' if status=='HYPOTHESIS' else 'Observation sans score'),x+39,657,'jv-small',29,1)
        else:
            y=675-(score-1)*15
            out+=face(score,cx,y)+text(str(score)+'/5',cx+29,y-19,'',5,1)
            out+=text('Hypothèse' if status=='HYPOTHESIS' else 'Observation déclarée',x+14,590,'jv-small',32,1)
            out+=text(emotion.get('label',''),x+14,702,'jv-small',35,1)
        out+='</g></a>'
    return out+'</svg>'


def figure(j, compact=False):
    from air.journey_map import cell, ROWS
    ident=anchor(j);n=len(j['steps'])
    heading='Le voyage de '+j['persona']['name']
    out='<section class="journey-visual" id="visual-'+ident+'" data-journey-visual><header class="jv-heading"><div><h2>'+h(heading)+'</h2><p>'+h(j['goal'])+'</p></div><span class="jv-count">'+str(n)+' étapes</span></header>'
    out+='<div class="jv-toolbar" data-jv-toolbar hidden><div class="jv-controls"><button type="button" data-jv-action="previous" aria-label="Étape précédente">Précédente</button><button type="button" data-jv-action="next" aria-label="Étape suivante">Suivante</button><button type="button" data-jv-action="tour" aria-pressed="false">Visite guidée</button><button type="button" data-jv-action="fit">Vue d’ensemble</button><button type="button" data-jv-action="read">Taille de lecture</button><button type="button" data-jv-action="zoom" aria-label="Agrandir la carte">+</button><button type="button" data-jv-action="reduce" aria-label="Réduire la carte">−</button></div>'
    out+='<label>Afficher <select data-jv-layer><option value="all">Toutes les dimensions</option><option value="experience">Expérience et ressenti</option><option value="actors">Acteurs et contacts</option><option value="systems">Systèmes et blocs</option></select></label><label>Intervenant <select data-jv-actor><option value="">Tous les intervenants</option>'
    for p in unique([j['persona'],*[p for s in j['steps'] for p in s['participants']]]):
        ids=[str(i) for i,s in enumerate(j['steps']) if p in unique([j['persona'],*s['participants']])]
        out+='<option value="'+','.join(ids)+'">'+h(p['name'])+'</option>'
    out+='</select></label></div><p class="jv-instruction">Choisir une étape pour explorer ses détails. Les traits suivent l’ordre déclaré du parcours. Les systèmes associés ne constituent pas des appels techniques.</p>'
    if n:
        out+='<div class="jv-viewport" tabindex="0" role="region" aria-label="Carte du parcours, défilement horizontal et étapes au clavier">'+svg(j,href_prefix='journey-map-'+ident+'.html' if compact else '')+'</div><p class="jv-status" role="status" aria-live="polite">Étape 1 sur '+str(n)+' : '+h(j['steps'][0]['name'])+'</p>'
    else: out+='<p>Aucune étape déclarée.</p>'
    out+='<p class="jv-legend"><span class="jv-legend-path">Ordre des étapes</span><span class="jv-legend-hypothesis">Ressenti proposé</span><span>Ressenti observé : source requise</span><span>Score : 1 très négatif, 5 très positif</span><span>Inconnue : aucun score inventé</span></p>'
    if compact:
        out+='<p><a href="journey-map-'+ident+'.html">Explorer le diagramme interactif et ses fiches</a></p>'
    else:
        out+='<div class="jv-details"><h3>Explorer une étape</h3>'
        for i,s in enumerate(j['steps']):
            out+='<details class="jv-step-detail" id="jv-'+ident+'-step-'+str(i)+'"'+(' open' if i==0 else '')+'><summary>'+str(i+1)+'. '+h(s['name'])+'</summary><dl>'+''.join('<div><dt>'+h(label)+'</dt><dd>'+cell(j,s,field)+'</dd></div>' for field,label,_ in ROWS)+'</dl></details>'
        out+='</div><p class="jv-downloads"><a href="journey-map-'+ident+'.svg" download>Exporter le diagramme SVG</a><a href="journey-map-'+ident+'.json">Lire les données et sources exactes</a><a href="journey-'+ident+'.html#map-'+ident+'">Comparer toutes les dimensions dans la matrice</a></p>'
    return out+'</section>'


def page(j):
    ident=anchor(j)
    return '<nav class="breadcrumb"><a href="journeys.html">Parcours</a> / <a href="journey-'+ident+'.html">'+h(j['name'])+'</a></nav><h1>Customer Journey Map</h1><p class="intro">'+h(j['name'])+'</p>'+figure(j)+'<p>Conception déclarée, sans recherche utilisateur ou exécution réelle déduite de la visite guidée.</p>'
