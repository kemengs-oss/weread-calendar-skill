import unittest,importlib.util,pathlib,unittest.mock as mock,datetime
p=pathlib.Path(__file__).resolve().parents[1]/'skills/weread-calendar/scripts/import_weread.py'
spec=importlib.util.spec_from_file_location('import_weread',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ImportTests(unittest.TestCase):
 def test_cursor_pagination(self):
  pages=[{'books':[{'bookId':'a','sort':9}],'hasMore':1},{'books':[{'bookId':'b','sort':8}],'hasMore':0}]
  with mock.patch.object(m,'api',side_effect=pages) as api:
   self.assertEqual([b['bookId'] for b in m.notebooks()],['a','b']);self.assertEqual(api.call_args_list[1].kwargs,{'count':100,'lastSort':9})
 def test_nonadvancing_cursor_rejected(self):
  with mock.patch.object(m,'api',return_value={'books':[{'bookId':'a','sort':9}],'hasMore':1}):
   with self.assertRaises(m.ImportFailure):m.notebooks()
 def test_missing_key_fails_without_network(self):
  with mock.patch.dict(m.os.environ,{},clear=True):
   with self.assertRaises(m.ImportFailure):m.api('/user/notebooks')
 def test_redirects_disabled(self):self.assertIsNone(m.NoRedirect().redirect_request(None,None,None,None,None,None))
 def test_age_deduplication_and_metadata(self):
  response={'updated':[{'bookmarkId':'a','markText':'演示原文。','createTime':1577836800,'chapterUid':1},{'bookmarkId':'a','markText':'重复。','createTime':1577836800},{'bookmarkId':'b','markText':'最近的文字。','createTime':1793059200}],'chapters':[{'chapterUid':1,'title':'演示章节'}]}
  with mock.patch.object(m,'api',return_value=response):bid,rows=m.fetch_book({'bookId':'book','book':{'title':'虚构书籍','author':'演示作者'}},datetime.datetime(2026,10,14,tzinfo=datetime.timezone.utc),datetime.timezone.utc)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['chapter'],'演示章节');self.assertEqual(rows[0]['book'],'虚构书籍')
if __name__=='__main__':unittest.main()
