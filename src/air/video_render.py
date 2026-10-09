"""Explicit local optional renderer. No API/MCP execution or publication."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from air.atelier import safe_path

VERSION = '0.8.143'


def render(root, prepared):
    root = Path(root).resolve()
    npx = shutil.which('npx.cmd') or shutil.which('npx')
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not all((npx, ffmpeg, ffprobe)): raise ValueError('Optional rendering requires Node/npx, Chromium, FFmpeg and FFprobe; compositions remain prepared')
    folder = (root / safe_path(prepared['directory'])).resolve()
    if not folder.is_relative_to(root): raise ValueError('Video output is outside workspace')
    sha = lambda p: 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
    for f in prepared['files']:
        path = (root / safe_path(f['path'])).resolve()
        if not path.is_relative_to(folder) or path.is_symlink() or sha(path) != f['content_digest']:
            raise ValueError('Video source differs from the prepared exact file set')
    receipt_path = folder / 'render-receipt.json'
    if receipt_path.exists():
        previous = json.loads(receipt_path.read_text(encoding='utf-8'))
        if previous.get('source_digest') != prepared['source_digest']: raise ValueError('Existing video receipt belongs to another source')
        if previous.get('source_files') != {f['path']:f['content_digest'] for f in prepared['files']}:
            raise ValueError('Existing video receipt has a different composition or source file set')
        if previous.get('status') != 'RENDERED_CHECKED_LOCAL' or previous.get('baseline') != prepared['baseline'] or {v.get('file') for v in previous.get('videos', [])} != {v['name']+'.mp4' for v in prepared['videos']}:
            raise ValueError('Existing video receipt is incomplete or belongs to another baseline')
        if all(sha(folder / safe_path(v['file'])) == v['digest'] and sha(folder / safe_path(v['poster'])) == v['poster_digest'] for v in previous['videos']): return previous
        raise ValueError('An existing rendered video was changed; preserve it and use a new workshop')
    videos = []
    def run(args, cwd, log):
        with (folder / log).open('w', encoding='utf-8') as stream:
            result = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode: raise ValueError('Video operation failed; inspect '+log+' in the local workshop')
    for video in prepared['videos']:
        name = video['name']; comp = folder/name
        base = [npx, '--yes', 'hyperframes@'+VERSION]
        run(base+['check', '.', '--json', '--snapshots', '--at', '3,9,15,21'], comp, name+'-check.json')
        output = folder/(name+'.mp4')
        if output.exists(): raise ValueError('Existing MP4 without a receipt is preserved; choose a new workshop')
        run(base+['render', '.', '--output', str(folder/(name+'-raw.mp4')), '--quality', 'delivery', '--fps', '30', '--skill', 'brag'], comp, name+'-render.log')
        poster = folder/(name+'.jpg')
        run([ffmpeg,'-y','-ss','9','-i',str(folder/(name+'-raw.mp4')),'-frames:v','1','-q:v','2',str(poster)], folder, name+'-poster.log')
        run([ffmpeg,'-y','-i',str(folder/(name+'-raw.mp4')),'-i',str(poster),'-filter_complex',"[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]",'-map','[v]','-map','0:a?','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(output)], folder, name+'-encode.log')
        probe = json.loads(subprocess.check_output([ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(output)], timeout=60))
        stream = next(s for s in probe['streams'] if s['codec_type']=='video')
        if stream['width']!=1920 or stream['height']!=1080 or abs(float(probe['format']['duration'])-24)>.1:
            raise ValueError('Rendered video format or duration differs from composition')
        run([ffmpeg,'-v','error','-i',str(output),'-f','null','-'],folder,name+'-decode.log')
        videos.append({'file':output.name,'digest':sha(output),'poster':poster.name,'poster_digest':sha(poster),'duration_seconds':probe['format']['duration'],'width':1920,'height':1080})
    receipt = {'engine':'air.video-render/1','source_digest':prepared['source_digest'],'baseline':prepared['baseline'],
        'status':'RENDERED_CHECKED_LOCAL','hyperframes_version':VERSION,'videos':videos,'published':False,
        'source_files':{f['path']:f['content_digest'] for f in prepared['files']},'business_execution_performed':False}
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt
