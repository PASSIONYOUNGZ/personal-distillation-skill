"""Summarize existing receipts; never infer unseen work, missing time or success."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import argparse, json, math


def read(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else default


def log(path, warnings):
    result=[]
    if path.is_file():
        for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if not line.strip(): continue
            try:
                value=json.loads(line)
                if not isinstance(value,dict): raise ValueError('Event is not an object')
                result.append(value)
            except (ValueError,TypeError): warnings.append(f'{path.name}:{n}: unreadable event retained in original log')
    return result


def instant(value):
    if not isinstance(value,str): return None
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError,OverflowError): return None


def timing(events):
    intervals=[];unpositioned=Counter();unknown=0
    for row in events:
        start,end=instant(row.get('started_at')),instant(row.get('ended_at'))
        if start is not None and end is not None and end>=start:
            intervals.append((start,end));continue
        duration=row.get('duration_seconds')
        if type(duration) in (int,float) and math.isfinite(duration) and duration>=0:
            unpositioned[row.get('duration_kind','unspecified')]+=duration
        else:unknown+=1
    merged=[]
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],end))
        else:merged.append((start,end))
    return {'positioned_interval_count':len(intervals),
            'observed_union_seconds':round(sum(end-start for start,end in merged),6) if merged else None,
            'unpositioned_seconds_by_kind':dict(unpositioned),'events_without_measured_duration':unknown,
            'is_total_task_duration':False,
            'boundary':'Only positioned measured intervals are unioned. Unpositioned durations may overlap and are not added to total; model work and unknown waiting time are not estimated.'}


def summarize(workspace):
    w=Path(workspace).resolve();d=w/'.distill';warnings=[]
    events=log(d/'run-log.jsonl',warnings);acquired=log(d/'acquisition-log.jsonl',warnings)
    report={'schema_version':1,'request':read(w/'request.json',{}),
      'checkpoint':read(d/'checkpoint.json',{}),'verification':read(d/'verification.json',{}),
      'event_count':len(events),'stages':dict(Counter(row.get('stage','unknown') for row in events)),
      'outcomes':dict(Counter(row.get('status','unknown') for row in events)),
      'timing':timing(events),'failed_or_blocked':[row for row in events if row.get('status') in ('failed','blocked')],
      'reuse_events':[row for row in events if row.get('status')=='reused' or row.get('reused') is True],
      'acquisition':[{'receipt_id':row.get('receipt_id'),'source_id':row.get('source_id') or row.get('channel'),
                     'capability':row.get('capability'),'route_id':row.get('route_id') or row.get('route'),
                     'decision':row.get('decision',{}),'evidence':row.get('evidence',[])} for row in acquired],
      'warnings':warnings,'basis':'Existing logs and receipts only; interpretation and unobserved work require the agent.'}
    return report


def escaped(value):
    return str(value if value is not None else '未记录').replace('|','\\|').replace('\r',' ').replace('\n',' ')


def save(workspace):
    w=Path(workspace).resolve();report=summarize(w);d=w/'.distill';d.mkdir(parents=True,exist_ok=True)
    (d/'process-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    person=report['request'].get('person',{}).get('name','待确认人物')
    rows=['# '+escaped(person)+' · 过程记录','',
      '本文件由已有请求、断点、获取回执与运行日志生成。没有记录的动作或耗时保持未知，内容质量仍以实际原文审阅为准。','',
      '## 当前状态','',
      '- 请求范围：'+escaped(json.dumps(report['request'].get('scope',{}),ensure_ascii=False)),
      '- 接续动作：'+escaped(report['checkpoint'].get('next_action')),
      '- 原范围完成：'+escaped(report['verification'].get('original_request_complete')),
      '- 成果可交付：'+escaped(report['verification'].get('artifact_ready')),
      '- 记录事件：'+str(report['event_count']),'','## 已知耗时','',
      '有定位的实测区间去重合并：'+escaped(report['timing']['observed_union_seconds'])+' 秒。',
      '无起止定位的耗时按类型保留：'+escaped(json.dumps(report['timing']['unpositioned_seconds_by_kind'],ensure_ascii=False))+'。',
      '以上不是任务总耗时，不能相加推算整轮耗时；并发、模型工作与未记录等待没有被补算。','',
      '## 获取与失败路线','', '| 来源 | 能力 | 路线 | 实际结果 | 下一步 |','| --- | --- | --- | --- | --- |']
    for row in report['acquisition']:
        decision=row['decision'];rows.append('| '+' | '.join(escaped(x) for x in (row['source_id'],row['capability'],row['route_id'],decision.get('outcome'),decision.get('action')))+' |')
    if not report['acquisition']:rows+=['','本任务尚无获取回执；纯本地导入或未开始获取都可能如此，不能据此判断平台失败。']
    rows+=['','## 失败与待处理事件','']
    for row in report['failed_or_blocked']:
        detail='；'.join(escaped(row[key]) for key in ('error_type','summary','next_action') if row.get(key))
        rows.append('- '+escaped(row.get('at'))+' / '+escaped(row.get('stage'))+' / '+escaped(row.get('operation'))+'：'+(detail or '未记录具体原因'))
        if row.get('evidence'):rows.append('  依据：'+escaped('；'.join(row['evidence'])))
    if not report['failed_or_blocked']:rows+=['已有日志未记录失败或阻塞；这不证明未记录的动作都已成功。']
    rows+=['','## 交付检查限制','']
    for limitation in report['verification'].get('delivery_limitations',[]):
        rows.append('- '+escaped(limitation.get('check'))+'：'+escaped(limitation.get('status'))+'；'+escaped(limitation.get('reason')))
    if not report['verification']:rows+=['尚无最终verification回执。']
    if warnings:=report['warnings']:rows+=['','## 记录读取问题','',*['- '+escaped(x) for x in warnings]]
    (d/'过程记录.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    return {'json':'.distill/process-report.json','markdown':'.distill/过程记录.md','event_count':report['event_count']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',required=True)
    print(json.dumps(save(parser.parse_args().workspace),ensure_ascii=False))
