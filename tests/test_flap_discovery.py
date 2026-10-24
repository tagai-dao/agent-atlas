import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/activity'))
from eth_abi import decode,encode
from flap import FACTORY,PORTAL,READER,ZERO,STATE,discover,signature,agent_fill,portal_fill,FLAP_BUY

def addr(n):return '0x'+f'{n:040x}'
class DiscoveryTests(unittest.TestCase):
    def mock(self, *, bad_factory=False, forged=False, missing_pool=False, fail=False):
        markets=[addr(1),addr(2),addr(3)]
        tokens=[addr(11),addr(12),ZERO]
        def read(calls):
            output=[]
            for target,data in calls:
                sel=data[:4]
                def method(name):return sel==signature(name)[:4]
                if method('factory()'):types,value=['address'],[addr(99) if bad_factory else FACTORY]
                elif method('flapPortal()'):types,value=['address'],[PORTAL]
                elif method('marketCount()'):types,value=['uint256'],[len(markets)]
                elif method('markets(uint256)'):types,value=['address'],[markets[decode(['uint256'],data[4:])[0]]]
                elif method('phase()'):types,value=['uint8'],[2 if target==markets[2] else 3]
                elif method('token()'):types,value=['address'],[tokens[markets.index(target)]]
                elif method('isMarket(address)'):types,value=['bool'],[True]
                elif method('marketOfToken(address)'):
                    token=decode(['address'],data[4:])[0];types,value=['address'],[ZERO if forged else markets[tokens.index(token)]]
                elif method('getTokenV6(address)'):
                    if fail:raise RuntimeError('RPC unavailable')
                    token=decode(['address'],data[4:])[0];listed=token==tokens[0]
                    types,value=[STATE],[(4 if listed else 1,0,0,0,6,0,0,0,0,ZERO,False,bytes(32),100,addr(55) if listed and not missing_pool else ZERO,10**18)]
                elif method('symbol()'):types,value=['string'],['.ai']
                elif method('name()'):types,value=['string'],['Same name']
                elif method('decimals()'):types,value=['uint8'],[18]
                else:raise AssertionError('Unexpected read')
                output.append(encode(types,value))
            return output
        return read
    def test_graduated_does_not_imply_dex(self):
        r=discover(self.mock(),123)
        self.assertEqual(r['marketCount'],3);self.assertEqual(r['launchedCount'],2);self.assertEqual(r['eligibleCount'],1)
        self.assertEqual([x['portalStatus'] for x in r['tokens']],[4,1]);self.assertEqual(r['snapshotBlock'],123)
    def test_forged_market_token_mapping_rejected(self):
        with self.assertRaises(AssertionError):discover(self.mock(forged=True),123)
    def test_reader_factory_mismatch_rejected(self):
        with self.assertRaises(AssertionError):discover(self.mock(bad_factory=True),123)
    def test_dex_without_actual_pool_rejected(self):
        with self.assertRaises(AssertionError):discover(self.mock(missing_pool=True),123)
    def test_only_fill_namespace_counts_as_agent_trade(self):
        def log(ns):return {'data':'0x'+encode(['bytes32','uint256','address','address','uint256','uint256'],[ns.encode().ljust(32,b'\0'),1,addr(7),ZERO,100,200]).hex()}
        self.assertIsNone(agent_fill(log('virtualBuy')))
        self.assertIsNone(agent_fill(log('virtualShareClaimed')))
        self.assertTrue(agent_fill(log('virtualBuyFill'))['buy'])
        self.assertFalse(agent_fill(log('virtualSellFill'))['buy'])
    def test_portal_transfer_candidates_require_actual_matching_fill(self):
        log={'address':PORTAL,'topics':['0x'+signature(FLAP_BUY).hex()],'data':'0x'+encode(['uint256','address','address','uint256','uint256','uint256','uint256'],[1,addr(11),addr(7),200,100,1,1]).hex()}
        self.assertEqual(portal_fill(log,addr(11))['owner'],addr(7))
        self.assertIsNone(portal_fill(log,addr(12)))
        self.assertIsNone(portal_fill({**log,'topics':['0x'+signature('Transfer(address,address,uint256)').hex()]},addr(11)))
    def test_required_read_failure_propagates(self):
        with self.assertRaises(RuntimeError):discover(self.mock(fail=True),123)
if __name__=='__main__':unittest.main()
