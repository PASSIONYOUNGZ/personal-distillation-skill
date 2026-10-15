"""Read-only Feishu connection probe, configurable CLI argv, no credential export.

Writing a smoke-test document is agent-managed inside an authorized destination.
"""
import argparse,json,subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--doc',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    config=json.loads(Path(a.config).read_text(encoding='utf-8-sig'));prefix=config['cli_argv']
    if not isinstance(prefix,list) or not prefix or not all(isinstance(x,str) for x in prefix):raise ValueError('cli_argv must be an argument array')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);formats=[]
    for fmt in ('markdown','xml'):
        cmd=prefix+['docs','+fetch','--doc',a.doc,'--doc-format',fmt,'--scope','full','--as','user']
        if fmt=='xml':cmd+=['--detail','full']
        proc=subprocess.run(cmd,capture_output=True,encoding='utf-8',errors='replace',timeout=90)
        result=json.loads(proc.stdout)
        if proc.returncode or result.get('ok') is not True:raise RuntimeError('CLI read not successful; inspect authorization through CLI')
        document=result['data']['document'];(out/('readback.'+('md' if fmt=='markdown' else 'xml'))).write_text(document['content'],encoding='utf-8');formats.append(fmt)
    print(json.dumps({'read_formats':formats,'reading_verified':True,'write_permission_verified':False,'note':'Agent must create/write/read back an authorized smoke test before claiming delivery capability.'}))

if __name__=='__main__':main()
