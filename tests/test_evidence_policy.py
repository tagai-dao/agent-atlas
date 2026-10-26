import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('policy',Path(__file__).resolve().parents[1]/'scripts/evidence_policy.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class EvidencePolicyTests(unittest.TestCase):
 def setUp(self):
  self.e={'name':'alice.ai','xHandle':'Alice','sourceUrl':'https://x.com/Alice/status/12345','extractionMethods':['image_ocr'],'status':'candidate'}
  self.c={'12345':{'authorId':'1','postId':'12345','xHandle':'Alice','displayName':'Alice','text':'Alice × Binance Agent ID','source':'public-post','media':[{'type':'photo','url':'https://pbs.twimg.com/media/a.jpg','ocrComplete':True,'names':['alice.ai'],'identityCard':True}]}}
 def test_card_does_not_require_first_person_or_english_template(self):
  for text in ['Alice × Binance Agent ID','ID Agen — satu nama untuk Agen Anda','Meet alice.ai — my Agent ID','']:
   self.c['12345']['text']=text;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'strongest')
 def test_article_covers_do_not_count_as_additional_identity_cards(self):
  self.c['12345']['text']='教程：我的就是alice.ai';self.c['12345']['media']=[{'type':'photo','url':'cover','ocrComplete':True,'names':[],'identityCard':False},*self.c['12345']['media'],{'type':'photo','url':'wallet','ocrComplete':True,'names':[],'identityCard':False}]
  self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'strongest')
 def test_multi_identity_image_excluded_without_changing_review(self):
  self.c['12345']['media'][0]['names']=['alice.ai','bob.ai'];self.e['status']='self_declared';self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'excluded');self.assertEqual(self.e['status'],'self_declared')
 def test_independent_text_survives_bad_image_as_weak(self):
  self.c['12345']['media'][0]['names']=['alice.ai','bob.ai'];self.e['extractionMethods'].append('text');self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_display_name_remains_independent_of_images(self):
  self.c['12345']['displayName']='Alice（alice.ai）';self.c['12345']['media'][0]['names']=['alice.ai','bob.ai'];self.assertEqual(p.classify(self.e,self.c)['associationReasons'],['author_display_name']);self.e['xHandle']='Bob';self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_display_names_exact_not_body_brackets_or_handle_similarity(self):
  self.c['12345']['media']=[]
  for display in ['Alice (alice.ai)','Alice（ALICE.ai）','Alice · alice.ai']:
   self.c['12345']['displayName']=display;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'strongest')
  for display in ['Alice (malice.ai)','alice_ai','Alice (alice.ai bob.ai)']:
   self.c['12345']['displayName']=display;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_multiple_identity_cards_remain_ambiguous(self):
  self.c['12345']['media']*=2;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_high_confidence_or_missing_context_never_manufactures_image_proof(self):
  self.e['sourceConfidence']='high';self.assertEqual(p.classify(self.e,{})['associationStrength'],'weak');self.c['12345']['media'][0]['ocrComplete']=False;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_reposts_and_explicit_other_person_examples_are_not_own_cards(self):
  self.c['12345']['repost']=True;self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak');self.c['12345']['repost']=False;self.c['12345']['text']='一姐 @someone 分享。这里是示意alice.ai';self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'weak')
 def test_public_image_preview_can_establish_single_id_image(self):
  self.c['12345']['media'][0]['type']='animated_gif';self.assertEqual(p.classify(self.e,self.c)['associationStrength'],'strongest')
 def test_names_do_not_join_ordinary_words_and_dot_ai_badges(self):
  self.assertEqual(p.names('A core for your .ai agent. arthouse.ai'),['arthouse.ai'])
 def test_display_name_rows_discovered_once_per_author_identity(self):
  self.c['12345']['displayName']='Alice (alice.ai)';rows=p.profile_mappings(self.c,[]);self.assertEqual(rows[0]['agentId'],'alice.ai');self.assertEqual(p.profile_mappings(self.c,rows),[])
if __name__=='__main__':unittest.main()
