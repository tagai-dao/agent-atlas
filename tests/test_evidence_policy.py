import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('policy',Path(__file__).resolve().parents[1]/'scripts/evidence_policy.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class EvidencePolicyTests(unittest.TestCase):
 def setUp(self):
  self.e={'name':'alice.ai','xHandle':'Alice','sourceUrl':'https://x.com/Alice/status/12345','extractionMethods':['image_ocr'],'status':'candidate'}
  self.c={'12345':{'authorId':'1','postId':'12345','xHandle':'Alice','displayName':'Alice','text':'My Agent ID is alice.ai','source':'cached.json','media':[{'type':'photo','url':'https://pbs.twimg.com/media/a.jpg','ocrComplete':True,'names':['alice.ai'],'identityCard':True}]}}
 def test_single_own_card_is_strongest_without_changing_review(self):
  self.assertEqual(p.classify(self.e,self.c)['associationReasons'],['own_single_identity_image']);self.assertEqual(self.e['status'],'candidate')
 def test_multi_identity_image_excluded_even_with_review(self):
  self.c['12345']['media'][0]['names']=['alice.ai','bob.ai'];self.e['status']='self_declared'
  self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'excluded')
 def test_independent_text_survives_bad_image_as_weak(self):
  self.c['12345']['media'][0]['names']=['alice.ai','bob.ai'];self.e['extractionMethods'].append('text')
  self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_display_name_overrides_bad_image_but_not_bad_author(self):
  self.c['12345']['displayName']='Alice（alice.ai）';self.c['12345']['media'][0]['names']=['alice.ai','bob.ai']
  self.assertEqual(p.classify(self.e,self.c)['associationReasons'],['author_display_name'])
  self.e['xHandle']='Bob';self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_display_names_are_exact_not_substrings_or_body_brackets(self):
  for display in ['Alice (alice.ai)','Alice（ALICE.ai）','Alice · alice.ai']:
   self.c['12345']['displayName']=display;self.c['12345']['media']=[];self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'strongest')
  for display in ['Alice (malice.ai)','alice_ai','Alice (alice.ai bob.ai)']:
   self.c['12345']['displayName']=display;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_missing_ocr_or_many_images_cannot_be_strongest(self):
  self.c['12345']['media'][0]['ocrComplete']=False;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
  self.c['12345']['media'][0]['ocrComplete']=True;self.c['12345']['media']*=2;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_quote_link_high_confidence_or_repost_cannot_promote(self):
  self.e.update(extractionMethods=['binance_share_link'],sourceConfidence='high');self.assertEqual(p.classify(self.e,{})['associationStrength'],'weak')
  self.c['12345']['repost']=True;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_raw_ocr_exclusion_even_when_source_has_only_one_mapping(self):
  self.c['12345']['media'][0]['names']=['alice.ai','hidden.ai'];self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'excluded')
 def test_display_name_rows_discovered_once_per_author_identity(self):
  self.c['12345']['displayName']='Alice (alice.ai)';rows=p.profile_mappings(self.c,[]);self.assertEqual(rows[0]['agentId'],'alice.ai');self.assertEqual(p.profile_mappings(self.c,rows),[])

if __name__=='__main__':unittest.main()
