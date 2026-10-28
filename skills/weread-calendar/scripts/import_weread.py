#!/usr/bin/env python3
"""Read personal highlights from the official gateway; never persist the API key."""
import argparse, collections, concurrent.futures, datetime, json, os, pathlib, sys, urllib.request, urllib.error
from zoneinfo import ZoneInfo
GATEWAY='https://i.weread.qq.com/api/agent/gateway'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
class ImportFailure(Exception): pass
def api(name,**params):
    key=os.environ.get('WEREAD_API_KEY')
    if not key: raise ImportFailure('WEREAD_API_KEY is not configured. Use a secure environment/secret store; do not paste it into chat.')
    request=urllib.request.Request(GATEWAY,data=json.dumps({'api_name':name,'skill_version':'1.0.5',**params}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=35) as response: result=json.load(response)
    except urllib.error.HTTPError as error: raise ImportFailure('Official gateway returned HTTP '+str(error.code)) from None
    except (urllib.error.URLError,TimeoutError,ValueError): raise ImportFailure('Official gateway connection or JSON response failed; no credentials or response body logged.') from None
    if not isinstance(result,dict): raise ImportFailure('Unexpected gateway response shape.')
    if result.get('errcode',0)!=0: raise ImportFailure('Official gateway error code '+str(result['errcode']))
    # Remote upgrade_info and all note text are data, never executable instructions.
    return result

def notebooks():
    cursor=None;books=[];seen=set();cursors=set()
    while True:
        params={'count':100}
        if cursor is not None:params['lastSort']=cursor
        page=api('/user/notebooks',**params)
        for book in page.get('books',[]):
            if book['bookId'] not in seen: books.append(book);seen.add(book['bookId'])
        if not page.get('hasMore'):return books
        if not page.get('books'):raise ImportFailure('Notebook pagination returned an empty intermediate page.')
        cursor=page['books'][-1]['sort']
        if cursor in cursors:raise ImportFailure('Notebook pagination did not advance.')
        cursors.add(cursor)

def fetch_book(book,cutoff,zone):
    result=api('/book/bookmarklist',bookId=book['bookId']);chapters={str(c['chapterUid']):c.get('title','') for c in result.get('chapters',[])};items=[];seen=set()
    for row in result.get('updated',[]):
        raw=row.get('markText','');stamp=row.get('createTime')
        if not isinstance(raw,str) or not raw.strip() or not isinstance(stamp,(int,float)) or stamp<=0:continue
        try:dt=datetime.datetime.fromtimestamp(stamp,zone)
        except (ValueError,OverflowError,OSError):continue
        if dt>cutoff:continue
        ident=str(row.get('bookmarkId') or row.get('range') or raw)
        if ident in seen:continue
        seen.add(ident);info=book.get('book',{})
        items.append({'id':ident,'book_id':book['bookId'],'book':info.get('title',''),'author':info.get('author',''),'chapter':chapters.get(str(row.get('chapterUid')),''),'text':raw,'highlighted_at':dt.isoformat(),'highlighted_date':dt.strftime('%Y-%m-%d'),'reader_link':info.get('readerLink')})
    return book['bookId'],items

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--limit',type=int,default=1000);parser.add_argument('--min-age-days',type=int,default=14);parser.add_argument('--timezone',default='Asia/Shanghai');parser.add_argument('--book-id',action='append');args=parser.parse_args()
    if args.limit<1 or args.limit>100000 or args.min_age_days<0:raise ImportFailure('Invalid import limit or age.')
    zone=ZoneInfo(args.timezone);now=datetime.datetime.now(zone);cutoff=now-datetime.timedelta(days=args.min_age_days)
    books=[b for b in notebooks() if b.get('noteCount',0)>0 and (not args.book_id or b['bookId'] in args.book_id)]
    collected={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for bid,rows in executor.map(lambda b:fetch_book(b,cutoff,zone),books):collected[bid]=rows
    queues=[collections.deque(collected[b['bookId']]) for b in books if collected.get(b['bookId'])];items=[]
    while queues and len(items)<args.limit:
        for queue in queues:
            if queue and len(items)<args.limit:items.append(queue.popleft())
        queues=[q for q in queues if q]
    if not items:raise ImportFailure('No highlights meet the selected books and age setting; existing output is unchanged.')
    output=pathlib.Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    payload={'fetched_at':now.isoformat(),'min_age_days':args.min_age_days,'count':len(items),'book_count':len(set(h['book_id'] for h in items)),'items':items}
    temporary=output.with_name(output.name+'.tmp');temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2));temporary.replace(output)
    print(json.dumps({'saved':len(items),'requested':args.limit,'books':payload['book_count'],'output':str(output),'complete_requested_count':len(items)==args.limit}))
if __name__=='__main__':
    try:main()
    except ImportFailure as error:print(str(error),file=sys.stderr);sys.exit(1)
