"""Synthetic reading-link preservation; no claim about online token validity."""
import copy,html,unittest
import distill
from source_links import xhs_note_id,source_key,link_issues,guard_update,audit
from test_contracts import fixture
from test_pipeline import test_workspace
from build_reader import build
from render_reader import render
from validate_reader import inspect_html
from test_reader_layout import ReaderTree

NOTE='0123456789abcdef01234567'
BARE='https://www.xiaohongshu.com/explore/'+NOTE
FULL=BARE+'?xsec_token=synthetic-A%2BB%3D&xsec_source=pc_user&source=webshare'


class SourceLinks(unittest.TestCase):
    def test_native_paths_and_identity_do_not_require_rewriting_the_url(self):
        nested='https://www.xiaohongshu.com/user/profile/'+'a'*24+'/'+NOTE+'?xsec_token=synthetic&xsec_source=pc_user'
        for address in (FULL,nested,'https://www.xiaohongshu.com/discovery/item/'+NOTE):
            self.assertEqual(xhs_note_id(address),NOTE)
        for address in (None,'https://www.xiaohongshu.com/user/profile/'+'a'*24,'https://xiaohongshu.com.bad.example/explore/'+NOTE):
            self.assertIsNone(xhs_note_id(address))
        self.assertEqual(source_key({'platform':'小红书','url':FULL}),source_key({'platform':'小红书','url':BARE}))

    def test_redacted_and_wrong_note_are_errors_but_bare_and_short_need_observation(self):
        s={'id':NOTE,'url':FULL,'platform':'小红书'}
        self.assertEqual(link_issues(s),[])
        self.assertEqual(link_issues({**s,'url':BARE})[0]['severity'],'warning')
        self.assertEqual(link_issues({**s,'url':'https://xhslink.com/a/synthetic'}),[])
        for bad in ({**s,'url':FULL.replace('synthetic-A%2BB%3D','REDACTED_TEMP_SIGNATURE')},{**s,'id':'f'*24}):
            with self.assertRaises(ValueError):guard_update(None,bad)
        refreshed={**s,'url':FULL.replace('synthetic-A%2BB%3D','synthetic-refreshed')}
        guard_update(s,refreshed)

    def test_ingest_rejects_parameter_loss_and_full_query_reaches_both_maps_and_reader(self):
        with test_workspace() as w:
            _,items,_=fixture(w)
            row=copy.deepcopy(items[0]);row['sources']=[{'platform':'小红书','source_id':'synthetic-author','id':NOTE,'url':FULL}]
            distill.write(w/'update.json',[row]);distill.ingest(w,w/'update.json')
            saved=(w/'.distill/catalog.json').read_bytes()
            for stripped in (BARE,FULL.replace('&xsec_source=pc_user','')):
                bad=copy.deepcopy(row);bad['sources'][0]['url']=stripped;distill.write(w/'update.json',[bad])
                with self.assertRaises(ValueError):distill.ingest(w,w/'update.json')
                self.assertEqual((w/'.distill/catalog.json').read_bytes(),saved)
            data=build(w);body=render(data,w/'output');tree=ReaderTree(body).root
            self.assertGreaterEqual(sum(a.attrs.get('href')==FULL for a in tree.descendants(tag='a')),3)
            self.assertEqual(inspect_html(data,body),[])
            broken=body.replace(html.escape(FULL,quote=True),html.escape(BARE,quote=True))
            self.assertTrue(inspect_html(data,broken))
            records=audit([{'id':'synthetic','sources':[{'platform':'小红书','url':BARE}]}])
            self.assertEqual(records[0]['code'],'reading_parameters_unconfirmed')
            self.assertNotIn('url',records[0])  # Reports do not echo access values.


if __name__=='__main__':unittest.main()
