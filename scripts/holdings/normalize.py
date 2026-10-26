"""Publish complete holdings snapshots as small static shards, not Worker imports."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from registration_history import publish_history
def load(p):return json.loads(p.read_text())
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
def units(raw,places):
    n=int(raw);assert n>=0 and 0<=places<=255
    if places==0:return str(n)
    s=str(n).zfill(places+1)
    return (s[:-places]+'.'+s[-places:]).rstrip('0').rstrip('.')
def publish(raw,destination):
    complete=load(raw/'complete.json');anchor=load(raw/'snapshot-block.json')
    assert complete['snapshotBlock']==anchor['number'] and complete['snapshotHash']==anchor['hash']
    assert complete.get('allRegisteredIds') is True, 'Incomplete registry coverage'
    wallets=load(raw/'wallets.json');assets=load(raw/'assets.json')
    assert len(wallets)==complete['walletCount'] and len(assets)==complete['assetCount']
    assert len({w['owner'] for w in wallets})==len(wallets)==len({w['name'] for w in wallets})
    block=anchor['number'];stage=destination.parent/(destination.name+'-next')
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if 'registryLogs' in complete:
        history=load(raw/'registration-history.json')
        publish_history(history, stage, anchor)
    bnb={'address':'native','symbol':'BNB','name':'BNB','decimals':18,'kind':'native','totalSupplyRaw':None}
    by_asset={t['address']:t for t in [bnb,*assets]}
    for w in wallets:
        assert set(w['balances'])<=set(by_asset)
        w['balances']['native']=w.pop('bnbRaw')
    snapshot_time=datetime.datetime.fromtimestamp(anchor['timestamp'],datetime.timezone.utc).isoformat()
    names=collections.defaultdict(dict);shards=collections.defaultdict(dict)
    for w in wallets:
        owner=w['owner'];assert owner==owner.lower() and len(owner)==42
        balances=[{'assetId':a,'raw':amount,'amount':units(amount,by_asset[a]['decimals'])} for a,amount in w['balances'].items() if int(amount)]
        shards[owner[2:4]][owner]={'owner':owner,'name':w['name'],'balances':balances}
        names[hashlib.sha256(w['name'].encode()).hexdigest()[:2]][w['name']]=owner
    for i in range(256):
        prefix=f'{i:02x}'
        save(stage/'wallets'/f'{prefix}.json',{'snapshotBlock':block,'wallets':shards[prefix]})
        save(stage/'names'/f'{prefix}.json',{'snapshotBlock':block,'names':names[prefix]})
    summary=[]
    for a,t in by_asset.items():
        selected=[w for w in wallets if int(w['balances'].get(a,'0'))]
        selected.sort(key=lambda w:(-int(w['balances'].get(a,'0')),w['name']))
        count=len(wallets) if a=='native' else len(selected)
        # Native pages include zero-balance wallets so every .ai can be browsed.
        if a=='native':selected+=sorted((w for w in wallets if not int(w['balances']['native'])),key=lambda w:w['name'])
        pages=max(1,(count+99)//100)
        total=sum(int(w['balances'].get(a,'0')) for w in selected)
        for page in range(1,pages+1):
            rows=[]
            for w in selected[(page-1)*100:page*100]:
                value=w['balances'].get(a,'0')
                rows.append({'owner':w['owner'],'name':w['name'],'raw':value,'amount':units(value,t['decimals'])})
            save(stage/'holders'/a/f'{page}.json',{'snapshotBlock':block,'assetId':a,'items':rows,'total':count,'page':page,'pages':pages})
        summary.append({**t,'holders':sum(bool(int(w['balances'].get(a,'0'))) for w in wallets),'totalRaw':str(total),'totalAmount':units(total,t['decimals']),'pages':pages,'rows':count})
    manifest={'schemaVersion':1,'chainId':56,'snapshotBlock':block,'snapshotHash':anchor['hash'],'snapshotTime':snapshot_time,'walletCount':len(wallets),'identityCoverage':'all-current-registered-bsc-ai','registry':'0x60b9262456de011f7d15a54cdd8c48baaa8b022f','registryDeployBlock':127950748,'assetCoverage':'tracked-contracts','assets':summary,'notes':[
        '身份范围：从注册合约部署区块重放全部 ERC721 Transfer，在同一固定区块复核 handleOf 与 ownerOf；含未参与交易的注册钱包，排除已销毁身份。',
        '资产范围：BNB、当前追踪的实际 ERC20 合约和 Relic NFT 当前余额。尚未接入全钱包资产索引；不代表所有链、所有代币或 NFT，未覆盖资产不视为零。',
        '每 2 小时重新采集。余额通过固定区块 Multicall3 读取，不用买卖差额或历史铸造枚数推算；零余额已实际查询，读取失败不发布。',
        'Flaip 曲线份额、Flap 未领取份额、质押、LP 和其他 DeFi 仓位不计入实际 ERC20 持仓；不将份额等同于已领取代币。',
        '同名资产按合约地址区分。按余额数量排序，不按市值；未提供资产估值、成本或盈亏。Relic 余额为当前 NFT 数量，包含转入并扣除转出，独立于铸造历史。',
        '持仓代表公开链上钱包余额；X 线索不是钱包控制权证明。显示快照区块与时间，非实时余额。'
    ]}
    save(stage/'manifest.json',manifest)
    with (stage/'balances.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(['Agent ID','Wallet','Chain ID','Snapshot block','Asset','Contract','Type','Balance raw','Decimals','Balance'])
        for w in wallets:
            for a,value in w['balances'].items():
                if int(value) or a=='native':
                    t=by_asset[a]
                    row=[w['name'],w['owner'],56,block,t['symbol'],a,t['kind'],value,t['decimals'],units(value,t['decimals'])]
                    writer.writerow(["'"+str(v) if str(v).startswith(('=','+','@','-')) else v for v in row])
    assert all(f.stat().st_size<24*1024*1024 for f in stage.rglob('*') if f.is_file()),'Static asset exceeds safe upload size'
    old=destination.parent/(destination.name+'-previous')
    if old.exists():shutil.rmtree(old)
    if destination.exists():destination.rename(old)
    stage.rename(destination)
    if old.exists():shutil.rmtree(old)
    print(json.dumps({'snapshotBlock':block,'wallets':len(wallets),'assets':len(summary),'positivePositions':sum(len(s['balances']) for s in [w for shard in shards.values() for w in shard.values()])}),flush=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('raw',type=Path)
    args=p.parse_args();publish(args.raw.resolve(),ROOT/'public/holdings')
