"""Small interchangeable video primitives; local models, no embedded credentials."""
from pathlib import Path
import argparse,json,subprocess,time,wave

def run(argv,timeout=180):return subprocess.run(argv,check=True,capture_output=True,timeout=timeout)
def extract(audio,out,ffmpeg):
    run([ffmpeg,'-hide_banner','-loglevel','error','-n','-i',str(audio),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(out)])
def whisper(audio,model,prompt):
    from faster_whisper import WhisperModel
    if not model or not Path(model).is_dir():raise ValueError('Pass an existing local model directory; no automatic downloads')
    recognizer=WhisperModel(model,device='cpu',compute_type='int8',cpu_threads=4)
    start=time.monotonic();iterator,info=recognizer.transcribe(str(audio),language='zh',vad_filter=True,beam_size=5,initial_prompt=prompt or None)
    result=[{'start':s.start,'end':s.end,'text':s.text} for s in iterator]
    return result,{'engine':'faster-whisper','prompt_used':bool(prompt),'duration':info.duration,'processing_seconds':round(time.monotonic()-start,3)}
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
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['subtitle','extract','whisper','sense']);p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--bbdown',default='BBDown');p.add_argument('--model');p.add_argument('--vad');p.add_argument('--prompt');a=p.parse_args()
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True);begin=time.monotonic()
    if a.command=='subtitle':
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

if __name__=='__main__':main()
