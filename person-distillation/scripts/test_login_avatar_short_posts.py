import unittest
from access_state import assess
from publication_review import differences,valid_review
from test_background_publication_review import source,row
from test_pipeline import ROOT
from distill import read
from validate_reader import validate

def channel(platform,**kw):
    return {'platform':platform,'needed':['text'],'preparation_probe_completed':True,
            'preparation_probe_evidence':['synthetic login wall'],
            'capabilities':{'text':{'status':'login_required','evidence':['synthetic gate']}},**kw}
def access(*channels):return {'inventory_reviewed':True,'inventory_evidence':['synthetic inventory'],'channels':list(channels)}

class LoginAvatarShortPosts(unittest.TestCase):
    def test_login_batch_offers_all_skip_or_some_and_filters_minor_platforms(self):
        result=assess(access(channel('B站'),channel('公众号'),channel('Instagram'),channel('即刻')))
        prompt=result['manual_batch']['interaction']
        self.assertEqual(prompt['platforms'],['B站','公众号'])
        self.assertEqual(prompt['options'],['login_all','skip_all','select_platforms'])
        self.assertEqual(len(result['coverage_gaps']),2)
        self.assertEqual(result['human_window'],'awaiting_user')

    def test_minor_login_does_not_block_but_explicit_request_does(self):
        self.assertEqual(assess(access(channel('Instagram')))['human_window'],'closed')
        r=assess(access(channel('Instagram',necessity='explicit')))
        self.assertEqual(r['manual_batch']['interaction']['platforms'],['Instagram'])

    def test_minor_public_content_remains_usable(self):
        c=channel('Instagram',capabilities={'text':{'status':'ready_public','evidence':['synthetic public body'],'observed_at':'synthetic now'}})
        r=assess(access(c))
        self.assertTrue(r['formal_collection_ready'])
        self.assertEqual(len(r['allowed_operations']),1)

    def test_skip_all_closes_window_without_claiming_sources_ready(self):
        channels=[channel(p,decision='exclude_by_user',decision_by='user',decision_evidence=['Synthetic explicit skip all']) for p in ('B站','公众号')]
        r=assess(access(*channels))
        self.assertEqual(r['human_window'],'closed')
        self.assertFalse(r['ready_capabilities'])
        self.assertFalse(r['user_actions'])

    def test_skip_is_actual_user_choice_not_assumed_login(self):
        b=channel('B站',decision='exclude_by_user',decision_by='user',decision_evidence=['User selected skip Bilibili'])
        r=assess(access(b,channel('公众号')))
        self.assertEqual(r['manual_batch']['interaction']['platforms'],['公众号'])
        self.assertFalse(r['ready_capabilities'])
        b.pop('decision_evidence')
        self.assertNotEqual(assess(access(b))['human_window'],'closed')

    def test_unfinished_inventory_does_not_show_dialog(self):
        r=assess({'channels':[channel('B站')]})
        self.assertIsNone(r['manual_batch']['interaction'])

    def test_avatar_uid_must_match_subject_not_logged_in_viewer(self):
        data=read(ROOT/'assets/reader.example.json')
        data['profile']['accounts']=[{'label':'B站','url':'https://space.bilibili.com/12345'}]
        data['profile']['avatar']={'path':'example-avatar.png','caption':'Synthetic author image',
            'account_url':'https://space.bilibili.com/99999','platform':'B站','observed_at':'synthetic',
            'selection_reason':'Synthetic author card'}
        self.assertIn('Subject avatar Bilibili UID differs from verified subject accounts',validate(data,ROOT/'assets'))
        data['profile']['avatar']['account_url']='https://space.bilibili.com/12345/upload/video'
        self.assertNotIn('Subject avatar Bilibili UID differs from verified subject accounts',validate(data,ROOT/'assets'))

    def test_500_boundary_full_short_and_located_user_exception(self):
        for count in (1,300,500,501):
            original='甲'*count
            unchanged={'source':source(original)['items'][0],'published':source(original)['items'][0]}
            self.assertTrue(valid_review(unchanged,row('full')))
            review=row('excerpt');review.update(excerpt_basis='long_source',excerpt_detail='Synthetic long text',meaning_preserved='Synthetic main claim',omissions='Synthetic omitted detail')
            change=differences(source(original),source('甲'))['a'] if count>1 else {'source':source(original)['items'][0],'published':source(original)['items'][0]}
            self.assertEqual(valid_review(change,review),count>500)
            review['excerpt_basis']='user_request';review['excerpt_detail']='Synthetic explicit quote request'
            self.assertTrue(valid_review(change,review))

    def test_aggregate_long_source_cannot_excuse_short_source_truncation(self):
        original=source('甲'*600);original['items'][0]['documents']+=source('短帖完整结论。')['items'][0]['documents']
        published=source('甲'*550)
        review=row('excerpt');review.update(excerpt_basis='long_source',excerpt_detail='Synthetic',meaning_preserved='Synthetic',omissions='Synthetic')
        self.assertFalse(valid_review(differences(original,published)['a'],review))

if __name__=='__main__':unittest.main()
