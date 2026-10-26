"""Snapshot every current BSC .ai owner, native BNB and tracked ERC20/NFT balances.

No indexer key is needed for this bounded asset inventory. Unknown assets are
explicitly outside coverage. All contract reads use fixed-block Multicall3.
"""
import argparse
import concurrent.futures as futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import httpx
from eth_abi import encode, decode
from Crypto.Hash import keccak

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
REGISTRY = '0x60b9262456de011f7d15a54cdd8c48baaa8b022f'
MULTI = '0xca11bde05977b3631167028862be2a173976ca11'
DEPLOY = 127950748
ZERO = '0x'+'0'*40
def sig(s): return keccak.new(digest_bits=256, data=s.encode()).digest()
TRANSFER = '0x'+sig('Transfer(address,address,uint256)').hex()
def load(p): return json.loads(p.read_text())
def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    t=p.with_suffix(p.suffix+'.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    t.replace(p)
def call(target, method, types=(), values=()): return target, sig(method)[:4]+encode(types,values)
def registry_owners(logs):
    """Replay ERC721 transfers, including transfers away and burns."""
    owners={}
    seen=set()
    for row in sorted(logs,key=lambda r:(int(r['blockNumber'],16),int(r['logIndex'],16))):
        assert row['address'].lower()==REGISTRY and not row.get('removed')
        assert len(row['topics'])==4 and row['topics'][0].lower()==TRANSFER
        key=(row['transactionHash'],row['logIndex'])
        assert key not in seen, 'Duplicate registry log'
        seen.add(key)
        token=row['topics'][3].lower()
        before='0x'+row['topics'][1][-40:].lower()
        after='0x'+row['topics'][2][-40:].lower()
        assert (token not in owners and before==ZERO) or owners.get(token)==before, 'Incomplete registry transfer history'
        if after==ZERO:owners.pop(token,None)
        else:owners[token]=after
    assert len(set(owners.values()))==len(owners), 'Multiple IDs per wallet need explicit identity handling'
    return owners

class Snapshot:
    def __init__(self,out,source=None):
        self.out=out;self.source=source
        self.client=httpx.Client(timeout=90)
        self.configured=os.environ.get('BSC_RPC_URL')
        self.log_url=self.configured or 'https://rpc-bsc.48.club'
        self.call_url=self.configured or 'https://bsc-mainnet.public.blastapi.io'
        self.out.mkdir(parents=True,exist_ok=True)
        if (out/'snapshot-block.json').exists():self.anchor=load(out/'snapshot-block.json')
        else:
            head=int(self.rpc('eth_blockNumber',[]),16)-100
            b=self.rpc('eth_getBlockByNumber',[hex(head),False])
            self.anchor={'number':head,'hash':b['hash'],'timestamp':int(b['timestamp'],16)}
            save(out/'snapshot-block.json',self.anchor)
        self.block=self.anchor['number']
        assert self.rpc('eth_getBlockByNumber',[hex(self.block),False])['hash']==self.anchor['hash']
    def rpc(self,method,params):
        for attempt in range(5):
            try:
                r=self.client.post(self.call_url if method in ('eth_call','eth_getCode') else self.log_url,json={'jsonrpc':'2.0','id':1,'method':method,'params':params})
                r.raise_for_status();d=r.json()
                if 'error' in d:raise ValueError()
                return d['result']
            except Exception:
                if attempt==4:raise RuntimeError(f'{method} failed; endpoint redacted') from None
                time.sleep(attempt+1)
    def multi(self,calls,optional=False):
        data=sig('aggregate3((address,bool,bytes)[])')[:4]+encode(['(address,bool,bytes)[]'],[[(a,optional,b) for a,b in calls]])
        r=self.rpc('eth_call',[{'to':MULTI,'data':'0x'+data.hex()},hex(self.block)])
        rows=decode(['(bool,bytes)[]'],bytes.fromhex(r[2:]))[0]
        assert len(rows)==len(calls)
        if optional:return rows
        assert all(ok for ok,_ in rows),'Required balance/identity read failed; preserve prior snapshot'
        return [b for _,b in rows]
    def logs(self,lo,hi):
        path=self.out/'logs'/f'{lo}-{hi}.json'
        if path.exists():
            rows=load(path)
            assert all(lo<=int(r['blockNumber'],16)<=hi for r in rows), 'Invalid cached log range'
            return rows
        try:
            rows=self.rpc('eth_getLogs',[{'address':REGISTRY,'topics':[TRANSFER],'fromBlock':hex(lo),'toBlock':hex(hi)}])
        except RuntimeError:
            if hi-lo<64:raise
            mid=(lo+hi)//2;rows=self.logs(lo,mid)+self.logs(mid+1,hi)
        if len(rows)>=10000 and hi>lo:
            mid=(lo+hi)//2;rows=self.logs(lo,mid)+self.logs(mid+1,hi)
        assert all(lo<=int(r['blockNumber'],16)<=hi for r in rows)
        save(path,rows);return rows
    def cached_multi(self,label,calls):
        digest=hashlib.sha256(b''.join(bytes.fromhex(a[2:])+b for a,b in calls)).hexdigest()
        p=self.out/'calls'/f'{label}-{self.block}-{digest}.json'
        if p.exists():
            values=[bytes.fromhex(v) for v in load(p)]
            assert len(values)==len(calls),'Incomplete Multicall cache'
            return values
        # Reuse interrupted first-run 500-call caches when increasing throughput.
        # Only uncached reads are issued; keys always include the fixed block.
        if label=='balances' and len(calls)>500:
            parts=[];missing=[]
            for start in range(0,len(calls),500):
                chunk=calls[start:start+500]
                key=hashlib.sha256(b''.join(bytes.fromhex(a[2:])+b for a,b in chunk)).hexdigest()
                path=self.out/'calls'/f'{label}-{self.block}-{key}.json'
                value=[bytes.fromhex(v) for v in load(path)] if path.exists() else None
                if value is not None:assert len(value)==len(chunk),'Incomplete Multicall subcache'
                parts.append([path,chunk,value])
                if value is None:missing.extend(chunk)
            fetched=self.multi(missing) if missing else [];offset=0
            for part in parts:
                if part[2] is None:
                    part[2]=fetched[offset:offset+len(part[1])];offset+=len(part[1])
                    save(part[0],[v.hex() for v in part[2]])
            rows=[v for _,_,part in parts for v in part]
        else:rows=self.multi(calls)
        save(p,[v.hex() for v in rows]);return rows
    def run(self):
        assert self.rpc('eth_getCode',[REGISTRY,hex(DEPLOY-1)])=='0x','Registry start block must precede deployment'
        previous=[];start=DEPLOY
        if self.source:
            old=load(self.source/'complete.json');anchor=load(self.source/'snapshot-block.json')
            assert old['snapshotHash']==anchor['hash'] and old['snapshotBlock']==anchor['number']<self.block
            assert self.rpc('eth_getBlockByNumber',[hex(anchor['number']),False])['hash']==anchor['hash']
            previous=load(self.source/'registry-transfers.json');start=anchor['number']+1
        ranges=[(lo,min(lo+4999,self.block)) for lo in range(start,self.block+1,5000)]
        logs=list(previous)
        with futures.ThreadPoolExecutor(max_workers=4) as ex:
            for i,rows in enumerate(ex.map(lambda r:self.logs(*r),ranges)):
                logs.extend(rows)
                if i%25==0:print({'registryLogBatches':i,'total':len(ranges)},flush=True)
        owners=registry_owners(logs);save(self.out/'registry-transfers.json',logs)
        from registration_history import build_history
        build_history(logs, self.anchor, self.rpc, self.out, self.source)
        print({'currentIds':len(owners),'snapshotBlock':self.block},flush=True)
        # The curve contract is not an ERC20. Do not fabricate a zero balance.
        activity=load(ROOT/'public/activity/manifest.json')
        erc20=[{'address':t['address'].lower(),'symbol':t['symbol'],'name':t['name'],'kind':'erc20'} for t in activity['tokens'] if t['status']!='curve']
        nft={'address':activity['nft']['contract'].lower(),'symbol':'Relic','name':'Relic NFT','kind':'erc721','decimals':0}
        assets=erc20+[nft]
        values=self.multi([call(t['address'],method) for t in erc20 for method in ('decimals()','totalSupply()')]+[call(nft['address'],'totalSupply()'),call(nft['address'],'supportsInterface(bytes4)',['bytes4'],[bytes.fromhex('80ac58cd')])],optional=True)
        for i,t in enumerate(erc20):
            ok,raw=values[i*2];assert ok
            t['decimals']=decode(['uint8'],raw)[0]
            ok,raw=values[i*2+1];t['totalSupplyRaw']=str(decode(['uint256'],raw)[0]) if ok else None
        ok,raw=values[-2];nft['totalSupplyRaw']=str(decode(['uint256'],raw)[0]) if ok else None
        ok,raw=values[-1];assert ok and decode(['bool'],raw)[0], 'Relic ERC721 interface mismatch'
        rows=sorted(owners.items());wallets=[]
        def identity(chunk):
            values=self.cached_multi('identities',[c for token,owner in chunk for c in (call(REGISTRY,'handleOf(address)',['address'],[owner]),call(REGISTRY,'ownerOf(uint256)',['uint256'],[int(token,16)]),call(MULTI,'getEthBalance(address)',['address'],[owner]))])
            out=[]
            for i,(token,owner) in enumerate(chunk):
                handle=decode(['string'],values[i*3])[0]
                assert re.fullmatch('[a-zA-Z0-9-]{3,32}',handle)
                assert '0x'+sig(handle).hex()==token and decode(['address'],values[i*3+1])[0].lower()==owner
                out.append({'owner':owner,'name':handle.lower()+'.ai','bnbRaw':str(decode(['uint256'],values[i*3+2])[0]),'balances':{}})
            return out
        chunks=[rows[i:i+200] for i in range(0,len(rows),200)]
        with futures.ThreadPoolExecutor(max_workers=4) as ex:
            for i,chunk in enumerate(ex.map(identity,chunks)):
                wallets.extend(chunk)
                if i%25==0:print({'identityBatches':i,'total':len(chunks)},flush=True)
        save(self.out/'identities.json',wallets)
        # Every wallet is queried, including zeros and identities with no activity.
        jobs=[(asset,wallets[i:i+2000]) for asset in assets for i in range(0,len(wallets),2000)]
        def balances(job):
            asset,chunk=job
            values=self.cached_multi('balances',[call(asset['address'],'balanceOf(address)',['address'],[w['owner']]) for w in chunk])
            return asset['address'],[(w['owner'],str(decode(['uint256'],v)[0])) for w,v in zip(chunk,values)]
        by_owner={w['owner']:w for w in wallets}
        with futures.ThreadPoolExecutor(max_workers=4) as ex:
            for i,(asset,values) in enumerate(ex.map(balances,jobs)):
                for owner,amount in values:
                    if int(amount):by_owner[owner]['balances'][asset]=amount
                if i%100==0:print({'balanceBatches':i,'total':len(jobs)},flush=True)
        assert self.rpc('eth_getBlockByNumber',[hex(self.block),False])['hash']==self.anchor['hash'],'Snapshot reorganization'
        save(self.out/'assets.json',assets)
        save(self.out/'wallets.json',wallets)
        save(self.out/'complete.json',{'snapshotBlock':self.block,'snapshotHash':self.anchor['hash'],'walletCount':len(wallets),'assetCount':len(assets),'registryLogs':len(logs),'allRegisteredIds':True,'assetCoverage':'BNB + tracked ERC20 contracts + Relic NFT; not a full-wallet asset index'})
        print({'complete':True,'wallets':len(wallets),'assets':len(assets)},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--source',type=Path)
    p.add_argument('--rpc-env-file',type=Path,help='Read only the named RPC variable; never execute/source the file')
    p.add_argument('--rpc-env-name',default='BSC_RPC_URL')
    args=p.parse_args()
    if not os.environ.get('BSC_RPC_URL') and args.rpc_env_file:
        assert re.fullmatch('[A-Z_][A-Z0-9_]*',args.rpc_env_name)
        found=re.search(r'^\s*'+re.escape(args.rpc_env_name)+r'\s*=\s*(.*?)\s*$',args.rpc_env_file.read_text(),re.M)
        assert found,'Named RPC setting not found; value redacted'
        endpoint=found[1].strip().strip('\"\'')
        assert endpoint.startswith('https://'),'HTTPS RPC required'
        os.environ['BSC_RPC_URL']=endpoint
    Snapshot(args.out.resolve(),args.source.resolve() if args.source else None).run()
