"""Portable, source-bound video companions; rendering is an optional local step."""
import json
import hashlib
from pathlib import Path
from html import escape
from air.core import record
from air.foundation import check_schema
from air.projections import SNAPSHOT, snapshot
from air.expr import artifact_digest, bounded
from air.editorial import prose
from air.atelier import product, render_json
from air import branding, architecture_story, project_updates, journey_catalog, journey_visual

ENGINE = 'air.video-refresh/1'
REQUEST = record({'baseline': SNAPSHOT, 'branding': branding.INPUT,
    'journey_id': {'type': 'string', 'format': 'uri', 'maxLength': 512},
    'content': {'enum': ['FULL', 'DIGESTS']}}, ['baseline'])


def composition(title, sections, profile):
    h = lambda x: escape(prose(str(x)), quote=True)
    colors = profile['colors']
    clips = ''
    for i, (heading, text, visual) in enumerate(sections):
        clips += '<section id="scene-' + str(i) + '" class="clip" data-start="' + str(i*6) + '" data-duration="6" data-track-index="0"><div class="content"><p class="kicker">0' + str(i+1) + ' / ' + h(heading) + '</p>' + ('<h2>' + h(text) + '</h2><div class="visual">' + visual + '</div>' if visual else '<h1>' + h(text) + '</h1>') + '</div></section>'
    return '''<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>''' + h(title) + '''</title><style>
*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;font-family:Arial,sans-serif;background:''' + colors['header'] + ';color:' + colors['header_text'] + '''}#main{position:relative;width:1920px;height:1080px;overflow:hidden}.brand{position:absolute;top:48px;left:90px;font-size:30px;letter-spacing:3px}.edition{position:absolute;top:48px;right:90px;font-size:24px}.clip{position:absolute;inset:0;padding:150px 100px 100px;display:flex;align-items:center}.content{width:100%}.kicker{font-size:28px;letter-spacing:3px;color:''' + colors['accent'] + ''';margin:0 0 35px}h1{font-size:80px;line-height:1.15;max-width:1650px;margin:0}h2{font-size:54px;line-height:1.2;margin:0 0 30px;max-width:1600px}.visual{height:640px;background:''' + colors['surface'] + ';color:' + colors['text'] + ''';border-radius:22px;padding:28px;display:flex;align-items:center;justify-content:center}.visual img{width:100%;height:100%;object-fit:contain}.facts{display:grid;grid-template-columns:1fr 1fr;gap:25px;width:100%;font-size:32px;line-height:1.45}.facts p{padding:24px;border:1px solid #536b74;border-radius:14px;margin:0}.footer{position:absolute;bottom:35px;left:100px;font-size:23px}.rail{position:absolute;bottom:75px;left:100px;right:100px;height:3px;background:''' + colors['accent'] + '''}</style></head><body><div id="main" data-composition-id="main" data-no-timeline data-start="0" data-duration="24" data-width="1920" data-height="1080" data-fps="30"><div class="brand">''' + h(profile['name']) + '''</div><div class="edition">''' + h(title[:100]) + '''</div>''' + clips + '''<div class="rail"></div><div class="footer">Conception sourcée · 24 secondes · aucune exécution métier</div></div><script>
document.querySelectorAll('.content').forEach((el,i)=>{const a=el.animate([{opacity:0,transform:'translateY(22px)'},{opacity:1,transform:'translateY(0)'}],{duration:550,delay:i*6000,fill:'both',iterations:1,easing:'ease-out'});a.pause()});
</script></body></html>'''


def prepare(store, principal, policy, request):
    from air.access import ScopedStore
    from air.readiness import assess_readiness
    from air.deliverables import Graph
    check_schema(request, REQUEST)
    e = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    gate = assess_readiness(store, principal, policy, {'baseline': request['baseline']})
    story = architecture_story.project(e, gate)
    updates = project_updates.project(e, gate)
    journeys = journey_catalog.project(Graph([e]))
    selected = next((j for j in journeys['journeys'] if j['reference']['id'] == request.get('journey_id')), None) if request.get('journey_id') else next(iter(journeys['journeys']), None)
    if request.get('journey_id') and not selected: raise ValueError('Journey absent from this authorized exact baseline')
    brand = branding.normalize(request.get('branding', {}));profile = brand['profile']
    source = {'engine': ENGINE, 'baseline': request['baseline'], 'story': story, 'updates': updates,
        'journey': selected, 'branding_digest': brand['profile_digest'], 'render_status': 'NOT_RENDERED',
        'business_execution_performed': False, 'research_validated': False}
    source['recipe_digest'] = 'sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source['source_digest'] = artifact_digest(source)
    folder = 'videos/' + source['source_digest'][7:23]
    files = []
    def add(name, media, content): files.append(product(folder+'/'+name, media, content, 'GENERATED', max_size=2*1024*1024))
    h = lambda x: escape(prose(str(x)), quote=True)
    def facts(rows): return '<div class="facts">' + ''.join('<p>'+h(row)+'</p>' for row in rows) + '</div>'
    intro = next((f['value'] for p in story['phases'] if p['id']=='purpose' for r in p['entries'] for f in r['fields'] if f['selector']=='/body/desired_change'), story['name'])
    names = [r['name'] for r in updates['decisions']['items'][:4]]
    open_names = [r['name'] for r in updates['open_questions']['items'][:4]]
    met = sum(c['status']=='MET' for c in gate['criteria'])
    specs = [('overview', 'Du besoin aux décisions', [
        ('Le besoin', prose(str(intro))[:210], ''),
        ('Le dossier', 'Des plans reliés, pour préparer la réalisation.', facts([str(len(e['objects']))+' objets exacts', str(len(journeys['journeys']))+' parcours déclarés', 'Révision '+str(request['baseline']['revision']), 'Préparation '+str(met)+'/'+str(len(gate['criteria']))])),
        ('Les choix', 'Choix déclarés et conséquences à lire.', facts(names or ['Aucun choix déclaré'])),
        ('La suite', 'Questions ouvertes, avant la réalisation.', facts(open_names or ['Lire les contrôles de préparation']))])]
    if selected:
        specs.append(('journey', 'Le parcours client', [
            ('Le persona', selected['name'][:150], ''),
            ('La carte réelle AIR', 'Touchpoints, acteurs, systèmes et ressenti.', '<img src="journey.svg" alt="Carte exacte du parcours AIR">'),
            ('Les étapes', 'Le parcours suit l’ordre déclaré.', facts([s['name'] for s in selected['steps'][:4]])),
            ('La traçabilité', 'Ouvrir le dossier pour les détails et les sources.', facts(['Émotions inconnues conservées', 'Hypothèses distinctes des observations', str(len(selected['steps']))+' étapes dans la carte complète', 'Aucune mesure terrain déduite']))]))
    add('source.json', 'application/json', render_json(source))
    for name, title, sections in specs:
        add(name+'/index.html', 'text/html', composition(title, sections, profile))
        add(name+'/hyperframes.json', 'application/json', render_json({'authoringSkill':'brag','runtime':'waapi'}))
        if name=='journey': add(name+'/journey.svg', 'image/svg+xml', journey_visual.svg(selected, profile))
    add('README.md', 'text/markdown', '# Vidéos du projet d’architecture\n\nDeux récits courts BRAG, depuis les mêmes sources exactes.\n\nBaseline r'+str(request['baseline']['revision'])+' ; source `'+source['source_digest']+'`.\nLes extraits sont bornés ; source.json et le dossier conservent le contenu complet.\n\n`air videos-refresh demande.json --workspace <projet> --apply --render`\n\nLe rendu optionnel utilise Hyperframes, Chromium et FFmpeg sur le poste.\nLe MCP prépare les compositions et leurs empreintes ; il ne publie pas de vidéo.\nAucune voix, musique tierce, exécution métier ou observation utilisateur ajoutée.\n')
    result = {'engine':ENGINE,'baseline':request['baseline'],'source_digest':source['source_digest'],
        'directory':folder,'videos':[{'name':name,'title':title,'composition':folder+'/'+name,'duration_seconds':24} for name,title,_ in specs],
        'render_status':'NOT_RENDERED','registry_written':False,'files':files}
    if request.get('content', 'DIGESTS')=='DIGESTS': result['files']=[{k:v for k,v in f.items() if k!='content'} for f in files]
    bounded(result)
    return result
