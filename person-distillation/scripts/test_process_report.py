"""Regression of traceability, overlap accounting and source structure."""
import json, unittest
from unittest.mock import patch
from test_pipeline import test_workspace
from test_contracts import fixture, quality_spec
from evidence_review import accept_quality, quality_status
from article_structure import structure
from read_public_article import Extractor, fetch
from document_render import render_document
from runlog import append
from process_report import save, summarize, timing
import acquisition


class ProcessReport(unittest.TestCase):
    def test_absent_uniform_log_does_not_claim_no_acquisition_receipts(self):
        with test_workspace() as w:
            custom=w/'download-receipt.json'
            custom.write_text('{"status":"downloaded","seconds":12}',encoding='utf-8')
            append(w,{'stage':'acquisition','status':'passed','operation':'custom-download','evidence':['download-receipt.json']})
            before=custom.read_bytes();save(w);report=summarize(w)
            self.assertFalse(report['acquisition_log_status']['exists'])
            self.assertEqual(report['acquisition'],[])
            text=(w/'.distill/过程记录.md').read_text(encoding='utf-8')
            self.assertNotIn('本任务尚无获取回执',text)
            self.assertIn('这不代表没有获取',text)
            self.assertEqual(custom.read_bytes(),before)

    def test_parallel_measurements_are_unioned_without_inventing_total_time(self):
        rows=[{'started_at':'2026-01-01T00:00:00Z','ended_at':'2026-01-01T00:00:10Z'},
              {'started_at':'2026-01-01T08:00:05+08:00','ended_at':'2026-01-01T08:00:20+08:00'},
              {'duration_seconds':43.25,'duration_kind':'tool_reported'}, {'at':'2026-01-01T00:00:25Z'}]
        result=timing(rows)
        self.assertEqual(result['observed_union_seconds'],20)
        self.assertEqual(result['unpositioned_seconds_by_kind'],{'tool_reported':43.25})
        self.assertFalse(result['is_total_task_duration']);self.assertEqual(result['events_without_measured_duration'],1)

    def test_route_context_survives_and_report_does_not_invalidate_content_review(self):
        with test_workspace() as w:
            _,items,_=fixture(w);accept_quality(w,quality_spec(items))
            append(w,{'stage':'review','status':'reused','item_id':'sample-article','version':'v1',
                      'source_id':'author-a','route_id':'saved-original','output_files':['materials/article.md'],'reused':True})
            acquisition.record(w,{'purpose':'probe','source_id':'author-a','channel':'A','capability':'text',
                                 'route':'native','source_kind':'native','outcome':'tool_timeout','evidence':['synthetic timeout']})
            before=(w/'.distill/quality-review.json').read_bytes();save(w)
            result=summarize(w)
            self.assertTrue(quality_status(w)[0]);self.assertEqual(before,(w/'.distill/quality-review.json').read_bytes())
            self.assertEqual(result['reuse_events'][0]['version'],'v1')
            self.assertEqual(result['failed_or_blocked'][0]['source_id'],'author-a')
            self.assertEqual(result['acquisition'][0]['decision']['outcome'],'tool_timeout')

    def test_incomplete_and_malformed_logs_are_preserved_without_claiming_success(self):
        with test_workspace() as w:
            folder=w/'.distill';folder.mkdir(exist_ok=True)
            original='{"stage":"access","status":"blocked"}\nnot json\n'
            (folder/'run-log.jsonl').write_text(original,encoding='utf-8')
            save(w);result=summarize(w)
            self.assertEqual(len(result['warnings']),1);self.assertEqual(result['verification'],{})
            self.assertIsNone(result['timing']['observed_union_seconds'])
            self.assertEqual((folder/'run-log.jsonl').read_text(encoding='utf-8'),original)

    def test_article_structure_and_lazy_image_locations_survive_without_executing_html(self):
        parser=Extractor();parser.feed('<nav>ignore</nav><div id="js_content"><h2>步骤</h2><p>前文<a href="/ref">来源</a></p>'
          '<img data-src="/picture.png" alt="步骤图"><ol start="3"><li>第三步</li><li value="7">第七步</li></ol>'
          '<pre>if ready:\n    keep = &quot;&lt;tag&gt;&quot;</pre><table><tr><th>条件</th><th>动作</th></tr><tr><td>A</td><td>B</td></tr></table>'
          '<blockquote>引用</blockquote><p>结尾<script>window.bad=1</script></p></div>')
        _,_,selected=parser.primary();document,images=structure(parser.container_nodes[selected],'https://example.org/post')
        html=render_document(document)
        for text in ('<h2>步骤</h2>','href="https://example.org/ref"','value="3"','value="7"','    keep =','<th>条件</th>','<blockquote>引用</blockquote>','结尾'):
            self.assertIn(text,html)
        self.assertNotIn('window.bad',html);self.assertNotIn('ignore',html)
        self.assertEqual(images[0]['url'],'https://example.org/picture.png');self.assertEqual(images[0]['block_index'],2)

    def test_article_structure_never_activates_source_javascript_links(self):
        parser=Extractor();parser.feed('<article><p>A<a href="javascript:alert(1)">unsafe</a></p><pre>&lt;script&gt;literal&lt;/script&gt;</pre></article>')
        _,_,selected=parser.primary();document,_=structure(parser.container_nodes[selected],'https://example.org/post')
        html=render_document(document)
        self.assertIn('unsafe',html);self.assertNotIn('href="javascript:',html)
        self.assertIn('&lt;script&gt;literal&lt;/script&gt;',html)
        parser=Extractor();parser.feed('<article><table><tr><td>original data</td></tr></table></article>')
        _,_,selected=parser.primary();document,_=structure(parser.container_nodes[selected],'https://example.org/post')
        self.assertIn('<td>original data</td>',render_document(document));self.assertNotIn('<th>',render_document(document))

    def test_public_fetch_saves_raw_body_structured_document_and_image_positions(self):
        class Headers:
            def get_content_type(self):return 'text/html'
        class Response:
            headers=Headers();url='https://example.org/post'
            def read(self,n):return ('<article><h2>结构标题</h2><p>'+('完整原文。'*30)+'</p><img data-src="/image.png"></article>').encode()
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with test_workspace() as w,patch('read_public_article.urllib.request.urlopen',return_value=Response()):
            result=fetch('https://example.org/post',w/'article')
            doc=json.loads((w/'article/article-document.json').read_text(encoding='utf-8'))
            self.assertEqual(doc['blocks'][0],{'type':'heading','text':'结构标题','level':2})
            self.assertIn('完整原文。'*30,(w/'article/article.txt').read_text(encoding='utf-8'))
            self.assertTrue((w/'article/page.html').is_file());self.assertTrue(result['coverage_requires_agent_check'])
            self.assertEqual(result['image_positions'][0]['url'],'https://example.org/image.png')


if __name__=='__main__':unittest.main()
