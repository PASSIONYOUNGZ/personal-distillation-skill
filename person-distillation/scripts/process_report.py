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
        if row.get('trace_event')=='start':continue
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
    times=[instant(r.get('at')) for r in events if instant(r.get('at')) is not None]
    stage_timing={stage:timing([r for r in events if r.get('stage')==stage]) for stage in dict.fromkeys(r.get('stage','unknown') for r in events)}
    from performance_report import analyze
    performance=analyze(events)
    report={'schema_version':3,'performance':performance,'request':read(w/'request.json',{}),
      'checkpoint':read(d/'checkpoint.json',{}),'verification':read(d/'verification.json',{}),
      'event_count':len(events),'stages':dict(Counter(row.get('stage','unknown') for row in events)),
      'outcomes':dict(Counter(row.get('status','unknown') for row in events)),
      'timing':timing(events),'stage_timing':stage_timing,
      'observed_event_span_seconds':round(max(times)-min(times),6) if len(times)>1 else None,
      'timing_coverage_warning':'Event span includes unlogged work and user waiting; command durations alone are not task duration.',
      'failed_or_blocked':[row for row in events if row.get('status') in ('failed','blocked')],
      'reuse_events':[row for row in events if row.get('status')=='reused' or row.get('reused') is True],
      'acquisition':[{'receipt_id':row.get('receipt_id'),'source_id':row.get('source_id') or row.get('channel'),
                     'capability':row.get('capability'),'route_id':row.get('route_id') or row.get('route'),
                     'decision':row.get('decision',{}),'evidence':row.get('evidence',[])} for row in acquired],
      'acquisition_log_status':{'path':'.distill/acquisition-log.jsonl','exists':(d/'acquisition-log.jsonl').is_file(),'receipts':len(acquired),
                                'boundary':'This table covers the uniform log only; its absence does not establish that no collection occurred.'},
      'warnings':warnings,'basis':'Existing logs and receipts only; interpretation and unobserved work require the agent.'}
    return report


def escaped(value):
    return str(value if value is not None else '未记录').replace('|','\\|').replace('\r',' ').replace('\n',' ')


def save(workspace):
    w=Path(workspace).resolve();report=summarize(w);d=w/'.distill';d.mkdir(parents=True,exist_ok=True)
    (d/'process-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    from performance_report import write_csv
    write_csv(d/'performance-spans.csv',report['performance'])
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
      '首末日志事件跨度：'+escaped(report['observed_event_span_seconds'])+' 秒（包含未定位工作与等待，不是各工具耗时之和）。',
      '无起止定位的耗时按类型保留：'+escaped(json.dumps(report['timing']['unpositioned_seconds_by_kind'],ensure_ascii=False))+'。',
      '以上不是任务总耗时，不能相加推算整轮耗时；并发、模型工作与未记录等待没有被补算。','',
      '## 获取与失败路线','', '| 来源 | 能力 | 路线 | 实际结果 | 下一步 |','| --- | --- | --- | --- | --- |']
    perf=report['performance']
    details=['## 耗时诊断','',
      '已分类区间并集：'+escaped(perf['classified_union_seconds'])+' 秒；日志跨度内未定位：'+escaped(perf['unattributed_seconds'])+' 秒。',
      '阶段窗口含Agent思考、工具和调度；不能据此称为模型纯计算。未结束区间：'+str(len(perf['open_spans']))+' 个，不补算到当前时间。','',
      '| 互斥归类（秒） | 区间 |','| --- | --- |']
    details += ['| '+escaped(k)+' | '+str(v)+' |' for k,v in sorted(perf['exclusive_seconds_by_category'].items(),key=lambda x:x[1],reverse=True)]
    details += ['','不同类别同时发生的工具/等待保留为parallel_mixed，不能唯一归因。父阶段与子工具不重复累计。','',
      '| 阶段 / 操作 | 次数 | 工作秒数合计（可重叠） | 最慢一次 | 失败/受阻 | 重试次数 | 复用 |',
      '| --- | --- | --- | --- | --- | --- | --- |']
    for r in perf['bottlenecks'][:20]:
        details.append('| '+' | '.join(escaped(v) for v in (str(r['stage'])+' / '+str(r['operation']),r['calls'],r['work_seconds_sum'],r['max_seconds'],r['failed_or_blocked'],r['retry_attempts'],r['reused']))+' |')
    details+=['','### 最长未定位区间','']
    details += ['- '+r['started_at']+' → '+r['ended_at']+'：'+str(r['seconds'])+' 秒。' for r in perf['unattributed_gaps'][:10]]
    if not perf['unattributed_gaps']:details+=['已有日志跨度内没有未定位空档；这不证明覆盖了任务开始之前或结束之后。']
    details+=['','### 未结束区间与计时异常','']
    details+=['- '+escaped(r.get('span_id'))+' / '+escaped(r.get('operation'))+' / '+escaped(r.get('started_at')) for r in perf['open_spans']]
    details+=['- '+escaped(x) for x in perf['warnings']]
    if not perf['open_spans'] and not perf['warnings']:details+=['已有记录未见未闭合区间或时钟异常。']
    details+=['','明细见performance-spans.csv；JSON保留完整排行、区间和可定位的ASR实时率。未知空档须结合实际动作补采，不能倒填猜测。','']
    position=rows.index('## 获取与失败路线');rows[position:position]=details
    for row in report['acquisition']:
        decision=row['decision'];rows.append('| '+' | '.join(escaped(x) for x in (row['source_id'],row['capability'],row['route_id'],decision.get('outcome'),decision.get('action')))+' |')
    if not report['acquisition']:rows+=['','统一获取日志未记录可列出的回执；这不代表没有获取。自定义下载、正文与媒体回执须另按实际路径核查，不能据此按平台推算耗时。']
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
    return {'json':'.distill/process-report.json','markdown':'.distill/过程记录.md','timing_csv':'.distill/performance-spans.csv','event_count':report['event_count']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',required=True)
    print(json.dumps(save(parser.parse_args().workspace),ensure_ascii=False))
