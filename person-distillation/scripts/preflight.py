"""Remember access capability and tool locations; never logs in or reads cookies."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from urllib.parse import urlparse

def x_browser_policy(channel):
    host=(urlparse(channel.get('url') or '').hostname or '').lower()
    names={str(channel.get(k,'')).strip().lower() for k in ('name','platform')}
    is_x=bool(names & {'x','twitter'}) or any(host==d or host.endswith('.'+d) for d in ('x.com','twitter.com'))
    if not is_x:return None
    browser=str(channel.get('browser') or '').strip()
    internal=browser.lower() in ('iab','mcpapps','codex','internal','in-app','in-app browser') or browser.lower().startswith('codex') or '内置' in browser
    selected=bool(browser) and not internal and (channel.get('browser_scope')=='external' or browser.lower() in ('chrome','edge','firefox','safari'))
    return {'required_browser_scope':'external','internal_login_allowed':False,'browser':browser or None,
            'external_connection_verified':bool(selected and channel.get('browser_connected') is True and channel.get('browser_evidence'))}

def environment(config, workspace):
    """Only named configuration files; never recursively scan other chats/home."""
    registry=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'person-distillation/environment.json'
    paths=[registry,Path(workspace)/'environment.json']
    if config.get('environment_file'):paths.append(Path(config['environment_file']).expanduser())
    merged={};used=[]
    for path in dict.fromkeys(paths):
        if path.is_file():
            saved=read(path,{})
            for field in ('tools','models'):
                merged.setdefault(field,{}).update(saved.get(field,{}))
            for field in ('python','tool_search_dirs'):
                if field in saved:merged[field]=saved[field]
            used.append(str(path))
    for field in ('tools','models'):merged.setdefault(field,{}).update(config.get(field,{}))
    for field in ('python','tool_search_dirs'):
        if field in config:merged[field]=config[field]
    return merged,used

def python_environment(config):
    python=resolve(config.get('python') or sys.executable)
    if not python:return {'status':'invalid_configuration','path':None,'modules':{}}
    code="import importlib.util,json,sys;print(json.dumps({'version':sys.version.split()[0],'modules':{m:bool(importlib.util.find_spec(m)) for m in ('faster_whisper','sherpa_onnx')}}))"
    try:
        p=subprocess.run([python,'-I','-c',code],capture_output=True,text=True,timeout=12,check=True)
        return {'status':'available','path':python,**json.loads(p.stdout)}
    except (OSError,subprocess.SubprocessError,ValueError):return {'status':'probe_failed','path':python,'modules':{}}

def read(path,default):return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def resolve(value):
    first=value[0] if isinstance(value,list) and value else value
    if not isinstance(first,str):return None
    path=Path(first).expanduser()
    return str(path.resolve()) if path.is_file() else shutil.which(first)
def tools(config,dirs):
    names={'ffmpeg':['ffmpeg','ffmpeg.exe'],'bbdown':['BBDown','BBDown.exe'],'yt_dlp':['yt-dlp','yt-dlp.exe'],'feishu':['lark-cli','lark-cli.cmd']}
    result={};patch={}
    for key,candidates in names.items():
        configured=config.get('tools',{}).get(key)
        path=resolve(configured) if configured else next((v for n in candidates if (v:=shutil.which(n))),None)
        origin='configured' if configured and path else 'PATH' if path else None
        if not path and not configured:
            for directory in dirs:
                for name in candidates:
                    candidate=Path(directory).expanduser()/name
                    if candidate.is_file():path=str(candidate.resolve());origin='provided directory';break
                if path:break
        result[key]={'path':path,'status':'available' if path else 'invalid_configuration' if configured else 'not_installed','origin':origin}
        if path and not configured:patch[key]=path
    return result,patch
from access_state import assess

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',required=True);parser.add_argument('--tool-dir',action='append',default=[]);parser.add_argument('--refresh',action='store_true');parser.add_argument('--remember-access',action='store_true');parser.add_argument('--phase',choices=['preparation','running'],default='preparation');parser.add_argument('--require-ready',action='store_true');a=parser.parse_args()
    w=Path(a.workspace).resolve();config_path=w/'config.json';config=read(config_path,{});access=read(w/'access.json',{})
    from user_access import load_candidates,remember
    access,access_records=load_candidates(config,access)
    env,used=environment(config,w);dirs=a.tool_dir or env.get('tool_search_dirs',[])
    # File/tool probes are cheap; recheck paths after moves instead of trusting a stale hash.
    found,patch=tools(env,dirs);python=python_environment(env)
    signature=hashlib.sha256(json.dumps({'env':env,'dirs':dirs,'access':access,'phase':a.phase},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    known=read(w/'.distill/source-ledger.json',{}).get('sources',[])
    requested=config.get('request',{}).get('scope',{}).get('platforms',[])
    if requested:known=[s for s in known if s.get('platform') in requested]
    result={'signature':signature,'observed_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'connection_record_reused':bool(access.get('channels')),
        'environment_records':used,'access_registry_records':access_records,'saved_access_candidates':access.get('saved_access_candidates',[]),'python':python,'tools':found,'modules':python.get('modules',{}),
        'models':{k:{'path':str(Path(v).expanduser()),'exists':Path(v).expanduser().exists()} for k,v in env.get('models',{}).items() if isinstance(v,str)},**assess(access,a.phase,known)}
    if config.get('needs_video') and not any(r['capability']=='video_path' for r in result['ready_capabilities']):
        result['agent_checks'].append({'action':'probe_subtitle_or_audio_asr_path_for_selected_video','reason':'Tool presence alone is not a usable video route'})
        result['formal_collection_ready']=False
        if result['readiness']=='ready':result['readiness']='needs_probe'
    from preparation_gate import save,passed
    if a.phase=='preparation':save(w,result)
    result['initial_preparation_complete']=passed(w)
    result['workflow_collection_allowed']=result['initial_preparation_complete'] and bool(result['allowed_operations'])
    result['note']='Check source/capability/route before each operation; running never globally authorizes blocked routes.'
    if a.remember_access:result['access_registry_saved']=remember(config,access)
    write(w/'.distill/preflight.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.require_ready and not result['workflow_collection_allowed']:raise SystemExit(1)
if __name__=='__main__':main()
