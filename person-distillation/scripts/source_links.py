"""Keep public reading URLs separate from stable source identity.

No network, cookies or token generation. URL shape cannot prove readability.
"""
import re
from urllib.parse import urlsplit,parse_qs


def xhs_note_id(url):
    if not isinstance(url,str):return None
    try:p=urlsplit(url)
    except ValueError:return None
    if (p.hostname or '').lower() not in ('xiaohongshu.com','www.xiaohongshu.com'):return None
    m=re.fullmatch(r'/(?:explore|discovery/item|user/profile/[0-9a-f]{24})/([0-9a-f]{24})/?',p.path,re.I)
    return m[1].lower() if m else None


def source_key(source):
    note=xhs_note_id(source['url'])
    return ('小红书',note) if note else (source['platform'],source.get('id') or source['url'])


def link_issues(source):
    address=source.get('url','');note=xhs_note_id(address)
    if not note:return []  # Official short links and account pages need actual observation.
    issues=[];expected=source.get('id','');query=parse_qs(urlsplit(address).query,keep_blank_values=True)
    if re.fullmatch(r'[0-9a-f]{24}',str(expected),re.I) and expected.lower()!=note:
        issues.append({'code':'note_id_mismatch','severity':'error'})
    token=query.get('xsec_token',[''])[0];origin=query.get('xsec_source',[''])[0]
    if token.upper().startswith(('REDACTED','YOUR_TOKEN','<TOKEN')):
        issues.append({'code':'redacted_access_parameters','severity':'error'})
    elif not token or not origin:
        issues.append({'code':'reading_parameters_unconfirmed','severity':'warning'})
    return issues


def guard_update(previous,current):
    problems=link_issues(current)
    if any(p['severity']=='error' for p in problems):raise ValueError('Invalid Xiaohongshu reading URL: '+','.join(p['code'] for p in problems))
    if previous and xhs_note_id(previous['url']) and xhs_note_id(current['url']):
        old=parse_qs(urlsplit(previous['url']).query);new=parse_qs(urlsplit(current['url']).query)
        if any(old.get(k) and not new.get(k) for k in ('xsec_token','xsec_source')):
            raise ValueError('Xiaohongshu reading parameters would be lost; retain the observed full URL or refresh it from the native page')


def audit(items):
    return [{'item_id':i['id'],'source_id':s.get('source_id'),'note_id':xhs_note_id(s.get('url','')),**issue}
            for i in items for s in i.get('sources',[]) for issue in link_issues(s)]
