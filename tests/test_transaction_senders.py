import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/activity'))
from transactions import fetch_senders

def hash_(i):return '0x'+f'{i:064x}'
def tx(h,block='0x5'):
    return {'hash':h,'from':'0x'+'1'*40,'to':'0x'+'2'*40,'blockNumber':block}

class SenderTests(unittest.TestCase):
    def test_unordered_responses_are_matched_by_numeric_id_and_hash(self):
        saved={}
        def post(endpoint,request):
            self.assertTrue(all(isinstance(r['id'],int) and r['method']=='eth_getTransactionByHash' for r in request))
            return [{'id':r['id'],'result':tx(r['params'][0])} for r in reversed(request)]
        fetch_senders([hash_(1),hash_(2)],10,['configured'],post,lambda h,v:saved.update({h:v}),lambda _:None)
        self.assertEqual(set(saved),{hash_(1),hash_(2)})
        self.assertEqual(saved[hash_(1)]['block'],5)
    def test_partial_results_only_retry_missing_hashes(self):
        requests=[];saved={}
        def post(endpoint,request):
            requests.append([r['params'][0] for r in request])
            return [{'id':r['id'],'result':tx(r['params'][0])} for r in request if r['params'][0]==hash_(1) or len(requests)>1]
        fetch_senders([hash_(1),hash_(2)],10,['configured'],post,lambda h,v:saved.update({h:v}),lambda _:None)
        self.assertEqual(requests,[[hash_(1),hash_(2)],[hash_(2)]])
    def test_provider_failure_falls_back_without_contract_reads(self):
        endpoints=[];saved={}
        def post(endpoint,request):
            endpoints.append(endpoint)
            if endpoint=='configured':raise RuntimeError('secret endpoint')
            return [{'id':r['id'],'result':tx(r['params'][0])} for r in request]
        fetch_senders([hash_(1)],10,['configured','public'],post,lambda h,v:saved.update({h:v}),lambda _:None)
        self.assertEqual(endpoints,['configured','configured','public']);self.assertEqual(len(saved),1)
    def test_wrong_hash_pending_or_future_block_cannot_be_cached(self):
        for result in [tx(hash_(99)),tx(hash_(1),None),tx(hash_(1),'0xff')]:
            saved={}
            with self.assertRaisesRegex(RuntimeError,'Missing transaction senders'):
                fetch_senders([hash_(1)],10,['configured'],lambda e,r:[{'id':0,'result':result}],lambda h,v:saved.update({h:v}),lambda _:None)
            self.assertFalse(saved)

if __name__=='__main__':unittest.main()
