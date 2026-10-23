import json,pathlib,re,concurrent.futures,time,httpx,datetime
from eth_abi import encode,decode
from Crypto.Hash import keccak
import argparse,hashlib,os
parser=argparse.ArgumentParser(description='Import reviewed public local X/Agent ID mappings')
parser.add_argument('--source',required=True,type=pathlib.Path)
parser.add_argument('--force',action='store_true')
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
source_bytes=args.source.read_bytes();fingerprint=hashlib.sha256(source_bytes).hexdigest()
out=root/'.sync-state';out.mkdir(exist_ok=True)
state_file=out/'source.json'
if state_file.exists() and not args.force and json.loads(state_file.read_text()).get('sha256')==fingerprint:
 print(json.dumps({'changed':False,'sourceSha256':fingerprint}));raise SystemExit(0)
src=json.loads(source_bytes)
if not isinstance(src.get('mappings'),list) or not src.get('generatedAt'):raise ValueError('Invalid source snapshot')
if len(src['mappings'])>50000:raise ValueError('Source row limit exceeded')
rpc_url=os.environ.get('BSC_RPC_URL','https://bsc-rpc.publicnode.com')

valid=[];rejected=[]
for r in src['mappings']:
 n=str(r.get('agentId','')).lower();u=r.get('postUrl','');expected=f"https://x.com/{r.get('xHandle','')}/status/{r.get('postId','')}"
 if n in ['registered.ai','josephoxyz.ai','wagar333.ai'] or not re.fullmatch(r'[a-z0-9-]{3,32}\.ai',n) or not re.fullmatch(r'\w{1,15}',str(r.get('xHandle',''))) or not re.fullmatch(r'\d{5,25}',str(r.get('postId',''))) or r.get('confidence') not in ['high','medium','low'] or r.get('sourceType') not in ['image-OCR','link','text','quoted'] or u!=expected:
  rejected.append({'name':n,'sourceUrl':u,'reason':'invalid name or source URL'});continue
 valid.append(r)
names=sorted({r['agentId'].lower() for r in valid});reg='0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F';multi='0xcA11bde05977b3631167028862bE2a173976CA11';sel=keccak.new(digest_bits=256,data=b'aggregate3((address,bool,bytes)[])').digest()[:4]
try:
 fixed_block=httpx.post(rpc_url,timeout=30,json={'jsonrpc':'2.0','id':1,'method':'eth_blockNumber','params':[]}).json()['result']
except Exception:
 raise RuntimeError('Cannot obtain BSC snapshot block; source data unchanged') from None
def batch(nn):
 calls=[(reg,True,bytes.fromhex('6352211e')+keccak.new(digest_bits=256,data=n[:-3].encode()).digest()) for n in nn]+[(multi,False,bytes.fromhex('42cbb15c'))]
 for i in range(4):
  try:
   d=httpx.post(rpc_url,timeout=60,json={'jsonrpc':'2.0','id':1,'method':'eth_call','params':[{'to':multi,'data':'0x'+(sel+encode(['(address,bool,bytes)[]'],[calls])).hex()},fixed_block]}).json();rr=decode(['(bool,bytes)[]'],bytes.fromhex(d['result'][2:]))[0];b=int.from_bytes(rr[-1][1],'big');assert b==int(fixed_block,16);return {n:{'owner':'0x'+raw[-20:].hex() if ok and len(raw)==32 else '', 'block':b} for n,(ok,raw) in zip(nn,rr)}
  except Exception:
   if i==3:raise RuntimeError('Fixed-block chain verification failed; no data files were changed') from None
   time.sleep(2)
checks={}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
 for checked in executor.map(batch,[names[i:i+100] for i in range(0,len(names),100)]):
  checks.update(checked)
now=datetime.datetime.now(datetime.timezone.utc).isoformat();ev=json.load(open(root/'data/evidence.json'));agents=json.load(open(root/'data/registry.json'));am={a['name']:a for a in agents};em={(e['name'],e['xHandle'].lower(),e['sourceUrl'].split('/')[-1]):e for e in ev};added=0;overlap=0
legacy=set(json.loads(re.search(r'const legacyIds=new Set\((\[.*?\])\);',(root/'scripts/check-data.mjs').read_text()).group(1)))
current={(r['agentId'].lower(),r['xHandle'].lower(),r['postId']) for r in valid}
original_count=len(ev)
ev=[e for e in ev if not e.get('sourceOrigin') or e['id'] in legacy or (e['name'],e['xHandle'].lower(),e['sourceUrl'].split('/')[-1]) in current]
em={(e['name'],e['xHandle'].lower(),e['sourceUrl'].split('/')[-1]):e for e in ev}
for r in valid:
 n=r['agentId'].lower();ch=checks[n];key=(n,r['xHandle'].lower(),r['postId']);method={'image-OCR':'image_ocr','link':'binance_share_link' if 'agent-id/' in r.get('evidence','') else 'expanded_url','text':'text','quoted':'quoted'}[r['sourceType']];note=re.sub(r'\s*\[raw:.*?\]','',r.get('evidence',''))[:700];media=re.search(r'https://pbs\.twimg\.com/[^\s\]\)]+',note)
 meta={'sourceOrigin':'Grok 本机索引','sourceConfidence':r['confidence'],'sourceSnapshotAt':src['generatedAt'],'nameRegistered':bool(ch['owner'])}
 if key in em:
  e=em[key];e.update(meta);e['extractionMethods']=list(dict.fromkeys(e.get('extractionMethods',[])+[method]));overlap+=1
 else:
  e={'id':r['postId']+'-'+n[:-3],'name':n,'xHandle':r['xHandle'],'sourceUrl':r['postUrl'],'excerpt':r.get('text','')[:130],'status':'candidate','publishedAt':r.get('postDate'),'collectedAt':now,'sourceType':'x','chainVerified':False,'extractionMethods':[method],'matchedText':n,'reviewNote':'本机来源评级仅表示提取线索可信度；未核实 X 账号与钱包控制权。'+note,**meta}
  if media:e['mediaUrl']=media[0]
  ev.append(e);em[key]=e;added+=1
 if not ch['owner']: am.pop(n,None)
 if ch['owner']:
  am[n]={**am.get(n,{}),'name':n,'owner':ch['owner'],'block':ch['block'],'source':'BSC ownerOf(name hash) · Grok source','chainVerified':True}
research=json.load(open(root/'data/research.json'));research['legacyApiLimitReason']=research.get('legacyApiLimitReason',research['limitReason']);research['limitReason']='本机 Grok 索引与既有线索合并，未证明完整覆盖最近 7 天的全部 X 帖子。';research['localImport']={'source':'Grok 本机索引','generatedAt':src['generatedAt'],'reportedPostsScanned':src['postsScanned'],'reportedOcrImages':src['ocrImages'],'mappingRows':len(src['mappings']),'acceptedRows':len(valid),'rejectedRows':len(rejected),'newEvidence':added,'overlapEvidence':overlap,'checkedNames':len(checks),'registeredNames':sum(bool(c['owner']) for c in checks.values()),'checkedAt':now,'minBlock':min(c['block'] for c in checks.values()),'maxBlock':max(c['block'] for c in checks.values())};research.update(evidenceItems=len(ev),linkedNames=len({e['name'] for e in ev}),registryRecords=len(am),selfDeclaredItems=sum(e['status']=='self_declared' for e in ev),candidateItems=sum(e['status']=='candidate' for e in ev))
for path,data in [('data/evidence.json',ev),('data/registry.json',list(am.values())),('data/research.json',research)]: (root/path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(out/'audit.json').write_text(json.dumps({'import':research['localImport'],'rejected':rejected},ensure_ascii=False,indent=2));(out/'chain-checks.json').write_text(json.dumps(checks));state_file.write_text(json.dumps({'sha256':fingerprint,'generatedAt':src['generatedAt']}))
print(json.dumps({'changed':True,'removedEvidence':original_count+added-len(ev),'import':research['localImport'],'mergedEvidence':len(ev),'linkedNames':research['linkedNames'],'unexpectedOldRegressionNames':[e['name'] for e in ev if e['name'] in ['registered.ai','josephoxyz.ai','wagar333.ai']]},ensure_ascii=False))
