import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from registration_history import build_history, publish_history, REGISTRY, TRANSFER, ZONE


def event(token, before, after, block):
    return {'address': REGISTRY, 'topics': [TRANSFER, hex(before), hex(after), hex(token)],
            'blockNumber': hex(block), 'logIndex': '0x1', 'transactionHash': hex(block)}


class RegistrationHistoryTests(unittest.TestCase):
    def run_history(self, logs, directory):
        # 15:59 UTC is 23:59 in Shanghai. Blocks 2 and 6 start new local days.
        start = int(dt.datetime(2026,10,20,15,59,tzinfo=dt.timezone.utc).timestamp())
        times = {1:start, 2:start+60, 3:start+120, 4:start+3600,
                 5:start+86400, 6:start+86460, 7:start+90000,
                 8:start+172800, 9:start+172860, 10:start+176000}
        requests = []
        def rpc(method, params):
            self.assertEqual(method, 'eth_getBlockByNumber')
            n = int(params[0],16)
            self.assertLessEqual(n,10)
            requests.append(n)
            return {'number':hex(n),'timestamp':hex(times[n]),'hash':f'h{n}'}
        anchor = {'number':10,'hash':'h10','timestamp':times[10]}
        return build_history(logs,anchor,rpc,Path(directory),deploy=1), anchor, requests

    def test_first_registration_not_transfer_burn_or_remint(self):
        logs = [event(1,0,11,1), event(2,0,12,2), event(1,11,13,3),
                event(2,12,0,4), event(2,0,14,6), event(3,0,15,9)]
        with tempfile.TemporaryDirectory() as tmp:
            history,anchor,_ = self.run_history(logs,tmp)
            self.assertEqual([d['date'] for d in history['days']],['2026-10-20','2026-10-21','2026-10-22','2026-10-23'])
            self.assertEqual([d['registrations'] for d in history['days']],[1,1,0,1])
            self.assertEqual([d['cumulative'] for d in history['days']],[1,2,2,3])
            self.assertEqual(history['mintEvents'],4)
            self.assertEqual(history['repeatMints'],1)
            self.assertEqual(history['days'][1]['fromBlock'],2)
            self.assertEqual(history['days'][2]['fromBlock'],6)
            self.assertEqual([r['complete'] for r in history['days']],[True,True,True,False])
            publish_history(history,Path(tmp)/'published',anchor)
            rows=(Path(tmp)/'published/registrations.csv').read_text(encoding='utf-8-sig').splitlines()
            self.assertIn('2026-10-22,0,2,True,10',rows)

    def test_duplicate_logs_and_future_events_fail(self):
        row=event(1,0,11,1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssertionError):self.run_history([row,row],tmp)
            with self.assertRaises(AssertionError):self.run_history([event(2,0,12,11)],tmp)

    def test_resume_keeps_same_day_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            first,_,requests=self.run_history([event(1,0,11,2)],tmp)
            second,_,cached=self.run_history([event(1,0,11,2)],tmp)
            self.assertEqual(first,second)
            self.assertLess(len(cached),len(requests))

    def test_wrong_snapshot_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            history,anchor,_=self.run_history([],tmp)
            with self.assertRaises(AssertionError):publish_history(history,Path(tmp)/'public',{**anchor,'hash':'wrong'})

    def test_normalization_cannot_drop_required_history(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('holdings_normalize_trend',Path(__file__).resolve().parents[1]/'scripts/holdings/normalize.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();destination=Path(tmp)/'published';destination.mkdir()
            (destination/'registrations.json').write_text('previous verified snapshot')
            for name,value in [('snapshot-block.json',{'number':10,'hash':'h10','timestamp':1}),('complete.json',{'snapshotBlock':10,'snapshotHash':'h10','allRegisteredIds':True,'registryLogs':0,'walletCount':0,'assetCount':0}),('wallets.json',[]),('assets.json',[])]:
                (raw/name).write_text(json.dumps(value))
            with self.assertRaises(FileNotFoundError):module.publish(raw,destination)
            self.assertEqual((destination/'registrations.json').read_text(),'previous verified snapshot')


if __name__=='__main__':unittest.main()
