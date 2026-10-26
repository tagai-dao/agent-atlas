import sys,json,tempfile,hashlib,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from x_evidence_review import image_result, refresh_review_cache
from evidence_policy import classify
class ReviewTests(unittest.TestCase):
 def test_suffix_confusion_requires_a_card_and_repeated_headline(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'media').mkdir();url='https://pbs.twimg.com/media/test.jpg';path=root/'media'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
   for text,expected in [('AGENT ID\nONE AND ONLY\n530\n530.al\nBINANCE',['530.ai']),('AGENT ID\nONE AND ONLY\nmarkas\nmarkas.a1',['markas.ai']),('Visit company.al for details',[]),('AGENT ID\nONE AND ONLY\n530.al',[])]:
    path.write_text(json.dumps({'url':url,'sha256':'fixture','engine':'fixture','text':text}));self.assertEqual(image_result(url,root)['names'],expected)
 def test_all_four_reported_posts_have_real_strong_image_evidence(self):
  root=Path(__file__).resolve().parents[1];evidence=json.loads((root/'data/evidence.json').read_text());context=json.loads((root/'data/x-evidence-context.json').read_text())
  for pid in ['2112695850464129206','2113335171789574619','2114497209861575078','2112922107889750209']:
   e=next(e for e in evidence if e['sourceUrl'].split('/')[-1]==pid);result=classify(e,context);self.assertEqual(result['associationStrength'],'strongest',pid);self.assertIn('own_single_identity_image',result['associationReasons']);self.assertTrue(any(m.get('imageSha256') and m.get('names')==[e['name']] for m in context[pid]['media']))
 def test_missing_preview_url_is_not_a_refresh_failure(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'posts').mkdir();(root/'posts'/'12345.json').write_text(json.dumps({'id_str':'12345','user':{'id_str':'1'},'mediaDetails':[{'type':'animated_gif','media_url_https':None}]}))
   result=refresh_review_cache([{'sourceUrl':'https://x.com/Alice/status/12345'}],root,{'12345':{'media':[{'type':'animated_gif','url':None}]}});self.assertEqual(result['imagesRequested'],0)
if __name__=='__main__':unittest.main()
