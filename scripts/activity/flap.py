"""Read-only discovery for the official Flap ID Agent Curve on BSC.

Primary ABI: official flap.sh Agent Curve artifact v20261023134909522;
Portal TokenStateV6: flap-sh/FlapVaultExample/src/flap/IPortal.sol.
All reads are delegated to the caller's fixed-block Multicall3 function.
"""
from eth_abi import encode, decode
from Crypto.Hash import keccak

FACTORY = '0xc55820f24015be7c4f18949d9e1363a3609b300e'
READER = '0x18aa6c93f1887a243fdc348c9a77f5136555174a'
PORTAL = '0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0'
ZERO = '0x'+'0'*40
WBNB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'
CARD = '(address,address,string,string,string,address,address,address,uint8,uint256,uint256,uint256,uint256,uint256,uint256,uint256)'
STATE = '(uint8,uint256,uint256,uint256,uint8,uint256,uint256,uint256,uint256,address,bool,bytes32,uint256,address,uint256)'
VIRTUAL_TRADE = 'VirtualTrade(uint256,address,uint8,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256)'
FLAP_BUY = 'TokenBought(uint256,address,address,uint256,uint256,uint256,uint256)'
FLAP_SELL = 'TokenSold(uint256,address,address,uint256,uint256,uint256,uint256)'

def signature(text):
    return keccak.new(digest_bits=256,data=text.encode()).digest()

def call(address, method, types=(), args=()):
    return address, signature(method)[:4]+encode(types,args)

def agent_fill(log):
    ns,_,owner,_,quote,shares=decode(['bytes32','uint256','address','address','uint256','uint256'],bytes.fromhex(log['data'][2:]))
    ns=ns.rstrip(b'\0')
    if ns not in (b'virtualBuyFill',b'virtualSellFill'):return None
    return {'owner':owner.lower(),'buy':ns==b'virtualBuyFill','amount':shares,'quote':quote}

def portal_fill(log, token):
    if log['address'].lower()!=PORTAL or not log['topics']:return None
    buy=log['topics'][0]=='0x'+signature(FLAP_BUY).hex()
    if not buy and log['topics'][0]!='0x'+signature(FLAP_SELL).hex():return None
    _,actual,owner,amount,quote,_,_=decode(['uint256','address','address','uint256','uint256','uint256','uint256'],bytes.fromhex(log['data'][2:]))
    if actual.lower()!=token.lower():return None
    return {'owner':owner.lower(),'buy':buy,'amount':amount,'quote':quote}

def discover(multicall, block):
    factory, portal, count = multicall([call(READER,'factory()'),call(FACTORY,'flapPortal()'),call(FACTORY,'marketCount()')])
    assert decode(['address'],factory)[0].lower()==FACTORY, 'Flap Reader factory mismatch'
    assert decode(['address'],portal)[0].lower()==PORTAL, 'Flap factory Portal mismatch'
    count=decode(['uint256'],count)[0]
    assert count<=25000, 'Flap market inventory exceeds safe discovery bound'
    markets=[]
    for start in range(0,count,100):
        markets.extend(decode(['address'],value)[0].lower() for value in multicall([call(FACTORY,'markets(uint256)',['uint256'],[i]) for i in range(start,min(start+100,count))]))
    assert len(markets)==len(set(markets)) and ZERO not in markets, 'Invalid factory market inventory'
    launched=[]
    for start in range(0,len(markets),40):
        chunk=markets[start:start+40]
        values=multicall([call(market,method) for market in chunk for method in ('phase()','token()')])
        for i,market in enumerate(chunk):
            phase=decode(['uint8'],values[i*2])[0]
            token=decode(['address'],values[i*2+1])[0].lower()
            assert phase in (1,2,3), 'Unknown Flap Agent Curve phase'
            if phase==3:
                assert token!=ZERO, 'Launched market has no actual token'
                launched.append((market,token))
    rows=[]
    for start in range(0,len(launched),20):
        batch=launched[start:start+20]
        calls=[]
        for r in batch:
            market,token=r
            calls.extend([call(FACTORY,'isMarket(address)',['address'],[market]),call(FACTORY,'marketOfToken(address)',['address'],[token]),call(market,'token()'),call(PORTAL,'getTokenV6(address)',['address'],[token]),call(token,'symbol()'),call(token,'decimals()'),call(token,'name()')])
        values=multicall(calls)
        for i,r in enumerate(batch):
            ok,registered,actual,state,symbol,decimals,name=values[i*7:i*7+7]
            market,token=r
            assert decode(['bool'],ok)[0] and decode(['address'],registered)[0].lower()==market and decode(['address'],actual)[0].lower()==token, 'Flap market provenance mismatch'
            state=decode([STATE],state)[0]
            assert state[0] in (1,4), 'Flap Portal token state mismatch'
            pool=state[13].lower()
            if state[0]==4:assert pool!=ZERO, 'DEX token has no canonical pool'
            rows.append({'address':token,'market':market,'name':decode(['string'],name)[0],'symbol':decode(['string'],symbol)[0],'decimals':decode(['uint8'],decimals)[0],'quoteToken':state[9].lower(),'phase':3,'portalStatus':state[0],'pool':pool,'eligible':state[0]==4,'block':block,'protocol':'flap-id-agent-curve'})
    assert len({r['address'] for r in rows})==len(rows), 'Duplicate Flap launched token'
    return {'factory':FACTORY,'reader':READER,'portal':PORTAL,'snapshotBlock':block,'marketCount':count,'launchedCount':len(rows),'eligibleCount':sum(r['eligible'] for r in rows),'tokens':rows,'rule':'factory membership + actual token + Agent Curve phase 3 + Portal status DEX (4) + canonical pool; Graduated alone is insufficient'}
