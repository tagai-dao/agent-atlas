import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from eth_abi import encode,decode

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
r=module('holdings_refresh','scripts/holdings/refresh.py')
n=module('holdings_normalize','scripts/holdings/normalize.py')
def address(i):return '0x'+f'{i:040x}'
def transfer(token,before,after,block):
    return {'address':r.REGISTRY,'topics':[r.TRANSFER,'0x'+before[2:].zfill(64),'0x'+after[2:].zfill(64),'0x'+f'{token:064x}'],'blockNumber':hex(block),'logIndex':'0x1','transactionHash':'0x'+f'{block:064x}'}
class HoldingsTests(unittest.TestCase):
    def test_transfers_and_burns_use_current_owner(self):
        logs=[transfer(1,r.ZERO,address(1),1),transfer(2,r.ZERO,address(2),2),transfer(1,address(1),address(3),3),transfer(2,address(2),r.ZERO,4)]
        self.assertEqual(r.registry_owners(logs),{'0x'+f'{1:064x}':address(3)})
    def test_missing_mint_and_duplicate_logs_rejected(self):
        with self.assertRaises(AssertionError):r.registry_owners([transfer(1,address(1),address(2),1)])
        log=transfer(1,r.ZERO,address(1),1)
        with self.assertRaises(AssertionError):r.registry_owners([log,log])
    def test_multiple_current_ids_require_explicit_handling(self):
        with self.assertRaises(AssertionError):r.registry_owners([transfer(1,r.ZERO,address(1),1),transfer(2,r.ZERO,address(1),2)])
    def test_required_multicall_failure_is_not_zero(self):
        snapshot=r.Snapshot.__new__(r.Snapshot);snapshot.block=123
        def rpc(method,params):
            self.assertEqual(method,'eth_call');self.assertEqual(params[0]['to'],r.MULTI);self.assertEqual(params[1],'0x7b')
            calls=decode(['(address,bool,bytes)[]'],bytes.fromhex(params[0]['data'][10:]))[0]
            self.assertFalse(calls[0][1])
            return '0x'+encode(['(bool,bytes)[]'],[[(False,b'')]]).hex()
        snapshot.rpc=rpc
        with self.assertRaises(AssertionError):snapshot.multi([r.call(address(1),'balanceOf(address)',['address'],[address(2)])])
    def test_resume_reuses_subchunks_without_reordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=r.Snapshot.__new__(r.Snapshot);snapshot.block=123;snapshot.out=Path(tmp)
            calls=[r.call(address(1),'balanceOf(address)',['address'],[address(i)]) for i in range(1200)]
            queries=[]
            def multi(chunk):
                queries.append(len(chunk))
                return [encode(['uint256'],[int.from_bytes(data[-32:],'big')]) for _,data in chunk]
            snapshot.multi=multi
            snapshot.cached_multi('balances',calls[:500])
            result=snapshot.cached_multi('balances',calls)
            self.assertEqual(queries,[500,700])
            self.assertEqual([decode(['uint256'],v)[0] for v in result],list(range(1200)))
            self.assertEqual(snapshot.cached_multi('balances',calls),result)
            self.assertEqual(queries,[500,700])
    def test_precision_zero_and_same_symbols_stay_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();out=Path(tmp)/'public'
            def save(name,value):(raw/name).write_text(json.dumps(value))
            save('snapshot-block.json',{'number':42,'hash':'0xabc','timestamp':1792800000})
            save('complete.json',{'snapshotBlock':42,'snapshotHash':'0xabc','walletCount':2,'assetCount':3,'allRegisteredIds':True})
            assets=[{'address':address(i),'symbol':'.ai' if i<3 else 'Relic','name':'Asset','kind':'erc20' if i<3 else 'erc721','decimals':18 if i<3 else 0,'totalSupplyRaw':'100000000000000000000'} for i in [1,2,3]]
            save('assets.json',assets)
            save('wallets.json',[{'owner':address(4),'name':'four.ai','bnbRaw':'1000000000000000001','balances':{address(1):'900719925474099312345',address(3):'2'}},{'owner':address(5),'name':'five.ai','bnbRaw':'0','balances':{address(2):'1'}}])
            manifest=n.publish(raw,out)
            self.assertEqual(manifest['walletCount'],2)
            self.assertEqual(manifest['assets'][1]['holders'],1)
            self.assertEqual(manifest['assets'][1]['totalAmount'],'900.719925474099312345')
            shard=json.loads((out/'wallets/00.json').read_text())
            self.assertEqual(shard['snapshotBlock'],42)
            wallet=shard['wallets'][address(4)]
            self.assertEqual(next(b['amount'] for b in wallet['balances'] if b['assetId']=='native'),'1.000000000000000001')
            self.assertNotIn(address(2),[b['assetId'] for b in wallet['balances']])
            self.assertEqual(manifest['assets'][-1]['totalAmount'],'2')
            self.assertEqual(json.loads((out/'holders/native/1.json').read_text())['total'],2)
            self.assertEqual(manifest['assetCoverage'],'tracked-contracts')

if __name__=='__main__':unittest.main()
