import json,re,pathlib,collections,datetime,sys
p=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'outputs/research');d=json.loads((p/'combined.json').read_text());users={x['id']:x for x in d['includes']['users']};media={x['media_key']:x for x in d['includes']['media']};ocr={}
if (p/'ocr.jsonl').exists():
 for l in (p/'ocr.jsonl').read_text().splitlines():
  try:r=json.loads(l);ocr[pathlib.Path(r['file']).stem]='\n'.join(r.get('lines',[]))
  except:pass
namepat=re.compile(r'(?<![\w./@-])([a-z0-9][a-z0-9-]{1,30}[a-z0-9])\.ai\b',re.I)
linkpat=re.compile(r'https?://web3\.binance\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?agent-id/([a-z0-9-]{3,32})(?=[/?#\s]|$)',re.I)
exclude={'gmgn.ai','openai.ai','xxx.ai','character.ai','singularity.ai','virtuals.ai','fetch.ai','bnb.ai','railway.ai','chatgpt.ai','claude.ai','v0.ai','cookie.ai','ant.fun.ai','luma.ai'}
ev=[];audits=[]
for t in d['data']:
 u=users.get(t['author_id']);
 if not u:continue
 text=t.get('note_tweet',{}).get('text') or t.get('text',''); entities=t.get('note_tweet',{}).get('entities') or t.get('entities',{});urls=' '.join(str(a.get(k,'')) for a in entities.get('urls',[]) for k in ['expanded_url','unwound_url','display_url'])
 methods=collections.defaultdict(list)
 for m in namepat.finditer(text+' '+urls):
  n=m[1].lower()+'.ai'
  if n not in exclude:methods[n].append('text' if n in text.lower() else 'expanded_url')
 for m in linkpat.finditer(urls):methods[m[1].lower()+'.ai'].append('binance_share_link')
 cards=[]
 for mk in t.get('attachments',{}).get('media_keys',[]):
  o=ocr.get(mk,'');isCard=bool(re.search(r'AGENT\s*ID',o,re.I))
  if isCard:
   ns=[m[1].lower()+'.ai' for line in o.splitlines() if re.fullmatch(r'[a-z0-9-]{3,32}\.ai',line.strip(),re.I) for m in namepat.finditer(line)]
   for n in ns:
    if n not in exclude:methods[n].append('image_ocr');cards.append({'name':n,'key':mk,'ocr':o})
 related=bool(re.search(r'agent\s*(id|identity|ic)|#MyAgentID|代理\s*ID',text+' '+urls,re.I))
 if not related and not cards:methods.clear()
 # Ordinary .ai websites and generic phrases are not Binance Agent IDs.
 strong={n for n,ms in methods.items() if 'binance_share_link' in ms or 'image_ocr' in ms}
 own=bool(re.search(r'my.{0,30}agent.{0,8}id|我的.{0,15}(?:id|身份)|我申请了|我注册了',text,re.I))
 for n in list(methods):
  if n not in strong and not own:del methods[n]
 for n in ['registered.ai','authsec.ai','asksurf.ai']:
  if n not in strong:methods.pop(n,None)
 reply=any(r.get('type')=='replied_to' for r in t.get('referenced_tweets',[]))
 selfclaim=bool(re.search(r'\bmy (?:official |new |unique )?(?:agent|id)|\bmyagentid\b|\bi (?:chose|named|created|claimed)|just claimed|meet my|claimed my|我的.*(?:id|身份)|我.*(?:领取|注册|认领)|mon.*id|je viens',text,re.I))
 corrections={'2113377164175581484':{'oxsiam.ai':'0xsiam.ai'},'2113356755866726869':{'kix.ai':'klx.ai'},'2113289440965628364':{'josephoxyz.ai':'joseph0xyz.ai'},'2113282227668939167':{'wagar333.ai':'waqar333.ai'}}
 for wrong,right in corrections.get(t['id'],{}).items():
  if wrong in methods:
   methods[right].extend(methods.pop(wrong)+['manual_review'])
   for c in cards:
    if c['name']==wrong:c['name']=right
 # A screenshot of a registry list does not associate every listed ID with its publisher.
 mentioned_only=len(methods)>3 and not selfclaim
 for n,ms in ([] if mentioned_only else methods.items()):
  ms=sorted(set(ms));card=next((c for c in cards if c['name']==n),None)
  status='self_declared' if selfclaim and len(methods)==1 and not reply else 'candidate'
  if t['id'] in ['2112563848020689152','2112695850464129206']:status='self_declared'
  ev.append({'id':t['id']+'-'+n[:-3],'name':n,'xHandle':u['username'],'authorId':u['id'],'displayName':u.get('name',u['username']),'sourceUrl':f'https://x.com/{u["username"]}/status/{t["id"]}','excerpt':text[:130],'status':status,'publishedAt':t.get('created_at'),'collectedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceType':'x','chainVerified':False,'extractionMethods':ms,'matchedText':n,'mediaUrl':(media.get(card['key'],{}).get('url') or media.get(card['key'],{}).get('preview_image_url')) if card else None,'reviewNote':'本人发布的 Agent ID 分享卡片，已人工核对' if t['id'] in ['2112563848020689152','2112695850464129206'] else ('图片字符已人工校正；不构成控制权证明' if 'manual_review' in ms else '自动提取；多名称、回复、他人提及保留为待核实')})
 audits.append({'postId':t['id'],'xHandle':u['username'],'url':f'https://x.com/{u["username"]}/status/{t["id"]}','publishedAt':t.get('created_at'),'names':list(methods),'hasMedia':bool(t.get('attachments',{}).get('media_keys')),'text':text})
(p/'extracted.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2));(p/'post-audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2))
print({'posts':len(audits),'evidence':len(ev),'names':len(set(e['name'] for e in ev)),'ocr':len(ocr),'methods':dict(collections.Counter(m for e in ev for m in e['extractionMethods'])),'self':sum(e['status']=='self_declared' for e in ev)})
print('names',','.join(sorted(set(e['name'] for e in ev))))
