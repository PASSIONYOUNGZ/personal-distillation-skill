"""Timing accounting, crash recovery and actual entrypoint instrumentation."""
import json, subprocess, sys, unittest
from pathlib import Path
from unittest.mock import patch
from test_pipeline import test_workspace
from performance_trace import start,finish,span,events
from performance_report import analyze
from process_report import save


def row(a,b,category='writing',kind='phase',ident='a',parent=None,**more):
    return {'trace_event':'end','span_id':ident,'parent_id':parent,'stage':'writing','operation':category,
        'category':category,'span_kind':kind,'status':'passed','started_at':f'2026-01-01T00:00:{a:02d}Z',
        'ended_at':f'2026-01-01T00:00:{b:02d}Z',**more}


class PerformanceTrace(unittest.TestCase):
    def test_nested_and_parallel_spans_do_not_invent_wall_time(self):
        rows=[row(0,30,ident='phase'),row(5,15,'fetch','tool','fetch','phase'),row(10,20,'asr','tool','asr','phase')]
        report=analyze(rows)
        self.assertEqual(report['classified_union_seconds'],30)
        self.assertEqual(report['exclusive_seconds_by_category'],{'writing':15,'fetch':5,'parallel_mixed':5,'asr':5})
        self.assertEqual(report['parallel_same_priority_seconds'],5)
        self.assertEqual(report['unattributed_seconds'],0)

    def test_nested_tools_are_attributed_to_deepest_child(self):
        r=analyze([row(0,20,'fetch','tool','outer'),row(3,8,'subtitle','tool','child','outer')])
        self.assertEqual(r['exclusive_seconds_by_category'],{'fetch':15,'subtitle':5})

    def test_task_window_does_not_hide_missing_instrumentation(self):
        r=analyze([row(0,40,'task','task','task'),row(10,20,'browser','tool','a'),row(30,35,'writing','phase','b')])
        self.assertEqual(r['unattributed_seconds'],25)
        self.assertEqual(r['classified_union_seconds'],15)
        self.assertEqual(r['unattributed_gaps'][0]['seconds'],10)

    def test_real_context_writes_start_before_work_and_closes_exception(self):
        with test_workspace() as w:
            with self.assertRaises(RuntimeError):
                with span(w,'writing','article-batch',category='writing',kind='phase'):
                    self.assertEqual(events(w)[0]['trace_event'],'start')
                    with span(w,'acquisition','subtitle-read',category='subtitle'):raise RuntimeError('secret payload must not be logged')
            rows=events(w);self.assertEqual(len(rows),4)
            self.assertEqual(rows[1]['parent_id'],rows[0]['span_id'])
            self.assertEqual(rows[2]['status'],'failed');self.assertEqual(rows[3]['status'],'failed')
            self.assertNotIn('secret payload',json.dumps(rows))
            self.assertFalse(analyze(rows)['open_spans'])

    def test_open_spans_survive_report_without_timing_to_now(self):
        with test_workspace() as w:
            ident=start(w,'access','login-batch','user_wait','wait')
            save(w);r=analyze(events(w))
            self.assertEqual(r['open_spans'][0]['span_id'],ident)
            self.assertEqual(r['classified_union_seconds'],0)
            self.assertTrue((w/'.distill/performance-spans.csv').is_file())
            self.assertIn('未结束区间',(w/'.distill/过程记录.md').read_text(encoding='utf-8'))

    def test_persistent_cli_closes_span_in_another_process(self):
        script=Path(__file__).with_name('performance_trace.py')
        with test_workspace() as w:
            base=[sys.executable,'-B','-X','utf8',str(script),'--workspace',str(w)]
            started=subprocess.run([*base,'start','--stage','review','--operation','reading-batch','--category','source_reading'],capture_output=True,text=True,encoding='utf-8',check=True)
            ident=json.loads(started.stdout)['span_id']
            subprocess.run([*base,'end','--span-id',ident,'--items','3'],capture_output=True,text=True,check=True)
            self.assertEqual(events(w)[-1]['metrics']['items'],3)
            with self.assertRaisesRegex(ValueError,'already closed'):finish(w,ident)

    def test_retries_cache_and_asr_throughput_remain_separate(self):
        r=analyze([row(0,10,'asr','tool','a',attempt=1,status='failed'),
            row(10,30,'asr','tool','b',attempt=2,metrics={'media_seconds':40}),
            row(30,31,'other','tool','c',status='reused')])
        asr=next(x for x in r['bottlenecks'] if x['category']=='asr')
        self.assertEqual(asr['retry_attempts'],1);self.assertEqual(asr['failed_or_blocked'],1)
        self.assertEqual(r['asr']['real_time_factor'],.5)
        self.assertEqual(sum(x['reused'] for x in r['bottlenecks']),1)

    def test_payload_fields_and_url_labels_are_rejected_before_logging(self):
        with test_workspace() as w:
            for context in ({'argv':['x','secret']},{'cookie':'secret'}):
                with self.assertRaises(ValueError):start(w,'access','browser',**context)
            with self.assertRaises(ValueError):start(w,'access','https://example.org/?token=secret')
            self.assertEqual(events(w),[])
            ident=start(w,'review','batch')
            with self.assertRaises(ValueError):finish(w,ident,metrics={'transcript':'secret'})
            self.assertEqual(len(events(w)),1)

    def test_legacy_rows_remain_unknown_without_fabricating_phases(self):
        r=analyze([{'at':'2026-01-01T00:00:00Z'}, {'at':'2026-01-01T00:00:30Z','duration_seconds':4,'duration_kind':'tool_reported'}])
        self.assertEqual(r['classified_union_seconds'],0);self.assertEqual(r['unattributed_seconds'],30)
        self.assertEqual(r['bottlenecks'],[])

    def test_bootstrap_timeout_records_actual_failed_step(self):
        import bootstrap
        with test_workspace() as w:
            spec=bootstrap.plan(w,runtime_dir=w/'runtime')
            with patch('bootstrap.subprocess.run',side_effect=subprocess.TimeoutExpired(['hidden'],.01)):
                with self.assertRaises(subprocess.TimeoutExpired):bootstrap.install(spec)
            rows=events(w);self.assertEqual(rows[0]['category'],'setup')
            self.assertEqual(rows[-1]['status'],'failed');self.assertEqual(rows[-1]['error_type'],'TimeoutExpired')

    def test_real_video_cli_wrapper_emits_failed_trace_before_invalid_input(self):
        with test_workspace() as w:
            script=Path(__file__).with_name('video_tools.py')
            proc=subprocess.run([sys.executable,'-B',str(script),'whisper-batch','--input',str(w/'missing.json'),'--out',str(w/'receipt.json'),'--workspace',str(w)],capture_output=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertEqual(events(w)[-1]['status'],'failed');self.assertFalse(analyze(events(w))['open_spans'])


if __name__=='__main__':unittest.main()
