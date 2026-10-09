"""Optional BRAG authoring from exact AIR stories; no runtime/render dependency.

Inputs are an authorized generated site and local licensed assets. This creates
plans and compositions, not MP4s or business evidence. Render separately after
Hyperframes checks. Existing output is refused to preserve manual authoring.
"""
import argparse
from array import array
from html import escape
from air.editorial import prose
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import wave
from air.architecture_story import verify
from air.branding import normalize

BRAG = 'https://github.com/latent-spaces/brag/tree/cb89b9f44309b0bf4e3cb89e685fadf80c7999ed/skills/brag'


def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, text): path.write_text(text, encoding='utf-8')
def site_file(site, relative):
    if not isinstance(relative, str) or '\\' in relative or ':' in relative or '..' in Path(relative).parts or Path(relative).is_absolute():
        raise ValueError('Source path must remain inside the authorized site')
    target=(site/relative).resolve()
    if not target.is_relative_to(site.resolve()) or not target.is_file():
        raise ValueError('Source file absent or outside the authorized site')
    return target
def field(entry, name):
    return next((f['value'] for f in entry['fields'] if f['selector'] == '/body/' + name), None)


def music(path):
    """Original deterministic four-chord bed + restrained transition accents.

    No sampled recording, voice, licensed tune or third-party music. The source
    code and generated music are distributed under AIR's Apache-2.0 license.
    """
    rate = 44100; samples = array('h'); chords = [(261.63,329.63,392),(220,261.63,329.63),(293.66,349.23,440),(196,246.94,293.66)]
    starts = [0,5,12,19]; ends = [5,12,19,24]
    for i in range(24*rate):
        t = i/rate; phase = sum(t >= x for x in starts[1:]); a=t-starts[phase]; b=ends[phase]-t
        envelope = min(1,a/.7,b/.8); modulation = .83+.17*math.sin(2*math.pi*.25*t)
        value = sum(math.sin(2*math.pi*f*t)+.12*math.sin(2*math.pi*2*f*t) for f in chords[phase]) * .055*envelope*modulation
        if 0 <= a < .22 and phase:
            value += .12*math.sin(2*math.pi*520*a)*math.exp(-30*a)*min(1,a/.008)
        samples.append(int(max(-1,min(1,value))*32767))
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(samples.tobytes())


def prepare(site, output, assets, captures, baselines=(), fictional=False, audio_data=None):
    manifest=json.loads((site/'site-manifest.json').read_text(encoding='utf-8'))
    available={d['baseline']['id']+'@'+str(d['baseline']['revision']) for d in manifest['dossiers']}
    if set(baselines)-available: raise ValueError('Requested exact baseline absent from this authorized site')
    chosen=[d for d in manifest['dossiers'] if not baselines or d['baseline']['id']+'@'+str(d['baseline']['revision']) in baselines]
    if output.exists(): raise ValueError('Choose a new output directory; existing authoring is preserved')
    stories=[verify(json.loads(site_file(site,d['story_data']).read_text(encoding='utf-8'))) for d in chosen]
    if any(m['baseline'] != d['baseline'] or m['story_digest'] != d['story_digest'] for m,d in zip(stories,chosen)):
        raise ValueError('Story does not match the exact dossier declared by the site manifest')
    for name in ['gsap.min.js','Manrope.ttf','Manrope-OFL.txt']:
        if not (assets/name).is_file(): raise ValueError('Missing local asset: '+name)
    for i in range(len(chosen)):
        if not (captures/('D%02d-decision.png'%(i+1))).is_file(): raise ValueError('Missing real AIR decision capture')
    output.mkdir(parents=True)
    music(output/'air-story-music.wav')
    plans=[]
    for i,(d,model) in enumerate(zip(chosen,stories),1):
        code='D%02d'%i; folder=output/code; comp=folder/'composition'; local=comp/'assets';local.mkdir(parents=True)
        brand_source = d.get('branding', {}).get('path')
        if brand_source:
            imported_brand = json.loads(site_file(site, brand_source).read_text(encoding='utf-8'))
            brand = normalize(imported_brand['source'])
            if imported_brand['profile_digest'] != brand['profile_digest'] or d['branding']['profile_digest'] != brand['profile_digest']:
                raise ValueError('Branding does not match its source or dossier manifest')
        else: brand = normalize({})
        for name in ['gsap.min.js','Manrope.ttf','Manrope-OFL.txt']: shutil.copy2(assets/name,local/name)
        shutil.copy2(output/'air-story-music.wav',local/'music.wav')
        shutil.copy2(captures/(code+'-decision.png'),local/'decision.png')
        phases={p['id']:p for p in model['phases']}
        intent=next((e for e in phases['purpose']['entries'] if e['source']['type']=='air.Intent'),None)
        decision=next((e for e in phases['choices']['entries'] if e['source']['type']=='air.Decision'),None)
        path=next(iter(model['potential_paths']),None)
        purpose=field(intent,'desired_change') if intent else 'Besoin non déclaré dans cette baseline.'
        selection=field(decision,'selection') if decision else 'Décision non déclarée.'
        consequence=(field(decision,'consequences') or ['Conséquence non déclarée.'])[0] if decision else 'Conséquence non déclarée.'
        steps=path['steps'][:3] if path else []
        omitted=max(0,len(path['steps'])-3) if path else 0
        workflow=path['source']['name'] if path else 'Aucun parcours ordonné déclaré'
        title=d['name'].removesuffix(' - design A')
        plan=f'''# BRAG - AIR / {code}

Skill : {BRAG}
Source : `{d['story_data']}` ; baseline `{model['baseline']['id']}` r{model['baseline']['revision']}.
Story digest : `{model['story_digest']}`.

## Inspection
Produit : AIR, atelier local de conception, vérification et simulation des plans.
Public : architectes, sponsors et équipes de réalisation.
Problème du dossier : {purpose}
Parcours montré : {workflow}.
Résultat voulu : comprendre les choix avant implémentation, sans exécution métier.
Moment réel : carte « {decision['source']['name'] if decision else 'source du dossier'} » capturée dans le site AIR.
Différence : modèle exact, ontologie et critères de préparation gardés visibles.
Preuves disponibles : objets déclarés, empreintes, parcours potentiels, calcul de préparation.
Identité : {brand['profile']['name']}, {brand['profile']['colors']['header']} / {brand['profile']['colors']['accent']}, familles locales {brand['profile']['fonts']['body']} / {brand['profile']['fonts']['display']}, repli Manrope licencié.

## Angle et contrat créatif
Rendre le design explicable. Ton polished ; 1920×1080, 24 secondes, sans voix.
Hook : Du besoin au plan. Outro : Comprendre. Décider. Puis construire.
Musique originale synthétisée localement, source Apache-2.0 ; trois accents doux.
Pas de musique BRAG embarquée dont les conditions de redistribution restent à vérifier.
Révélations naturelles pour laisser lire ; pas de verrouillage artificiel sur un beat.
Réactivité : intensité très légère du filet de marque, pilotée par les données audio extraites.

| Scène | Temps | Faits et visuel |
|---|---|---|
| Hook | 0–5 s | Intention exacte : {purpose} |
| Reveal | 5–12 s | {workflow} ; {len(steps)} étapes visibles, {omitted} omises |
| Highlights | 12–19 s | {selection} ; {consequence} ; vraie carte AIR |
| Outro | 19–24 s | Préparation calculée : {model['readiness']['result']} ; aucune exécution métier |

Lecture courte : elle omet les chapitres Données et Évolution et les autres branches.
Le site et story.json restent la source complète. Les conditions ne sont pas évaluées.
'''
        write(folder/'brag-plan.md',plan)
        write(folder/'composition-brief.md',plan+'\n## Hyperframes\nComposition locale, GSAP seek-safe, assets locaux, check avant rendu. Montrer les poses 0/3/8/15/22/24 et vérifier la recherche arrière. Aucun runtime métier exécuté.\n')
        write(folder/'share-copy.txt',f'AIR - {title}. Du besoin aux mécanismes et aux décisions : un design sourcé pour préparer la réalisation. Le film ne constitue pas une exécution ou une réception métier.\nDistribution publique : https://github.com/yannickhuchard/air-engine\nLes capacités 0.35 restent distinctes de la distribution rc9.\n')
        write(folder/'story.json',json.dumps(model,ensure_ascii=False,indent=2)+'\n')
        write(comp/'hyperframes.json',json.dumps({'$schema':'https://hyperframes.heygen.com/schema/hyperframes.json','authoringSkill':'brag','paths':{'assets':'assets','blocks':'compositions','components':'compositions/components'}}))
        h=lambda value: escape(prose(value))
        cards=''.join('<article class="step"><span>0'+str(j+1)+'</span><h3>'+h(s['name'])+'</h3></article>' for j,s in enumerate(steps))
        html='''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=1920,height=1080"><title>AIR architecture story</title><script src="assets/gsap.min.js"></script><style>
@font-face{font-family:Manrope;src:url('assets/Manrope.ttf') format('truetype');font-weight:200 800}
*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#153f4a;color:#f1f6f7;font-family:Manrope,sans-serif}
#main{position:relative;width:100%;height:100%;overflow:hidden}.clip{position:absolute;inset:0;padding:150px 100px 100px;display:flex;align-items:center}.content{width:100%}
.brand{position:absolute;top:50px;left:100px;font-size:42px;font-weight:800;letter-spacing:8px;z-index:5}.project{position:absolute;top:58px;right:100px;font-size:25px;max-width:1300px;text-align:right;z-index:5}
.bar{position:absolute;left:100px;right:100px;bottom:56px;height:5px;background:#6ed5c2;z-index:5}.kicker{color:#6ed5c2;font-size:26px;text-transform:uppercase;letter-spacing:4px;margin:0 0 28px}
h1{font-size:100px;line-height:1.05;letter-spacing:-4px;margin:0 0 40px}h2{font-size:68px;line-height:1.15;letter-spacing:-2px;margin:0 0 32px;max-width:1600px}.lead{font-size:52px;line-height:1.4;max-width:1500px;margin:0}.note{font-size:28px;line-height:1.45;color:#bfd8de;margin-top:34px}
.steps{display:flex;gap:30px;margin-top:50px}.step{flex:1;border:1px solid #6c9ba6;border-top:5px solid #6ed5c2;border-radius:14px;padding:40px;min-height:270px;background:#204f5b}.step span{font-size:24px;color:#6ed5c2}.step h3{font-size:40px;line-height:1.4;margin:25px 0}
.split{display:grid;grid-template-columns:1fr 580px;gap:70px;align-items:center}.split h2{font-size:68px}.split .lead{font-size:43px}.real-ui{width:580px;height:740px;object-fit:contain;object-position:center;border-radius:10px;background:#f1f6f7;padding:20px}.gate{display:inline-block;padding:16px 28px;border:1px solid #edc28e;color:#edc28e;border-radius:8px;font-size:32px}.source{position:absolute;bottom:16px;left:100px;font-size:20px;color:#bfd8de}
</style></head><body><div id="main" data-composition-id="main" data-start="0" data-duration="24" data-width="1920" data-height="1080" data-fps="30"><div class="brand">AIR</div><div class="project">PROJECT_TITLE</div><div class="bar"></div>
<section id="scene-0" class="clip" data-start="0" data-duration="5" data-track-index="0"><div class="content" id="hook"><p class="kicker">01 / Le besoin</p><h1>Du besoin au plan.</h1><p class="lead">PURPOSE</p><p class="note">SOURCE_LABEL</p></div></section>
<section id="scene-5" class="clip" data-start="5" data-duration="7" data-track-index="0"><div class="content" id="reveal"><p class="kicker">02 / Le mécanisme déclaré</p><h2>WORKFLOW</h2><div class="steps">STEPS</div><p class="note">Branche potentielle · gardes non évaluées · OMITTED étape(s) omise(s) dans ce plan court</p></div></section>
<section id="scene-12" class="clip" data-start="12" data-duration="7" data-track-index="0"><div class="content split" id="choices"><div><p class="kicker">03 / Le choix et sa conséquence</p><h2>SELECTION</h2><p class="lead">CONSEQUENCE</p><p class="note">À droite : la vraie carte de décision du site AIR.</p></div><img class="real-ui" src="assets/decision.png" alt="Carte de décision du dossier AIR"></div></section>
<section id="scene-19" class="clip" data-start="19" data-duration="5" data-track-index="0"><div class="content" id="outro"><p class="kicker">04 / Préparer la réalisation</p><h1>Comprendre. Décider.<br>Puis construire.</h1><span class="gate">Préparation : READINESS</span><p class="note">Aucune exécution métier. Lire les blocages dans le dossier complet.</p></div></section>
<div class="source">CODE · BASELINE · STORY_DIGEST</div><audio id="music" src="assets/music.wav" data-start="0" data-duration="24" data-track-index="1" data-volume="0.8"></audio></div>
<script>const tl=gsap.timeline({paused:true});
for(const [selector,time] of [['#hook',0],['#reveal',5],['#choices',12],['#outro',19]]){
 tl.fromTo(selector,{opacity:0,y:26},{opacity:1,y:0,duration:.6,ease:'power2.out',immediateRender:false},time);
}
for(let i=0;i<document.querySelectorAll('.step').length;i++)tl.fromTo(document.querySelectorAll('.step')[i],{opacity:0,y:22},{opacity:1,y:0,duration:.5,ease:'power2.out',immediateRender:false},5.35+i*.6);
// Natural timing chosen for text readability; no invented musical cue metadata.
// AUDIO_REACTIVE
tl.to({}, {duration:.01},23.99);window.__timelines=window.__timelines||{};window.__timelines.main=tl;
</script></body></html>'''
        variables={'SOURCE_LABEL':'Démonstration fictive · sources exactes' if fictional else 'Baseline exacte · sources déclarées','PROJECT_TITLE':title,'PURPOSE':purpose,'WORKFLOW':workflow,'STEPS':cards,'OMITTED':str(omitted),'SELECTION':selection,'CONSEQUENCE':consequence,'READINESS':model['readiness']['result'],'CODE':code,'BASELINE':'r'+str(model['baseline']['revision']),'STORY_DIGEST':model['story_digest'][7:19]}
        # One pass: model text containing another placeholder is never rewritten.
        html=re.sub(r'\b(?:'+ '|'.join(variables) +r')\b',lambda m: variables[m[0]] if m[0]=='STEPS' else h(variables[m[0]]),html)
        if audio_data:
            audio=json.loads(audio_data.read_text(encoding='utf-8'))
            if audio['totalFrames'] != 720 or audio['fps'] != 30: raise ValueError('Audio analysis must cover 24 seconds at 30fps')
            reactive='const audio='+json.dumps(audio,separators=(',',':'))+'; for(let f=0;f<audio.totalFrames;f++){tl.fromTo(".bar",{opacity:.65+.2*audio.frames[f].bands[0]},{opacity:.65+.2*audio.frames[f].bands[0],duration:1/30,immediateRender:false},f/30);}'
            html=html.replace('// AUDIO_REACTIVE',reactive)
        else:
            write(folder/'composition-brief.md',plan+'\nRéactivité audio non intégrée : fournir --audio-data (analyse Hyperframes de la musique originale) avant qualification.\n')
        # Apply only the presentation envelope. Story objects/digests stay exact.
        profile = brand['profile']; colors = profile['colors']
        write(local/'logo.svg', profile['logo_svg'])
        video_fonts = {}; font_css = ''; font_assets = []
        for role in ('body', 'display'):
            supplied = 'Brand' + role.title() + '.ttf'; license_name = 'Brand' + role.title() + '-LICENSE.txt'
            if (assets/supplied).is_file():
                if not (assets/license_name).is_file(): raise ValueError('Custom video font needs its local license: ' + license_name)
                shutil.copy2(assets/supplied, local/supplied); shutil.copy2(assets/license_name, local/license_name)
                chosen_font = supplied; font_assets.extend([supplied, license_name])
            else: chosen_font = 'Manrope.ttf'
            video_fonts[role] = {'requested_family': profile['fonts'][role], 'asset': chosen_font, 'fallback': chosen_font == 'Manrope.ttf'}
            font_css += '@font-face{font-family:AIRBrand' + role.title() + ';src:url("assets/' + chosen_font + '") format("truetype")}\n'
        css_head, remainder = html.split('</style>', 1)
        for old, new in {'#153f4a': colors['header'], '#6ed5c2': colors['accent'], '#204f5b': colors['header'], '#bfd8de': colors['header_text']}.items():
            css_head = css_head.replace(old, new)
        html = css_head + '</style>' + remainder
        html = html.replace('<div class="brand">AIR</div>', '<div class="brand"><img src="assets/logo.svg" alt="" width="60" height="60"> ' + h(profile['name']) + '</div>')
        style = font_css + 'body{color:' + colors['header_text'] + ';font-family:AIRBrandBody,Manrope,sans-serif}h1,h2,h3,.brand{font-family:AIRBrandDisplay,Manrope,sans-serif}.brand{display:flex;align-items:center;gap:20px}.step span{color:' + colors['header_text'] + '}'
        html = html.replace('</style>', style + '\n</style>', 1)
        write(comp/'index.html', html)
        receipt={'baseline':model['baseline'],'story_digest':model['story_digest'],'source_story':d['story_data'],
            'source_story_file_digest':sha(site_file(site,d['story_data'])),'real_ui_digest':sha(local/'decision.png'),
            'brag_skill':BRAG,'hyperframes_version':'0.8.114','duration_seconds':24,'business_execution_performed':False,
            'render_status':'NOT_RENDERED','selected_path_source':path['source'] if path else None,
            'omitted_steps':omitted,'omitted_other_paths':max(0,len(model['potential_paths'])-1),
            'branding_digest': brand['profile_digest'], 'source_branding': brand_source,
            'video_fonts': video_fonts,
            'source_branding_file_digest': sha(site_file(site, brand_source)) if brand_source else None,
            'assets':{name:sha(local/name) for name in ['gsap.min.js','Manrope.ttf','music.wav','decision.png','logo.svg', *font_assets]}}
        write(folder/'source-receipt.json',json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        write(folder/'CREDITS.md','BRAG : latent-spaces, workflow MIT (skill non redistribué).\nHyperframes : HeyGen, outil de rendu.\nGSAP 3.14.2 : GreenSock, https://gsap.com/standard-license (avis dans assets/gsap.min.js).\nManrope : SIL Open Font License 1.1, voir assets/Manrope-OFL.txt.\nMusique et accents : synthèse originale via le script AIR, Apache-2.0.\nLes droits des sources AIR et captures restent ceux du projet ; vérifier avant diffusion.\n')
        plans.append({'dossier':code,'name':title,'composition':str(comp),'story_digest':model['story_digest']})
    write(output/'preparation.json',json.dumps({'status':'PREPARED_NOT_RENDERED','trailers':plans},ensure_ascii=False,indent=2)+'\n')
    return plans


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--assets',required=True,type=Path,help='Local gsap.min.js, Manrope.ttf, Manrope-OFL.txt')
    p.add_argument('--captures',required=True,type=Path,help='Real authorized AIR D01-decision.png, D02…, one per selected dossier')
    p.add_argument('--baseline',action='append',default=[],help='Exact id@revision, repeatable; default: all dossiers')
    p.add_argument('--fictional',action='store_true',help='Label user-designated fictional examples')
    p.add_argument('--audio-data',type=Path,help='Hyperframes analysis of the same original 24-second music bed')
    a=p.parse_args();print(json.dumps({'prepared':len(prepare(a.site.resolve(),a.output.resolve(),a.assets.resolve(),a.captures.resolve(),a.baseline,a.fictional,a.audio_data))}))
