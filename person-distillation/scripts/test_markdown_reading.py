"""Real render bridge regressions: explanations once, full originals preserved."""
import unittest
from test_pipeline import test_workspace
from test_contracts import fixture
import distill


class MarkdownReadingTests(unittest.TestCase):
    def test_legacy_section_image_path_is_relative_to_export(self):
        with test_workspace() as w:
            _,_,cards=fixture(w)
            config=distill.read(w/'config.json');config['output']['formats']=['markdown'];distill.write(w/'config.json',config)
            # The real renderer must relocate a task-root path into output/.
            frame=w/'materials/frame.png'
            frame.write_bytes(b'local fixture')
            cards[0]['analysis_sections']=[{'title':'Observed frame','paragraphs':['The picture supports this step.'],
                'images':[{'path':'materials/frame.png','caption':'00:12 source frame','source_url':'https://example.com/video'}]}]
            distill.write(w/'.distill/cards.json',cards)
            distill.render(w)
            markdown=(w/'output/人物蒸馏.md').read_text(encoding='utf-8')
            self.assertIn('src="../materials/frame.png"',markdown)
            self.assertTrue((w/'output/../materials/frame.png').is_file())
            self.assertEqual(distill.read(w/'.distill/cards.json')[0]['analysis_sections'][0]['images'][0]['path'],'materials/frame.png')

    def test_viewpoints_share_map_order_and_escape_emphasis_without_touching_originals(self):
        from test_reader_feedback import fixture as reader_fixture
        from markdown_reading import parts
        data=reader_fixture();units=data['reading_units']
        units[1].update(summary='Zara: <a> expresses a precise judgment, then gives context.',
                        highlights=['<a> expresses a precise judgment'])
        data['reading_units']=[units[n] for n in (0,2,1,3)]
        body='\n'.join(parts(data,lambda label,url:'['+label+']('+url+')'))
        self.assertLess(body.index('### Ideas'),body.index('### Other'))
        self.assertIn('<strong>&lt;a&gt; expresses a precise judgment</strong>',body)
        self.assertNotIn('<a> expresses',body)
        self.assertIn('Exact original 1\nSecond original line.',body)

    def test_layered_pipeline_preserves_complete_article_and_both_speech_versions_once(self):
        with test_workspace() as w:
            _,_,cards=fixture(w)
            explanation='读者需要知道这次具体改动的来由、步骤与结果，不能只得到一句短摘要。'
            cards[0].update(reading_layer='deep',analysis_sections=[{'title':'完整解释','paragraphs':[explanation]}])
            cards[1]['reading_layer']='viewpoint'
            distill.write(w/'.distill/cards.json',cards)
            packet=distill.read(w/'.distill/packets/sample-video.json')
            spec={'item_id':'sample-video','raw_sha256':packet['raw_sha256'],
                'edits':[{'segment_index':0,'before':'v2','after':'v3','status':'confirmed','sensitive_change_verified':True,
                    'evidence':[{'basis':'synthetic correction fixture','file':'materials/video.json'}]}]}
            distill.write(w/'correction.json',spec);distill.review(w,w/'correction.json')
            before={name:distill.sha(w/name) for name in ('materials/article.md','materials/video.json')}
            distill.render(w)
            markdown=(w/'output/人物蒸馏.md').read_text(encoding='utf-8')
            original=(w/'materials/article.md').read_text(encoding='utf-8')
            self.assertIn(original,markdown)
            self.assertEqual(markdown.count(explanation),1)
            self.assertEqual(markdown.count('Evidence API v2.'),1)
            self.assertEqual(markdown.count('Evidence API v3.'),1)
            self.assertIn('校正依据与待核',markdown)
            self.assertIn('synthetic correction fixture',markdown)
            self.assertIn('原文全文',markdown)
            self.assertIn('<details>',markdown)
            self.assertEqual(before,{name:distill.sha(w/name) for name in before})

    def test_viewpoint_expansion_has_originals_without_old_analysis(self):
        with test_workspace() as w:
            _,items,cards=fixture(w)
            cards[0].update(reading_layer='viewpoint',what='甲来源独立说明：三次比较之中的第二次存在不同条件。')
            cards[1].update(reading_layer='viewpoint',what='乙来源独立说明：失败案例没有得到最终解决。')
            distill.write(w/'.distill/cards.json',cards)
            distill.write(w/'.distill/reading-units.json',[{'id':'merged','kind':'viewpoint','item_ids':[i['id'] for i in items],
                'title':'对比两个来源的判断','topic':'合成观点','summary':'两个来源共同提醒检查具体条件。',
                'paragraphs':['聚合后的主线只提取共同判断，不代表两篇来源所有细节。']}])
            distill.render(w)
            markdown=(w/'output/人物蒸馏.md').read_text(encoding='utf-8')
            self.assertEqual(markdown.count('两个来源共同提醒检查具体条件。'),1)
            self.assertNotIn('聚合后的主线只提取共同判断，不代表两篇来源所有细节。',markdown)
            for card in cards:
                self.assertNotIn(card['what'],markdown)
            self.assertIn((w/'materials/article.md').read_text(encoding='utf-8'),markdown)
            self.assertIn('Evidence API v2.',markdown)

    def test_legacy_markdown_only_preserves_existing_interpretation_and_adds_article_full_text(self):
        with test_workspace() as w:
            _,_,cards=fixture(w)
            config=distill.read(w/'config.json');config['output']['formats']=['markdown'];distill.write(w/'config.json',config)
            distill.render(w)
            markdown=(w/'output/人物蒸馏.md').read_text(encoding='utf-8')
            self.assertIn('## 内容研读',markdown)
            self.assertNotIn('## 精选观点',markdown)
            self.assertIn(cards[0]['what'],markdown)
            self.assertIn((w/'materials/article.md').read_text(encoding='utf-8').strip(),markdown)
            self.assertIn('Evidence API v2.',markdown)
            self.assertIn('Do not change 1 example.',markdown)


if __name__=='__main__':unittest.main()
