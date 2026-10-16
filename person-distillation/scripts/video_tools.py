"""Small interchangeable video primitives; local models, no embedded credentials."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,wave
from importlib.metadata import version,PackageNotFoundError
from datetime import datetime,timezone

def run(argv,timeout=180):return subprocess.run(argv,check=True,capture_output=True,timeout=timeout)
def extract(audio,out,ffmpeg):
    run([ffmpeg,'-hide_banner','-loglevel','error','-n','-i',str(audio),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(out)])
def load_whisper(model):
    from faster_whisper import WhisperModel
    if not model or not Path(model).is_dir():raise ValueError('Pass an existing local model directory; no automatic downloads')
    return WhisperModel(model,device='cpu',compute_type='int8',cpu_threads=4)

def whisper(audio,model,prompt,recognizer=None):
    if recognizer is None:recognizer=load_whisper(model)
    start=time.monotonic();iterator,info=recognizer.transcribe(str(audio),language='zh',vad_filter=True,beam_size=5,initial_prompt=prompt or None)
    result=[{'start':s.start,'end':s.end,'text':s.text} for s in iterator]
    return result,{'engine':'faster-whisper','prompt_used':bool(prompt),'duration':info.duration,'processing_seconds':round(time.monotonic()-start,3)}

def whisper_batch(jobs,model,prompt=None,loader=load_whisper,transcriber=whisper,workspace=None):
    """Reuse one model; persist each result and isolate item failures. Local files only."""
    if not isinstance(jobs,list) or not jobs:raise ValueError('Batch needs a nonempty job list')
    outputs=[Path(j['out']).resolve() for j in jobs]
    if len(set(outputs))!=len(outputs):raise ValueError('Duplicate batch output paths')
    if not model:raise ValueError('Existing local model required')
    model_path=Path(model).resolve()
    if not model_path.is_dir():raise ValueError('Existing local model required')
    signature=[(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(model_path.iterdir()) if p.is_file()]
    try:engine_version=version('faster-whisper')
    except PackageNotFoundError:engine_version='not-installed'
    model_key=hashlib.sha256(json.dumps([str(model_path),signature,prompt,engine_version],sort_keys=True).encode()).hexdigest()
    recognizer=None;rows=[];load_seconds=0
    from performance_trace import start,finish,span
    for job,target in zip(jobs,outputs):
        started=time.monotonic()
        started_at=datetime.now(timezone.utc).isoformat()
        item_span=start(workspace,'acquisition','whisper-batch-item',category='other',kind='phase',item_id=job.get('id')) if workspace else None
        def record(row):
            row.update(started_at=started_at,ended_at=datetime.now(timezone.utc).isoformat());rows.append(row)
            if workspace:
                finish(workspace,item_span,row['status'],error_type=row.get('error_type'),
                       metrics={'items':1,'cache_hits':int(row['status']=='reused'),'cache_misses':int(row['status']!='reused')},duration=time.monotonic()-started)
        try:
            source=Path(job['input']).resolve()
            source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
            key={'source_sha256':source_hash,'model_signature':model_key,'engine':'faster-whisper','language':'zh','beam_size':5,'vad_filter':True}
            if target.exists():
                old=json.loads(target.read_text(encoding='utf-8'))
                body_hash=hashlib.sha256(json.dumps(old.get('segments'),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                if old.get('metadata',{}).get('batch_cache')==key and old.get('segments') and old.get('metadata',{}).get('segments_sha256')==body_hash:
                    record({'id':job.get('id'),'status':'reused','out':str(target),'seconds':round(time.monotonic()-started,3)});continue
                raise ValueError('Existing output has different/unknown provenance; preserve and choose a new path')
            if recognizer is None:
                with span(workspace,'acquisition','whisper-model-load',category='model_load',parent_id=item_span):
                    loading=time.monotonic();recognizer=loader(str(model_path));load_seconds=round(time.monotonic()-loading,3)
            with span(workspace,'acquisition','whisper-transcribe',category='asr',parent_id=item_span,item_id=job.get('id')) as traced:
                segments,meta=transcriber(source,str(model_path),prompt,recognizer=recognizer)
                if not segments or not any(str(s.get('text','')).strip() for s in segments):raise ValueError('Empty transcript')
                traced['metrics']={'items':1,'media_seconds':meta.get('duration',0)}
            if not segments or not any(str(s.get('text','')).strip() for s in segments):raise ValueError('Empty transcript')
            target.parent.mkdir(parents=True,exist_ok=True)
            # Exclusive creation protects originals even if another job has written meanwhile.
            body_hash=hashlib.sha256(json.dumps(segments,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            with target.open('x',encoding='utf-8') as handle:json.dump({'segments':segments,'metadata':{**meta,'batch_cache':key,'segments_sha256':body_hash}},handle,ensure_ascii=False,indent=2)
            record({'id':job.get('id'),'status':'passed','out':str(target),'seconds':round(time.monotonic()-started,3)})
        except (OSError,ValueError,RuntimeError) as exc:
            record({'id':job.get('id'),'status':'failed','error_type':type(exc).__name__,'reason':str(exc),'seconds':round(time.monotonic()-started,3)})
    return {'items':rows,'model_load_seconds':load_seconds,'model_loads':int(recognizer is not None),'success':all(r['status']!='failed' for r in rows)}
def sense(audio,model,vad_path):
    if not model or not vad_path or not all(p.is_file() for p in (Path(model)/'model.int8.onnx',Path(model)/'tokens.txt',Path(vad_path))):
        raise ValueError('Existing SenseVoice model, tokens and VAD files are required')
    import numpy as np
    import sherpa_onnx as so
    with wave.open(str(audio),'rb') as f:
        if f.getframerate()!=16000 or f.getnchannels()!=1 or f.getsampwidth()!=2:raise ValueError('SenseVoice input must be mono 16kHz PCM16 WAV; extract first')
        values=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
    recognizer=so.OfflineRecognizer.from_sense_voice(model=str(Path(model)/'model.int8.onnx'),tokens=str(Path(model)/'tokens.txt'),num_threads=4,use_itn=True)
    cfg=so.VadModelConfig();cfg.sample_rate=16000;cfg.silero_vad.model=vad_path
    cfg.silero_vad.min_silence_duration=.3;cfg.silero_vad.min_speech_duration=.25;cfg.silero_vad.max_speech_duration=20
    vad=so.VoiceActivityDetector(cfg,buffer_size_in_seconds=30);window=cfg.silero_vad.window_size
    result=[];start=time.monotonic()
    def drain():
        while not vad.empty():
            clip=vad.front;begin=clip.start/16000;samples=clip.samples;duration=len(samples)/16000
            stream=recognizer.create_stream();stream.accept_waveform(16000,samples);recognizer.decode_stream(stream)
            result.append({'start':begin,'end':begin+duration,'text':stream.result.text});vad.pop()
    for pos in range(0,len(values),window):
        chunk=values[pos:pos+window]
        if len(chunk)<window:chunk=np.pad(chunk,(0,window-len(chunk)))
        vad.accept_waveform(chunk);drain()
    vad.flush();drain()
    return result,{'engine':'SenseVoice int8','duration':len(values)/16000,'processing_seconds':round(time.monotonic()-start,3)}
def execute(a):
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True);begin=time.monotonic()
    if a.command=='whisper-batch':
        if target.exists():raise ValueError('Batch receipt already exists; choose a new receipt path')
        result=whisper_batch(json.loads(Path(a.input).read_text(encoding='utf-8-sig')),a.model,a.prompt,workspace=a.workspace)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    elif a.command=='subtitle':
        if target.exists() and any(target.iterdir()):raise ValueError('Subtitle directory is not empty; reuse recorded files or choose a new directory')
        target.mkdir(exist_ok=True);proc=run([a.bbdown,a.input,'--sub-only','--skip-ai','false','-p','ALL','--work-dir',str(target)],90)
        (target/'subtitle.log').write_bytes(proc.stdout+proc.stderr)
        files=list(target.rglob('*.srt'));result={'files':[str(x) for x in files],'success':bool(files),'seconds':round(time.monotonic()-begin,3)}
    elif a.command=='extract':extract(Path(a.input),target,a.ffmpeg);result={'audio':str(target),'seconds':round(time.monotonic()-begin,3)}
    else:
        if target.exists():raise ValueError('Output already exists; preserve original and use a new path')
        segs,meta=whisper(Path(a.input),a.model,a.prompt) if a.command=='whisper' else sense(Path(a.input),a.model,a.vad)
        if not segs or not any(x['text'] for x in segs):raise RuntimeError('No transcript produced')
        target.write_text(json.dumps({'segments':segs,'metadata':meta},ensure_ascii=False,indent=2),encoding='utf-8');result=meta
    print(json.dumps(result,ensure_ascii=False))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['subtitle','extract','whisper','whisper-batch','sense']);p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--bbdown',default='BBDown');p.add_argument('--model');p.add_argument('--vad');p.add_argument('--prompt');p.add_argument('--workspace');a=p.parse_args()
    from performance_trace import span
    with span(a.workspace,'acquisition','video-'+a.command,category={'subtitle':'subtitle','extract':'other','whisper':'asr','sense':'asr'}.get(a.command,'other'),kind='phase' if a.command=='whisper-batch' else 'tool') as traced:
        result=execute(a)
        if result.get('success') is False:traced['status']='partial'
    if result.get('success') is False:raise SystemExit(1)

if __name__=='__main__':main()
