import json,pathlib,collections,datetime,re,sys
from decimal import Decimal,getcontext
getcontext().prec=90
from Crypto.Hash import keccak
site=pathlib.Path(__file__).resolve().parents[2];raw=pathlib.Path(sys.argv[1]).expanduser().resolve();public=site/'public/activity';public.mkdir(parents=True,exist_ok=True);(public/'wallets').mkdir(exist_ok=True)
assert (raw/'refresh-complete.json').exists(), 'A complete refreshed snapshot is required'
handles=json.load(open(raw/'handles-source.json'))['wallets'];extra=raw/'extra-handles-source.json'
if extra.exists():handles+=json.load(open(extra))
head=json.load(open(raw/'snapshot-block.json'))['number'];assert json.load(open(raw/'refresh-complete.json'))['block']==head
assert all(r['block']==head for r in handles), 'Mixed identity snapshot blocks'
known={r['owner']:r for r in handles};known={a:r for a,r in known.items() if re.fullmatch('[a-zA-Z0-9-]{3,32}',r['handle'] or '')};ledger=[];stats=collections.Counter();all_inner={};all_outer=collections.Counter();head=json.load(open(raw/'relic-mints-source.json'))['head'];pool0=json.load(open(raw/'pool-token0.json'))
def dec(n):
 s=format(Decimal(n)/Decimal(10**18),'f');return s.rstrip('0').rstrip('.') if '.' in s else s
def words(l):return [int(l['data'][i:i+64],16) for i in range(2,len(l['data']),64)]
def add(l,owner,asset,kind,venue,direction,amount,quote=None,qs=None,source='',attribution='',pool=None):
 owner=owner.lower()
 if owner not in known:return
 row={'id':l['transactionHash']+':'+str(int(l['logIndex'],16)),'kind':kind,'owner':owner,'name':known[owner]['handle'].lower()+'.ai','asset':asset,'venue':venue,'direction':direction,'amount':str(amount),'tx':l['transactionHash'],'block':int(l['blockNumber'],16),'logIndex':int(l['logIndex'],16),'source':source,'attribution':attribution}
 if quote is not None:row.update({'quoteAmount':quote,'quoteSymbol':qs})
 if pool:row['pool']=pool
 ledger.append(row)
for f in raw.glob('*.json'):
 d=json.load(open(f))
 if isinstance(d,dict) and 'logs' in d:assert d.get('head')==head and d.get('complete'), f'Incomplete or mixed source: {f.name}'
# NFT mint events have recipient and handleHash; require an exact hash/name match.
nft=json.load(open(raw/'relic-mints-source.json'))
for l in nft['logs']:
 a='0x'+l['topics'][1][-40:];r=known.get(a)
 if not r or '0x'+keccak.new(digest_bits=256,data=r['handle'].encode()).hexdigest()!=l['topics'][2].lower():stats['nft_unmatched_hash']+=1;continue
 w=words(l);bnb=l['topics'][0]=='0x'+keccak.new(digest_bits=256,data=b'MintedWithBnb(address,bytes32,uint8,uint256)').hexdigest();add(l,a,'Relic NFT','nft','mint','mint',str(w[0]),dec(w[1]),'BNB' if bnb else 'USDT','Ptah Minted / MintedWithBnb','铸造事件接收地址；名称 hash 与链上记录一致')
# Curve events. ERC20 transfers alone are never classified as trades.
for f in raw.glob('inner-*.json'):
 d=json.load(open(f));all_inner[d['symbol']]=len(d['logs'])
 for l in d['logs']:
  w=words(l);form=d['format'];a='0x'+l['topics'][2 if form=='manager' else 1][-40:]
  if form=='aipro':buy=bool(w[0]);amount=w[1];quote=w[2]
  elif form=='direct':buy=l['topics'][0].startswith('0x1cbc5a');amount=w[0];quote=w[1]
  else:buy=l['topics'][0].startswith('0x75a85');amount=w[2];quote=w[0]
  add(l,a,d['symbol'],'token','inner','buy' if buy else 'sell',dec(amount),dec(quote),'BNB','BSC 曲线成交事件','成交事件中的交易者；计价数量为事件值，费用口径以合约为准')
flaip=json.load(open(raw/'flaip-all-events.json'));all_inner['Flaip']=len(flaip['logs'])
for l in flaip['logs']:
 w=words(l);buy=l['topics'][0].startswith('0x27330b');a='0x'+l['topics'][1][-40:];amount=w[2] if buy else w[0];quote=w[0] if buy else w[1];add(l,a,'Flaip','token','inner','buy' if buy else 'sell',dec(amount),dec(quote),'BNCB','Flaip Bought / Sold','曲线份额交易事件中的交易者；非普通 ERC20，报价单位为 BNCB')
# DEX records are assigned to transaction.from, never pool sender/router or a transfer recipient.
for f in raw.glob('pool-*.json'):
 d=json.load(open(f))
 if 'pool' not in d:continue
 symbol='.ai' if d['symbol']=='dotai' else d['symbol'];all_outer[symbol]+=len(d['logs']);p=d['pool'];idx=0 if pool0[p['pairAddress'].lower()]==d['token'].lower() else 1
 other=p['quoteToken'] if p['baseToken']['address'].lower()==d['token'].lower() else p['baseToken'];qs=other['symbol']
 for l in d['logs']:
  path=raw/'txs'/(l['transactionHash']+'.json')
  if not path.exists():stats['missing_swap_transactions']+=1;continue
  tx=json.load(open(path));a=tx.get('from')
  if not a:stats['missing_swap_transactions']+=1;continue
  if a not in known:continue
  w=words(l)
  if d['version']==2:
   ti,to=w[idx],w[idx+2];oi,oo=w[1-idx],w[3-idx]
   if to>0 and ti==0:buy=True;amount=to;quote=oi
   elif ti>0 and to==0:buy=False;amount=ti;quote=oo
   else:stats['ambiguous_swaps']+=1;continue
  else:
   amounts=[v if v<2**255 else v-2**256 for v in w[:2]];amt=amounts[idx];buy=amt<0;amount=abs(amt);quote=abs(amounts[1-idx])
  add(l,a,symbol,'token','outer','buy' if buy else 'sell',dec(amount),dec(quote),qs,p['dexId']+' V'+str(d['version'])+' Swap','交易发起地址 tx.from；不把路由器或收币地址当成交易者',p['pairAddress'])
assert not stats['missing_swap_transactions'], 'Incomplete transaction sender coverage'
# Idempotent log identity.
ledger=list({r['id']:r for r in ledger}.values());ledger.sort(key=lambda r:(r['block'],r['logIndex']),reverse=True);bywallet=collections.defaultdict(list)
for r in ledger:bywallet[r['owner']].append(r)
agents=[]
for a,rows in bywallet.items():
 r=known[a];ts={};summary={'tokenTrades':0,'innerTrades':0,'outerTrades':0,'nftMintCount':0,'nftMintTransactions':0,'lastBlock':max(t['block'] for t in rows),'tokens':[]}
 for t in rows:
  if t['kind']=='nft':summary['nftMintCount']+=int(t['amount']);summary['nftMintTransactions']+=1
  else:
   summary['tokenTrades']+=1;summary['innerTrades' if t['venue']=='inner' else 'outerTrades']+=1
   z=ts.setdefault(t['asset'],{'symbol':t['asset'],'buys':0,'sells':0,'inner':0,'outer':0,'innerBuys':0,'innerSells':0,'outerBuys':0,'outerSells':0});z['buys' if t['direction']=='buy' else 'sells']+=1;z[t['venue']]+=1;z[t['venue']+('Buys' if t['direction']=='buy' else 'Sells')]+=1
 summary['nftMintTransactions']=len({t['tx'] for t in rows if t['kind']=='nft'})
 summary['tokens']=list(ts.values());agents.append({'name':r['handle'].lower()+'.ai','owner':a,'source':'BSC RPC + events','chainVerified':True,'block':r['block'],'activity':summary})
agents.sort(key=lambda a:a['activity']['lastBlock'],reverse=True)
for prefix in [f'{i:02x}' for i in range(256)]:
 data={a:rs for a,rs in bywallet.items() if a[2:4]==prefix};(public/'wallets'/(prefix+'.json')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
(public/'agents.json').write_text(json.dumps(agents,ensure_ascii=False,separators=(',',':')))
feed=[]
for symbol in ['AIPRO','.ai','GANG','Flaip','Relic NFT']:feed.extend([r for r in ledger if r['asset']==symbol][:200])
feed.sort(key=lambda r:(r['block'],r['logIndex']),reverse=True);(public/'feed.json').write_text(json.dumps(feed,ensure_ascii=False,separators=(',',':')))
nf=[r for r in ledger if r['kind']=='nft'];tr=[r for r in ledger if r['kind']=='token'];tokens=[]
for symbol,a in {'AIPRO':'0xfa81c13f979f0dff4a40b68c4aba147fa0723333','.ai':'0x7ffcf7b3b52adcc00c76f50ce2e37bf3c7e215dc','GANG':'0x0c6302401aa5325c2e36f170f52c00b1d220b405','Flaip':'0xb8fb293b3e8e3c5fd741e34ac5810dd5dc9f2c7f'}.items():
 rows=[r for r in tr if r['asset']==symbol];tokens.append({'symbol':symbol,'address':a,'status':'curve' if symbol=='Flaip' else 'active','internal':{'status':'indexed','events':all_inner[symbol],'agentEvents':sum(r['venue']=='inner' for r in rows),'note':'Bought / Sold 曲线份额；计价 BNCB' if symbol=='Flaip' else '按已识别的曲线成交事件统计'},'external':{'status':'not_discovered' if symbol=='Flaip' else 'indexed','events':all_outer[symbol],'agentEvents':sum(r['venue']=='outer' for r in rows),'note':'未发现外部交易池，不等于零交易' if symbol=='Flaip' else '已发现的 DEX 池；按 Swap 与 tx.from 归属'},'agentWallets':len({r['owner'] for r in rows})})
pool_count=len([f for f in raw.glob('pool-*.json') if 'pool' in json.load(open(f))])
manifest={'updatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'snapshotBlock':head,'snapshotHash':json.load(open(raw/'snapshot-block.json'))['hash'],'identitySnapshotBlock':head,'poolCount':pool_count,'snapshotTime':datetime.datetime.fromtimestamp(json.load(open(raw/'snapshot-block.json'))['timestamp'],datetime.timezone.utc).isoformat(),'chainId':56,'tokens':tokens,'nft':{'name':'Relic NFT','contract':'0xe8c6b38b5e63377a96b268319b66638f772254bb','game':'0xb0d5f3108af164f5f7046f53ab59fd2779812d10','publicMinted':sum(words(l)[0] for l in nft['logs']),'mintEvents':len(nft['logs']),'agentMinted':sum(int(r['amount']) for r in nf),'agentMintEvents':len(nf),'agentMintTransactions':len({r['tx'] for r in nf}),'agentWallets':len({r['owner'] for r in nf})},'totals':{'agentCount':len(agents),'tokenTrades':len(tr),'nftMinted':sum(int(r['amount']) for r in nf),'nftMintEvents':len(nf),'nftMintTransactions':len({r['tx'] for r in nf})},'notes':[f'这是固定区块的历史快照，不是持续自动同步。代币内盘从 Agent ID 注册体系上线区块 128724651 扫描到快照区块；外盘覆盖已发现并核验的 {pool_count} 个 V2/V3 交易池，从各池建立时间或注册体系上线区块开始。','交易按当前链上 handleOf(address) 归属回溯；不能保证交易发生时已注册该名称。地址与 X 账号的关联依然单独核验。','内盘只识别确认的成交事件；外盘按 Swap 事件计数，聚合或多跳交易可能有多条 Swap。tx.from 由代付方或中继发起时可能遗漏实际用户，未确认的收币地址不推断为交易者。','Relic 仅统计 Game 的 Minted / MintedWithBnb 事件，并核对 handleHash；不把 NFT 普通转账、二级买入或团队预留铸造计入公开铸造量。NFT 枚数与铸造交易次数分别展示。','Flaip 使用用户更正的曲线合约地址，metadata() 确认为 Flaip，报价单位 BNCB；它不是普通 ERC20，尚未发现外部池。计价金额为事件记录值，不计作当前估值或利润。',f"外盘共读取 {sum(all_outer.values())} 条 Swap；交易详情未取到的事件 {stats['missing_swap_transactions']} 条，歧义事件 {stats['ambiguous_swaps']} 条。未收录不等于没有发生。"]}
excluded=json.load(open(raw/'excluded-pools.json'))
manifest['excludedPools']=excluded
manifest['walletsChecked']=json.load(open(raw/'refresh-complete.json'))['walletsChecked']
manifest['pools']=[{'address':d['pool']['pairAddress'].lower(),'symbol':'.ai' if d['symbol']=='dotai' else d['symbol'],'dex':d['pool']['dexId'],'version':d['version'],'fromBlock':d['fromBlock'],'toBlock':d['head'],'events':len(d['logs'])} for f in raw.glob('pool-*.json') if isinstance((d:=json.load(open(f))),dict) and 'pool' in d]
if excluded:manifest['notes'].append('发现但暂未纳入统计的池：'+ '；'.join(p['dex']+' '+p['address']+'（事件格式尚未支持）' for p in excluded)+'。不声称完整覆盖所有外盘。')
(public/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(raw/'normalized-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,separators=(',',':')));(raw/'build-summary.json').write_text(json.dumps({'manifest':manifest,'diagnostics':dict(stats)},ensure_ascii=False,indent=2));print(json.dumps({'agents':len(agents),'trades':len(tr),'nftMintEvents':len(nf),'nftMinted':sum(int(r['amount']) for r in nf),'diagnostics':dict(stats)},ensure_ascii=False),flush=True)

# Legacy directory counts must agree with the current complete AIPRO ledger.
registry_path=site/'data/registry.json'
registry=json.load(open(registry_path))
by_name={a['name']:a for a in agents}
for a in registry:
 current=by_name.get(a['name'])
 token=next((t for t in current['activity']['tokens'] if t['symbol']=='AIPRO'),None) if current and current['owner']==a['owner'].lower() else None
 if token or 'tradeCount' in a:
  a.update(tradeCount=token['buys']+token['sells'] if token else 0,buyCount=token['buys'] if token else 0,sellCount=token['sells'] if token else 0)
registry_path.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
