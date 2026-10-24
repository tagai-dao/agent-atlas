"""Contract attribution regression against an isolated miniature raw snapshot."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

class NormalizationTests(unittest.TestCase):
    def test_one_pool_swap_keeps_two_tracked_same_symbol_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'scripts/activity';script.mkdir(parents=True)
            source=Path(__file__).resolve().parents[1]/'scripts/activity'
            for name in ('normalize.py','assets.py','flap.py'):shutil.copyfile(source/name,script/name)
            raw=root/'raw';raw.mkdir();(raw/'txs').mkdir();(root/'data').mkdir()
            def save(name,data):
                p=raw/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
            def address(n):return '0x'+f'{n:040x}'
            a,b,pool,owner=map(address,(1,2,3,4));tx='0x'+'a'*64;anchor={'number':123,'hash':'0x'+'b'*64,'timestamp':1}
            save('snapshot-block.json',anchor);save('refresh-complete.json',{'block':123,'hash':anchor['hash'],'walletsChecked':1})
            save('handles-source.json',{'wallets':[{'owner':owner,'handle':'tester','block':123}]});save('extra-handles-source.json',[])
            assets=[{'address':a,'symbol':'.ai','name':'First','protocol':'manual','decimals':18},{'address':b,'symbol':'.ai','name':'Second','protocol':'manual','decimals':18},{'address':'0xb8fb293b3e8e3c5fd741e34ac5810dd5dc9f2c7f','symbol':'Flaip','name':'Flaip','protocol':'manual-curve','decimals':18}]
            save('tracked-assets.json',assets);save('pool-token0.json',{pool:a});save('token-decimals.json',{a:18,b:18});save('excluded-pools.json',[])
            for name in ('relic-mints-source.json','flaip-all-events.json'):save(name,{'head':123,'complete':True,'logs':[]})
            log={'data':'0x'+''.join(f'{v:064x}' for v in (100,0,0,50)),'topics':['0x'+'c'*64],'transactionHash':tx,'blockNumber':'0x7b','logIndex':'0x1'}
            pair={'pairAddress':pool,'dexId':'pancakeswap','baseToken':{'address':a,'symbol':'.ai'},'quoteToken':{'address':b,'symbol':'.ai'}}
            for token in (a,b):save('pool-'+pool+'-'+token+'.json',{'head':123,'fromBlock':1,'complete':True,'token':token,'pool':pair,'symbol':'.ai','version':2,'logs':[log]})
            save('txs/'+tx+'.json',{'from':owner});(root/'data/registry.json').write_text('[]')
            result=subprocess.run([sys.executable,str(script/'normalize.py'),str(raw)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            rows=json.loads((root/'public/activity/wallets/00.json').read_text())[owner]
            self.assertEqual(len(rows),2);self.assertEqual(len({r['id'] for r in rows}),2)
            self.assertEqual({r['assetId']:r['direction'] for r in rows},{a:'sell',b:'buy'})
            manifest=json.loads((root/'public/activity/manifest.json').read_text())
            self.assertEqual(manifest['poolCount'],1)
            by_token={r['address']:r for r in manifest['tokens']}
            self.assertEqual(by_token[a]['external']['agentEvents'],1);self.assertEqual(by_token[b]['external']['agentEvents'],1)
            self.assertEqual(manifest['totals']['tokenTrades'],2)
            participant=json.loads((root/'public/activity/agents.json').read_text())[0]
            self.assertEqual({r['address'] for r in participant['activity']['tokens']},{a,b})
if __name__=='__main__':unittest.main()
