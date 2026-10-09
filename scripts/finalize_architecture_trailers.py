"""Verify local BRAG MP4s, bake their poster frame and build a companion viewer.

Optional FFmpeg authoring tool. Preserves the raw MP4 and refuses to finalize
twice. Does not upload, alter the generated AIR pack or assert business readiness.
"""
import argparse
from html import escape as H
import json
import os
import re
from pathlib import Path
import subprocess
from urllib.parse import quote
from air.architecture_story import verify, video_freshness
from prepare_architecture_trailers import sha, write, site_file


def run(args):
    return subprocess.run(args,check=True,capture_output=True).stdout


def inspect(path):
    result=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    video=next(s for s in result['streams'] if s['codec_type']=='video')
    audio=next(s for s in result['streams'] if s['codec_type']=='audio')
    assert video['width']==1920 and video['height']==1080 and video['r_frame_rate']=='30/1'
    assert int(video['nb_frames'])==720 and abs(float(result['format']['duration'])-24)<.1
    return {'width':video['width'],'height':video['height'],'fps':video['r_frame_rate'],'frames':int(video['nb_frames']),
            'duration_seconds':float(result['format']['duration']),'video_codec':video['codec_name'],
            'audio_codec':audio['codec_name'],'audio_duration_seconds':float(audio['duration'])}


def audio_hash(path):
    return run(['ffmpeg','-v','error','-i',str(path),'-map','0:a','-c','copy','-f','hash','-hash','sha256','-']).decode().strip()


def finalize(output, site):
    plans=json.loads((output/'preparation.json').read_text(encoding='utf-8'))['trailers'];cards=[];receipts=[]
    for plan in plans:
        if not re.fullmatch(r'D[0-9]{2,}',plan['dossier']): raise ValueError('Invalid companion dossier directory')
        folder=output/plan['dossier'];receipt=json.loads((folder/'source-receipt.json').read_text(encoding='utf-8'))
        source=site_file(site,receipt['source_story']); model=verify(json.loads(source.read_text(encoding='utf-8')))
        assert video_freshness(model,receipt)=='CURRENT' and sha(source)==receipt['source_story_file_digest']
        if receipt.get('source_branding'):
            from air.branding import normalize
            brand_path = site_file(site, receipt['source_branding'])
            brand = normalize(json.loads(brand_path.read_text(encoding='utf-8'))['source'])
            assert video_freshness(model, receipt, brand['profile_digest']) == 'CURRENT'
            assert sha(brand_path) == receipt['source_branding_file_digest']
        raw=folder/'brag.raw.mp4';video=folder/'brag.mp4';poster=folder/'brag.jpg';baked=folder/'brag.poster.mp4'
        if raw.exists() or (folder/'video-receipt.json').exists(): raise ValueError('Already finalized; preserve this reviewed output')
        check=json.loads((folder/'check.json').read_text(encoding='utf-8-sig'))
        assert check['ok'] and not check['browserSkipped']
        for part in ['lint','runtime','layout','contrast']: assert check[part]['errorCount']==0
        spec=inspect(video);original_audio=audio_hash(video)
        run(['ffmpeg','-v','error','-y','-ss','8','-i',str(video),'-frames:v','1','-q:v','2',str(poster)])
        run(['ffmpeg','-v','error','-y','-i',str(video),'-i',str(poster),'-filter_complex',"[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]",'-map','[v]','-map','0:a?',
             '-c:v','libx264','-crf','18','-preset','slow','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(baked)])
        assert inspect(baked)==spec and audio_hash(baked)==original_audio
        # Exact named files inside this fresh authoring directory; preserve raw.
        video.rename(raw);baked.rename(video)
        run(['ffmpeg','-v','error','-y','-i',str(video),'-frames:v','1',str(folder/'first-frame.png')])
        receipt.update({'render_status':'RENDERED_VERIFIED','render':spec,'video_digest':sha(video),'poster_digest':sha(poster),
            'composition_digest':sha(folder/'composition/index.html'),'check_digest':sha(folder/'check.json'),
            'poster_baked_frame':0,'poster_source_seconds':8,'audio_preserved':True,'audio_hash':original_audio,
            'freshness':'CURRENT','published':False})
        write(folder/'video-receipt.json',json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');receipts.append(receipt)
        href=quote(Path(os.path.relpath(site/receipt['source_story'].replace('story.json','story.html'),output)).as_posix(),safe='/')
        code=plan['dossier'];cards.append('<article><h2>'+H(plan['name'])+'</h2><video controls preload="metadata" poster="'+code+'/brag.jpg" src="'+code+'/brag.mp4"></video><p>24 secondes · 1080p · 30 images/s · sources exactes.</p><p><a href="'+href+'">Lire l’architecture story complète</a> · <a href="'+code+'/brag.mp4">Télécharger le MP4</a> · <a href="'+code+'/video-receipt.json">Sources et empreintes</a></p></article>')
    write(output/'index.html','<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AIR - Architecture stories Asteria</title><style>body{margin:0;background:#f1f6f7;color:#17333c;font:17px/1.6 system-ui}header{padding:3rem 6vw;background:#153f4a;color:white;border-bottom:4px solid #6ed5c2}main{max-width:1300px;margin:auto;padding:2rem 5vw}article{padding:1.5rem;margin:2rem 0;background:white;border:1px solid #d0dfe4;border-radius:16px}video{width:100%;border-radius:8px;background:#153f4a}a{color:#17687c}h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.15}</style><header><p>AIR / ASTERIA</p><h1>Trois designs.<br>Leurs mécanismes et leurs choix.</h1><p>Démonstrations fictives. Récits de conception, aucune exécution métier.</p></header><main>'+''.join(cards)+'<p>Les MP4 sont des compagnons locaux du site. Leur présence ne modifie pas les critères de préparation. Conserver les sources et crédits lors de la transmission.</p></main></html>')
    write(output/'videos-receipt.json',json.dumps({'status':'PASS_SCOPED','videos':receipts,'business_execution_performed':False,'published':False},ensure_ascii=False,indent=2)+'\n')
    return receipts


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--site',required=True,type=Path)
    a=p.parse_args();print(json.dumps({'status':'PASS_SCOPED','videos':len(finalize(a.output.resolve(),a.site.resolve()))}))
