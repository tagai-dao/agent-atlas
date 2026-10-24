"""Increment a complete raw BSC activity snapshot, then recheck identities.

Usage: python refresh.py --source RAW_SNAPSHOT --out NEW_RAW_SNAPSHOT
Requires httpx, eth-abi and pycryptodome. No wallet or signing capability.
Raw output stays outside the repository; normalize.py produces public files.
"""
import argparse
import concurrent.futures as futures
import json
import os
from pathlib import Path
import shutil
import time

import httpx
from eth_abi import encode, decode
from Crypto.Hash import keccak
from flap import discover, FACTORY, PORTAL, ZERO, WBNB, call, FLAP_BUY, FLAP_SELL
from assets import LEGACY

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args()
src, out = args.source.resolve(), args.out.resolve()
assert src != out, 'Keep the previous complete snapshot intact'
out.mkdir(parents=True, exist_ok=True)
(out/'logs').mkdir(exist_ok=True)
(out/'txs').mkdir(exist_ok=True)
(out/'handles').mkdir(exist_ok=True)
(out/'receipts').mkdir(exist_ok=True)
client = httpx.Client(timeout=60)
rpc_url = os.environ.get('BSC_RPC_URL') or 'https://rpc-bsc.48.club'
registry = '0x60b9262456de011f7d15a54cdd8c48baaa8b022f'
multi = '0xca11bde05977b3631167028862be2a173976ca11'

def read(path): return json.loads(path.read_text())
def save(path, data):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    temp.replace(path)
def topic(signature): return '0x'+keccak.new(digest_bits=256, data=signature.encode()).hexdigest()
def rpc(method, params):
    for attempt in range(5):
        try:
            endpoint = rpc_url if os.environ.get('BSC_RPC_URL') else 'https://bsc-mainnet.public.blastapi.io' if method=='eth_call' else 'https://bsc-dataseed1.defibit.io' if method=='eth_getTransactionReceipt' else rpc_url
            response = client.post(endpoint, json={'jsonrpc':'2.0','id':1,'method':method,'params':params})
            response.raise_for_status()
            data = response.json()
            if 'error' in data: raise RuntimeError(str(data['error']))
            return data['result']
        except Exception:
            if attempt == 4: raise RuntimeError(f'{method} failed after retries') from None
            time.sleep(attempt+1)

old_block = read(src/'snapshot-block.json')
assert rpc('eth_getBlockByNumber', [hex(old_block['number']), False])['hash'] == old_block['hash'], 'Previous snapshot anchor changed'
anchor_file = out/'snapshot-block.json'
if anchor_file.exists():
    anchor = read(anchor_file)
else:
    head = int(rpc('eth_blockNumber', []), 16)-20
    block = rpc('eth_getBlockByNumber', [hex(head),False])
    anchor = {'number':head,'hash':block['hash'],'timestamp':int(block['timestamp'],16)}
    save(anchor_file, anchor)
head = anchor['number']
print({'snapshotBlock':head,'previousBlock':old_block['number']}, flush=True)
selector=bytes.fromhex(topic('aggregate3((address,bool,bytes)[])')[2:10])
def multicall(calls, optional=False):
    data='0x'+(selector+encode(['(address,bool,bytes)[]'],[[(address,optional,calldata) for address,calldata in calls]])).hex()
    result=rpc('eth_call',[{'to':multi,'data':data},hex(head)])
    results=decode(['(bool,bytes)[]'],bytes.fromhex(result[2:]))[0]
    assert len(results)==len(calls)
    if optional: return results
    assert all(ok for ok,_ in results), 'Required Multicall read failed'
    return [value for _,value in results]

def fetch_logs(spec):
    label, address, topics, lo, hi = spec
    path = out/'logs'/f'{label}-{lo}-{hi}.json'
    if path.exists(): return read(path)
    params = {'address':address,'fromBlock':hex(lo),'toBlock':hex(hi)}
    if topics is not None: params['topics'] = topics
    try:
        rows = rpc('eth_getLogs', [params])
    except RuntimeError:
        if hi-lo<64:raise
        midpoint=(lo+hi)//2
        rows=fetch_logs((label,address,topics,lo,midpoint))+fetch_logs((label,address,topics,midpoint+1,hi))
    if len(rows)>=10000 and lo<hi:
        midpoint=(lo+hi)//2
        rows=fetch_logs((label,address,topics,lo,midpoint))+fetch_logs((label,address,topics,midpoint+1,hi))
    assert all(not r.get('removed') and lo <= int(r['blockNumber'],16) <= hi for r in rows)
    save(path, rows)
    return rows

def scan(label,address,topics,start):
    with futures.ThreadPoolExecutor(max_workers=4) as executor:
        batches=executor.map(fetch_logs,[(label,address,topics,lo,min(lo+4999,head)) for lo in range(start,head+1,5000)])
        return [row for batch in batches for row in batch]

catalog=discover(multicall,head)
save(out/'flap-discovery.json',catalog)
assets={a['address']:a for a in (read(src/'tracked-assets.json') if (src/'tracked-assets.json').exists() else LEGACY)}
eligible=[a for a in catalog['tokens'] if a['eligible']]
assert all(a['address'] in {r['address'] for r in eligible} for a in assets.values() if a.get('protocol')=='flap-id-agent-curve'), 'Previously tracked Flap token disappeared from verified inventory'
quote_addresses=sorted({a['quoteToken'] for a in eligible if a['quoteToken']!=ZERO})
quote_values=multicall([call(a,method) for a in quote_addresses for method in ('symbol()','decimals()')]) if quote_addresses else []
quotes={ZERO:{'symbol':'BNB','decimals':18}}
for i,a in enumerate(quote_addresses):quotes[a]={'symbol':decode(['string'],quote_values[i*2])[0],'decimals':decode(['uint8'],quote_values[i*2+1])[0]}
for a in eligible:
    assets[a['address']]={**a,'quoteSymbol':quotes[a['quoteToken']]['symbol'],'quoteDecimals':quotes[a['quoteToken']]['decimals']}
save(out/'tracked-assets.json',list(assets.values()))
eligible=[assets[a['address']] for a in eligible]
print({'flapMarkets':catalog['marketCount'],'flapDexTokens':len(eligible)},flush=True)

# Factory creation logs anchor historical coverage to each market's creation.
factory_cached=out/'flap-factory-source.json'
factory_old=read(factory_cached) if factory_cached.exists() else read(src/'flap-factory-source.json') if (src/'flap-factory-source.json').exists() else {'head':128724650,'logs':[]}
assert factory_old['head']<=head
factory_rows=factory_old['logs']+scan('flap-factory',FACTORY,[topic('MarketCreated(address,address,address,address,bytes32)')],factory_old['head']+1)
factory_rows=list({(r['transactionHash'],r['logIndex']):r for r in factory_rows}.values())
save(out/'flap-factory-source.json',{'head':head,'complete':True,'logs':factory_rows})
births={'0x'+r['topics'][2][-40:]:int(r['blockNumber'],16) for r in factory_rows}
assert len(births)==catalog['marketCount'], 'Incomplete factory creation history'

sources = []
for file in src.glob('*.json'):
    if file.name.startswith(('inner-','pool-')) or file.name in ('relic-mints-source.json','flaip-all-events.json'):
        data = read(file)
        if not isinstance(data,dict) or 'logs' not in data: continue
        assert data['complete'] and data['head']==old_block['number'], f'Incomplete source: {file.name}'
        sources.append((file.name, data))

existing={name for name,_ in sources}
shared=topic('FlapSharedIndexerLog(bytes32,uint256,address,address,uint256,uint256)')
for a in eligible:
    assert a['market'] in births, 'Missing Flap market creation log'
    start=births[a['market']]
    for kind,address,topics in [('flap-agent',a['market'],[shared]),('flap-portal',PORTAL,[[topic(FLAP_BUY),topic(FLAP_SELL)]])]:
        name=f"inner-{kind}-{a['address']}.json"
        if name not in existing:sources.append((name,{'head':start-1,'fromBlock':start,'complete':True,'logs':[],'address':address,'token':a['address'],'symbol':a['symbol'],'format':kind,'topics':topics}))

# The Portal's canonical DEX pool is authoritative even before third-party indexing.
for a in eligible:
    if any(d.get('pool',{}).get('pairAddress','').lower()==a['pool'] and d.get('token')==a['address'] for _,d in sources):continue
    values=multicall([call(a['pool'],'token0()'),call(a['pool'],'token1()')])
    token0,token1=[decode(['address'],value)[0].lower() for value in values]
    quote=WBNB if a['quoteToken']==ZERO else a['quoteToken']
    assert {token0,token1}=={a['address'],quote}, 'Flap canonical pool token mismatch'
    probes=multicall([call(a['pool'],'getReserves()'),call(a['pool'],'slot0()')],optional=True)
    version=2 if probes[0][0] and len(probes[0][1])==96 else 3 if probes[1][0] and len(probes[1][1])>=224 else None
    assert version, 'Unsupported canonical Flap DEX pool'
    pool={'pairAddress':a['pool'],'dexId':'pancakeswap','chainId':'bsc','labels':['v'+str(version)],'baseToken':{'address':a['address'],'symbol':a['symbol']},'quoteToken':{'address':quote,'symbol':'WBNB' if a['quoteToken']==ZERO else a['quoteSymbol']}}
    sources.append((f"pool-{a['pool']}-{a['address']}.json",{'head':births[a['market']]-1,'fromBlock':births[a['market']],'complete':True,'pool':pool,'symbol':a['symbol'],'token':a['address'],'version':version,'logs':[]}))

# Refresh pool discovery, retaining previously discovered pools even if delisted.
pools = {d['pool']['pairAddress'].lower() for _,d in sources if 'pool' in d}
tokens = {d['token']: d['symbol'] for _,d in sources if 'pool' in d}
discovery = []
excluded = []
for token,symbol in tokens.items():
    response = client.get(f'https://api.dexscreener.com/token-pairs/v1/bsc/{token}')
    response.raise_for_status()
    rows = response.json()
    assert isinstance(rows,list)
    discovery.extend(rows)
    for pool in rows:
        address = pool['pairAddress'].lower()
        if any(d.get('pool',{}).get('pairAddress','').lower()==address and d.get('token','').lower()==token.lower() for _,d in sources):continue
        if pool['chainId']!='bsc' or pool['dexId'] not in ('pancakeswap','uniswap'):
            excluded.append({'address':address,'dex':pool['dexId'],'reason':'unsupported pool event format'})
            continue
        labels = pool.get('labels',[])
        if 'v2' in labels: version=2
        elif 'v3' in labels: version=3
        else:
            probes=multicall([(address,bytes.fromhex('0902f1ac')),(address,bytes.fromhex('3850c7bd'))],optional=True)
            if probes[0][0] and len(probes[0][1])==96: version=2
            elif probes[1][0] and len(probes[1][1])>=224: version=3
            else: raise RuntimeError(f'Unrecognized new pool version: {address}')
        # Scan from the registry launch; no reliance on approximate creation timestamps.
        start=births[assets[token.lower()]['market']] if assets[token.lower()].get('protocol')=='flap-id-agent-curve' else 128724651
        data = {'head':start-1,'fromBlock':start,'complete':True,'pool':pool,'symbol':symbol,'token':token,'version':version,'logs':[]}
        sources.append((f'pool-{address}-{token.lower()}.json',data))
        pools.add(address)
save(out/'pool-discovery.json', discovery)
save(out/'excluded-pools.json', excluded)

for name,data in sources:
    destination = out/name
    # Backfill Pancake V3's extended Swap ABI; older snapshots queried only
    # the Uniswap V3 topic and therefore missed these events entirely.
    backfill_v3 = 'pool' in data and data['version']==3 and not data.get('v3TopicBackfill')
    if backfill_v3:
        data={**data,'head':data['fromBlock']-1,'logs':[]}
    if destination.exists() and (not backfill_v3 or read(destination).get('v3TopicBackfill')):
        assert read(destination)['head']==head
        continue
    if 'pool' in data:
        address=data['pool']['pairAddress']
        topics=[topic('Swap(address,uint256,uint256,uint256,uint256,address)')] if data['version']==2 else [[topic('Swap(address,address,int256,int256,uint160,uint128,int24)'),topic('Swap(address,address,int256,int256,uint160,uint128,int24,uint128,uint128)')]]
    elif name=='relic-mints-source.json':
        address='0xb0d5f3108af164f5f7046f53ab59fd2779812d10';topics=[[topic('Minted(address,bytes32,uint8,uint256)'),topic('MintedWithBnb(address,bytes32,uint8,uint256)')]]
    else: address=data['address'];topics=data.get('topics')
    tasks=[(name+('-v3-backfill' if backfill_v3 else ''),address,topics,lo,min(lo+4999,head)) for lo in range(data['head']+1,head+1,5000)]
    rows=list(data['logs'])
    if data.get('format')=='flap-portal':
        # Transfers only identify candidate receipts. Only actual Portal fill
        # events are emitted into the ledger; claims/transfers are not trades.
        transfer=topic('Transfer(address,address,uint256)');portal_topic='0x'+PORTAL[2:].zfill(64)
        candidates=scan(name+'-from',data['token'],[transfer,portal_topic],data['head']+1)+scan(name+'-to',data['token'],[transfer,None,portal_topic],data['head']+1)
        hashes=sorted({r['transactionHash'] for r in candidates})
        def receipt(txhash):
            path=out/'receipts'/(txhash+'.json');previous=src/'receipts'/(txhash+'.json')
            if not path.exists() and previous.exists():shutil.copyfile(previous,path)
            if path.exists():return read(path)
            r=rpc('eth_getTransactionReceipt',[txhash]);assert r and r.get('status')=='0x1';save(path,r);return r
        with futures.ThreadPoolExecutor(max_workers=6) as executor:
            for r in executor.map(receipt,hashes):
                asset_pools={d['pool']['pairAddress'].lower() for _,d in sources if 'pool' in d and d['token'].lower()==data['token'].lower()}
                dex=any(l['address'].lower() in asset_pools and l['topics'] and l['topics'][0] in {topic('Swap(address,uint256,uint256,uint256,uint256,address)'),topic('Swap(address,address,int256,int256,uint160,uint128,int24)'),topic('Swap(address,address,int256,int256,uint160,uint128,int24,uint128,uint128)')} for l in r['logs'])
                for l in r['logs']:
                    if not dex and l['address'].lower()==PORTAL and l['topics'] and l['topics'][0] in data['topics'][0] and '0x'+l['data'][90:130].lower()==data['token']:rows.append(l)
    else:
        with futures.ThreadPoolExecutor(max_workers=4) as executor:
            for batch in executor.map(fetch_logs,tasks): rows.extend(batch)
    rows=list({(r['transactionHash'],r['logIndex']):r for r in rows}.values())
    rows.sort(key=lambda r:(int(r['blockNumber'],16),int(r['logIndex'],16)))
    data={**data,'head':head,'logs':rows}
    if backfill_v3:data['v3TopicBackfill']=True
    # Never persist a credential-bearing RPC URL.
    data.pop('rpc',None)
    save(destination,data)
    print({'source':name,'events':len(rows)},flush=True)

# Fetch transaction senders (not contract calls); immutable caches may be reused.
hashes={r['transactionHash'] for name,d in sources if 'pool' in d for r in read(out/name)['logs']}
pending=[]
for txhash in hashes:
    previous=src/'txs'/(txhash+'.json');destination=out/'txs'/(txhash+'.json')
    if not destination.exists() and previous.exists():
        if read(previous).get('from'): shutil.copyfile(previous,destination)
    if not destination.exists(): pending.append(txhash)
print({'transactionSendersRequired':len(pending)},flush=True)
def fetch_tx(chunk):
    # JSON-RPC batching is used only for transaction retrieval, never eth_call.
    missing=set(chunk)
    for attempt in range(5):
        try:
            endpoint=rpc_url if os.environ.get('BSC_RPC_URL') else 'https://bsc-dataseed1.defibit.io'
            response=client.post(endpoint,json=[{'jsonrpc':'2.0','id':h,'method':'eth_getTransactionByHash','params':[h]} for h in missing])
            response.raise_for_status()
            results=response.json()
            assert isinstance(results,list)
            for row in results:
                transaction=row.get('result');txhash=row.get('id')
                if txhash not in missing or not transaction or not transaction.get('from'): continue
                save(out/'txs'/(txhash+'.json'),{'from':transaction['from'].lower(),'to':(transaction.get('to') or '').lower(),'block':int(transaction['blockNumber'],16)})
                missing.remove(txhash)
            if not missing:return
        except Exception: pass
        time.sleep(attempt+1)
    raise RuntimeError(f'Missing transaction senders: {len(missing)}')
with futures.ThreadPoolExecutor(max_workers=4) as executor:
    chunks=[pending[i:i+50] for i in range(0,len(pending),50)]
    for i,_ in enumerate(executor.map(fetch_tx,chunks)):
        if i%20==0: print({'transactionBatches':i,'total':len(chunks)},flush=True)

addresses=set()
for name,_ in sources:
    data=read(out/name)
    if 'pool' in data: continue
    index=2 if data.get('format')=='manager' else 1
    if data.get('format') in ('flap-agent','flap-portal'):
        for r in data['logs']:
            words=[r['data'][i:i+64] for i in range(2,len(r['data']),64)]
            if data['format']=='flap-agent' and bytes.fromhex(words[0]).rstrip(b'\0') not in (b'virtualBuyFill',b'virtualSellFill'):continue
            addresses.add('0x'+words[2][-40:].lower())
    else:addresses.update('0x'+r['topics'][index][-40:].lower() for r in data['logs'])
addresses.update(read(out/'txs'/(h+'.json'))['from'] for h in hashes)
addresses=sorted(addresses)
def handles(chunk):
    cache=out/'handles'/(str(head)+'-'+topic(''.join(chunk))[2:]+'.json')
    if cache.exists():
        rows=read(cache)
        assert [r['owner'] for r in rows]==chunk and all(r['block']==head for r in rows)
        return rows
    results=multicall([(registry,bytes.fromhex('c50a1514'+a[2:].zfill(64))) for a in chunk])
    rows=[{'owner':a,'handle':decode(['string'],value)[0],'block':head} for a,value in zip(chunk,results)]
    save(cache,rows)
    return rows
wallets=[]
with futures.ThreadPoolExecutor(max_workers=4) as executor:
    chunks=[addresses[i:i+150] for i in range(0,len(addresses),150)]
    for i,rows in enumerate(executor.map(handles,chunks)):
        wallets.extend(rows)
        if i%25==0:print({'handleBatches':i,'total':len(chunks)},flush=True)
save(out/'handles-source.json',{'head':head,'total':len(wallets),'wallets':wallets})
save(out/'extra-handles-source.json',[])
pool_addresses=sorted(pools)
values=multicall([(a,bytes.fromhex(selector)) for a in pool_addresses for selector in ('0dfe1681','d21220a7')])
verified_pools={a:(decode(['address'],values[i*2])[0].lower(),decode(['address'],values[i*2+1])[0].lower()) for i,a in enumerate(pool_addresses)}
for _,d in sources:
    if 'pool' in d:
        p=d['pool'];assert set(verified_pools[p['pairAddress'].lower()])=={p['baseToken']['address'].lower(),p['quoteToken']['address'].lower()}, 'Pool token metadata mismatch'
save(out/'pool-token0.json',{a:pair[0] for a,pair in verified_pools.items()})
token_addresses=sorted({d['token'].lower() for _,d in sources if 'pool' in d}|{p[k]['address'].lower() for p in discovery for k in ('baseToken','quoteToken')})
decimals=multicall([(a,bytes.fromhex('313ce567')) for a in token_addresses])
save(out/'token-decimals.json',{a:decode(['uint8'],v)[0] for a,v in zip(token_addresses,decimals)})
assert rpc('eth_getBlockByNumber',[hex(head),False])['hash']==anchor['hash'], 'Snapshot reorganization detected'
save(out/'refresh-complete.json',{'block':head,'hash':anchor['hash'],'walletsChecked':len(wallets),'poolCount':len(pools)})
print({'complete':True,'block':head,'walletsChecked':len(wallets),'registered':sum(bool(w['handle']) for w in wallets)},flush=True)
