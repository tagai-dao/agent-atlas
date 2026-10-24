"""Normalize a complete fixed-block activity snapshot into contract-keyed ledgers."""
import collections
import datetime
import json
from pathlib import Path
import re
import sys
from decimal import Decimal, getcontext
from assets import LEGACY, ALIASES
from flap import signature, agent_fill, portal_fill

getcontext().prec=90
site=Path(__file__).resolve().parents[2]
raw=Path(sys.argv[1]).expanduser().resolve()
public=site/'public/activity'
(public/'wallets').mkdir(parents=True,exist_ok=True)
load=lambda p:json.loads(p.read_text())
def write(path,value,pretty=False):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2 if pretty else None,separators=None if pretty else (',',':'))+('\n' if pretty else ''))
anchor=load(raw/'snapshot-block.json')
head=anchor['number']
complete=load(raw/'refresh-complete.json')
assert complete['block']==head and complete['hash']==anchor['hash']
handles=load(raw/'handles-source.json')['wallets']+load(raw/'extra-handles-source.json')
assert all(r['block']==head for r in handles), 'Mixed identity snapshot blocks'
known={r['owner'].lower():r for r in handles if re.fullmatch('[a-zA-Z0-9-]{3,32}',r['handle'] or '')}
assets=load(raw/'tracked-assets.json') if (raw/'tracked-assets.json').exists() else LEGACY
specs={a['address']:a for a in assets}
decimals=load(raw/'token-decimals.json') if (raw/'token-decimals.json').exists() else {}
pool0=load(raw/'pool-token0.json')
ledger=[]
stats=collections.Counter()
inner=collections.Counter()
outer=collections.Counter()
pools=[]

def dec(value,places=18):
    text=format(Decimal(value)/Decimal(10**places),'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text

def words(log):
    return [int(log['data'][i:i+64],16) for i in range(2,len(log['data']),64)]

def add(log,owner,asset,kind,venue,direction,amount,quote=None,quote_symbol=None,source='',attribution='',pool=None,stage=None,unit='token'):
    owner=owner.lower()
    if owner not in known:return
    assert Decimal(str(amount))>0, 'Non-positive fill amount'
    asset_id=asset['address']
    row={'id':f"{log['transactionHash']}:{int(log['logIndex'],16)}:{asset_id}",'kind':kind,'owner':owner,'name':known[owner]['handle'].lower()+'.ai','asset':asset['symbol'],'assetId':asset_id,'venue':venue,'direction':direction,'amount':str(amount),'tx':log['transactionHash'],'block':int(log['blockNumber'],16),'logIndex':int(log['logIndex'],16),'source':source,'attribution':attribution,'amountUnit':unit}
    if quote is not None:row.update(quoteAmount=quote,quoteSymbol=quote_symbol)
    if pool:row['pool']=pool
    if stage:row['stage']=stage
    ledger.append(row)

for file in raw.glob('*.json'):
    data=load(file)
    if isinstance(data,dict) and 'logs' in data:assert data.get('head')==head and data.get('complete'), f'Incomplete or mixed source: {file.name}'

nft=load(raw/'relic-mints-source.json')
nft_asset={'address':'0xe8c6b38b5e63377a96b268319b66638f772254bb','symbol':'Relic NFT'}
for log in nft['logs']:
    owner='0x'+log['topics'][1][-40:]
    identity=known.get(owner)
    if not identity or '0x'+signature(identity['handle']).hex()!=log['topics'][2].lower():
        stats['nft_unmatched_hash']+=1
        continue
    w=words(log)
    bnb=log['topics'][0]=='0x'+signature('MintedWithBnb(address,bytes32,uint8,uint256)').hex()
    add(log,owner,nft_asset,'nft','mint','mint',w[0],dec(w[1]),'BNB' if bnb else 'USDT','Ptah Minted / MintedWithBnb','铸造事件接收地址；名称 hash 与链上记录一致',unit='nft')

for file in raw.glob('inner-*.json'):
    data=load(file)
    asset=specs[data['token'].lower()]
    form=data['format']
    for log in data['logs']:
        w=words(log)
        quote_symbol=asset.get('quoteSymbol','BNB')
        quote_places=asset.get('quoteDecimals',18)
        unit='token'
        stage=None
        if form=='flap-agent':
            fill=agent_fill(log)
            if not fill:continue
            owner,buy,amount,quote=[fill[k] for k in ('owner','buy','amount','quote')]
            unit='shares';stage='agent-curve'
            source='Flap Agent Curve virtualBuyFill / virtualSellFill'
        elif form=='flap-portal':
            fill=portal_fill(log,asset['address'])
            assert fill, 'Invalid Portal fill source'
            owner,buy,amount,quote=[fill[k] for k in ('owner','buy','amount','quote')]
            stage='flap-curve';source='Flap Portal TokenBought / TokenSold'
        else:
            owner='0x'+log['topics'][2 if form=='manager' else 1][-40:]
            if form=='aipro':buy=bool(w[0]);amount,quote=w[1],w[2]
            elif form=='direct':buy=log['topics'][0].startswith('0x1cbc5a');amount,quote=w[0],w[1]
            elif form=='manager':buy=log['topics'][0].startswith('0x75a85');amount,quote=w[2],w[0]
            else:raise ValueError('Unknown inner fill format: '+form)
            source='BSC 曲线成交事件'
        inner[asset['address']]+=1
        add(log,owner,asset,'token','inner','buy' if buy else 'sell',dec(amount,18 if unit=='shares' else asset['decimals']),dec(quote,quote_places),quote_symbol,source,'成交事件中的交易者；份额和实际代币数量分开标注，计价为事件值',stage=stage,unit=unit)

flaip=load(raw/'flaip-all-events.json')
asset=specs[ALIASES['Flaip']]
for log in flaip['logs']:
    assert log['topics'][0] in ('0x27330bd7589580547b6437e08f9c60653de63691d2d2b2c13bff9ee67da2a68d','0xe029f26dbcf8c42dd2f352c10214a7fc26773dc62482c6241334a0402ac09a80')
    w=words(log);buy=log['topics'][0].startswith('0x27330b')
    inner[asset['address']]+=1
    add(log,'0x'+log['topics'][1][-40:],asset,'token','inner','buy' if buy else 'sell',dec(w[2] if buy else w[0]),dec(w[0] if buy else w[1]),'BNCB','Flaip Bought / Sold','曲线份额交易事件中的交易者；非普通 ERC20，报价单位 BNCB',unit='shares')

for file in raw.glob('pool-*.json'):
    data=load(file)
    if not isinstance(data,dict) or 'pool' not in data:continue
    asset=specs[data['token'].lower()]
    pool=data['pool'];address=pool['pairAddress'].lower()
    index=0 if pool0[address]==asset['address'] else 1
    quote=pool['quoteToken'] if pool['baseToken']['address'].lower()==asset['address'] else pool['baseToken']
    outer[asset['address']]+=len(data['logs'])
    pools.append({'address':address,'assetId':asset['address'],'symbol':asset['symbol'],'dex':pool['dexId'],'version':data['version'],'fromBlock':data['fromBlock'],'toBlock':data['head'],'events':len(data['logs'])})
    for log in data['logs']:
        path=raw/'txs'/(log['transactionHash']+'.json')
        tx=load(path) if path.exists() else {}
        owner=tx.get('from')
        if not owner:stats['missing_swap_transactions']+=1;continue
        if owner not in known:continue
        w=words(log)
        if data['version']==2:
            ti,to=w[index],w[index+2];oi,oo=w[1-index],w[3-index]
            if to>0 and ti==0:buy=True;amount,paid=to,oi
            elif ti>0 and to==0:buy=False;amount,paid=ti,oo
            else:stats['ambiguous_swaps']+=1;continue
        else:
            signed=[v if v<2**255 else v-2**256 for v in w[:2]]
            buy=signed[index]<0;amount,paid=abs(signed[index]),abs(signed[1-index])
            if amount==0:stats['ambiguous_swaps']+=1;continue
        add(log,owner,asset,'token','outer','buy' if buy else 'sell',dec(amount,asset['decimals']),dec(paid,decimals.get(quote['address'].lower(),18)),quote['symbol'],pool['dexId']+' V'+str(data['version'])+' Swap','交易发起地址 tx.from；不把路由器或收币地址当成交易者',address,stage='dex')
assert not stats['missing_swap_transactions'], 'Incomplete transaction sender coverage'
ledger=list({r['id']:r for r in ledger}.values())
ledger.sort(key=lambda r:(r['block'],r['logIndex'],r['assetId']),reverse=True)
bywallet=collections.defaultdict(list)
for row in ledger:bywallet[row['owner']].append(row)
agents=[]
for owner,rows in bywallet.items():
    identity=known[owner]
    tokens={}
    summary={'tokenTrades':0,'innerTrades':0,'outerTrades':0,'nftMintCount':0,'nftMintTransactions':len({r['tx'] for r in rows if r['kind']=='nft'}),'lastBlock':max(r['block'] for r in rows),'tokens':[]}
    for row in rows:
        if row['kind']=='nft':summary['nftMintCount']+=int(row['amount']);continue
        summary['tokenTrades']+=1;summary['innerTrades' if row['venue']=='inner' else 'outerTrades']+=1
        token=tokens.setdefault(row['assetId'],{'address':row['assetId'],'symbol':row['asset'],'buys':0,'sells':0,'inner':0,'outer':0,'innerBuys':0,'innerSells':0,'outerBuys':0,'outerSells':0})
        token['buys' if row['direction']=='buy' else 'sells']+=1;token[row['venue']]+=1;token[row['venue']+('Buys' if row['direction']=='buy' else 'Sells')]+=1
    summary['tokens']=list(tokens.values())
    agents.append({'name':identity['handle'].lower()+'.ai','owner':owner,'source':'BSC RPC + events','chainVerified':True,'block':head,'activity':summary})
agents.sort(key=lambda a:a['activity']['lastBlock'],reverse=True)
for prefix in [f'{i:02x}' for i in range(256)]:write(public/'wallets'/(prefix+'.json'),{a:rows for a,rows in bywallet.items() if a[2:4]==prefix})
write(public/'agents.json',agents)
feed=[]
for asset_id in [*specs,nft_asset['address']]:feed.extend([r for r in ledger if r['assetId']==asset_id][:200])
feed.sort(key=lambda r:(r['block'],r['logIndex'],r['assetId']),reverse=True)
write(public/'feed.json',feed)
nfts=[r for r in ledger if r['kind']=='nft'];trades=[r for r in ledger if r['kind']=='token']
tokens=[]
for asset in assets:
    rows=[r for r in trades if r['assetId']==asset['address']]
    token={k:asset[k] for k in ('address','symbol','name','protocol')}
    is_flap=asset['protocol']=='flap-id-agent-curve'
    token.update(status='dex' if is_flap else 'curve' if asset['symbol']=='Flaip' else 'active',internal={'status':'indexed','events':inner[asset['address']],'agentEvents':sum(r['venue']=='inner' for r in rows),'note':'Agent Curve 份额 / Flap 曲线成交；详情分别标注阶段与单位' if is_flap else 'Bought / Sold 曲线份额；计价 BNCB' if asset['symbol']=='Flaip' else '按已识别的曲线成交事件统计'},external={'status':'indexed' if any(p['assetId']==asset['address'] for p in pools) else 'not_discovered','events':outer[asset['address']],'agentEvents':sum(r['venue']=='outer' for r in rows),'note':'已核验的 V2/V3 池；按 Swap 与 tx.from 归属' if any(p['assetId']==asset['address'] for p in pools) else '未发现外部交易池，不等于零交易'},agentWallets=len({r['owner'] for r in rows}))
    if is_flap:token.update(market=asset['market'],canonicalPool=asset['pool'],portalStatus=asset['portalStatus'],discoveryBlock=asset['block'])
    tokens.append(token)
catalog=load(raw/'flap-discovery.json') if (raw/'flap-discovery.json').exists() else None
pool_count=len({p['address'] for p in pools})
manifest={'updatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'snapshotBlock':head,'snapshotHash':anchor['hash'],'identitySnapshotBlock':head,'poolCount':pool_count,'snapshotTime':datetime.datetime.fromtimestamp(anchor['timestamp'],datetime.timezone.utc).isoformat(),'chainId':56,'tokens':tokens,'nft':{'name':'Relic NFT','contract':nft_asset['address'],'game':'0xb0d5f3108af164f5f7046f53ab59fd2779812d10','publicMinted':sum(words(log)[0] for log in nft['logs']),'mintEvents':len(nft['logs']),'agentMinted':sum(int(r['amount']) for r in nfts),'agentMintEvents':len(nfts),'agentMintTransactions':len({r['tx'] for r in nfts}),'agentWallets':len({r['owner'] for r in nfts})},'totals':{'agentCount':len(agents),'tokenTrades':len(trades),'nftMinted':sum(int(r['amount']) for r in nfts),'nftMintEvents':len(nfts),'nftMintTransactions':len({r['tx'] for r in nfts})},'walletsChecked':complete['walletsChecked'],'pools':pools,'excludedPools':[p for p in load(raw/'excluded-pools.json') if p['dex']!='flapsh'],'notes':[
    f'固定区块历史快照；外盘覆盖已发现并核验的 {pool_count} 个 V2/V3 池。现有代币从注册体系上线区块扫描，自动加入的 Flap 代币从各自 Agent Curve 市场创建区块回补。',
    'Flap 自动收录条件：官方工厂确认市场归属、实际 token 一致、Agent Curve phase=3，且 Flap Portal status=DEX(4)、canonical pool 与币对均核验通过。页面 Graduated 本身不足以判定进入 DEX；尚在 Flap 曲线的代币继续等待，不冒充外盘。',
    '同名代币严格按合约地址分开统计与筛选。内盘包括 Agent Curve 份额成交及可核验的后续 Flap 曲线成交，分别标注阶段；份额不是已领取的实际 ERC20 数量。Claim / 普通 Transfer 不是成交。',
    'Flap Portal 的 TokenBought / TokenSold 从转账候选交易的真实回执核验；已通过 DEX 执行的路由交易只计池 Swap，避免重复计数。聚合多段操作仍可能遗漏个别曲线成交。',
    '交易按当前链上 handleOf(address) 归属回溯，不证明成交时已注册该名称。X 关联仍独立核验。外盘按 Swap 事件计数，多跳可能有多条；tx.from 为中继或代付方时可能遗漏实际用户。',
    'Relic 只统计公开 Game 铸造事件并核验 handleHash；不把普通转账、二级买入或团队分配计入公开铸造。枚数、事件和去重交易数分别展示。',
    'Flaip 保留用户指定的原曲线合约，份额计价 BNCB。金额为事件值，不代表估值或利润。',
    f"外盘读取 {sum(outer.values())} 条 Swap，交易详情缺失 {stats['missing_swap_transactions']} 条、歧义事件 {stats['ambiguous_swaps']} 条；未收录不等于未发生。"
]}
if catalog:manifest['discovery']={'flap':catalog}
manifest['curveReferences']=[p for p in load(raw/'excluded-pools.json') if p['dex']=='flapsh']
if manifest['curveReferences']:manifest['notes'].append('第三方 Flap 曲线参考地址不作为 DEX 池统计；Flap 曲线成交通过真实 Portal 成交事件单独核验。')
if manifest['excludedPools']:manifest['notes'].append('暂未纳入的池：'+'；'.join(p['dex']+' '+p['address'] for p in manifest['excludedPools'])+'；不声称完整覆盖所有外盘。')
write(public/'manifest.json',manifest,True)
write(raw/'normalized-ledger.json',ledger)
write(raw/'build-summary.json',{'manifest':manifest,'diagnostics':dict(stats)},True)
registry=load(site/'data/registry.json')
by_name={a['name']:a for a in agents}
for identity in registry:
    current=by_name.get(identity['name'])
    token=next((t for t in current['activity']['tokens'] if t['address']==ALIASES['AIPRO']),None) if current and current['owner']==identity['owner'].lower() else None
    if token or 'tradeCount' in identity:identity.update(tradeCount=token['buys']+token['sells'] if token else 0,buyCount=token['buys'] if token else 0,sellCount=token['sells'] if token else 0)
write(site/'data/registry.json',registry,True)
print(json.dumps({'agents':len(agents),'assets':len(tokens),'trades':len(trades),'nftMinted':manifest['nft']['agentMinted'],'diagnostics':dict(stats)},ensure_ascii=False),flush=True)
