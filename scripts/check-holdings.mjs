import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const dir='public/holdings',read=p=>JSON.parse(fs.readFileSync(`${dir}/${p}`));
const m=read('manifest.json'),activity=JSON.parse(fs.readFileSync('public/activity/manifest.json'));
assert.equal(m.identityCoverage,'all-current-registered-bsc-ai');assert.equal(m.assetCoverage,'tracked-contracts');
assert.ok(m.walletCount>0);assert.equal(m.chainId,56);assert.ok(m.snapshotHash);
const assets=new Map(m.assets.map(a=>[a.address,a]));assert.equal(assets.size,m.assets.length);
for(const t of activity.tokens.filter(t=>t.status!=='curve'))assert.ok(assets.has(t.address),`Missing tracked token ${t.address}`);
assert.ok(assets.has(activity.nft.contract));assert.ok(assets.has('native'));
const wallets=new Map(),names=new Map(),sum=new Map(),holders=new Map();
const unit=(raw,p)=>{if(!p)return raw;const s=raw.padStart(p+1,'0');return (s.slice(0,-p)+'.'+s.slice(-p)).replace(/0+$/,'').replace(/\.$/,'');};
for(let i=0;i<256;i++){
 const prefix=i.toString(16).padStart(2,'0'),s=read(`wallets/${prefix}.json`),n=read(`names/${prefix}.json`);
 assert.equal(s.snapshotBlock,m.snapshotBlock);assert.equal(n.snapshotBlock,m.snapshotBlock);
 for(const [name,owner] of Object.entries(n.names)){assert.equal(crypto.createHash('sha256').update(name).digest('hex').slice(0,2),prefix);assert.ok(!names.has(name));names.set(name,owner);}
 for(const [owner,w] of Object.entries(s.wallets)){
 assert.equal(owner.slice(2,4),prefix);assert.equal(w.owner,owner);assert.ok(!wallets.has(owner));wallets.set(owner,w);
 const seen=new Set();for(const b of w.balances){assert.ok(assets.has(b.assetId));assert.ok(!seen.has(b.assetId));seen.add(b.assetId);assert.ok(BigInt(b.raw)>0n);assert.equal(b.amount,unit(b.raw,assets.get(b.assetId).decimals));sum.set(b.assetId,(sum.get(b.assetId)||0n)+BigInt(b.raw));holders.set(b.assetId,(holders.get(b.assetId)||0)+1);}
 }
}
assert.equal(wallets.size,m.walletCount);assert.equal(names.size,m.walletCount);for(const [owner,w] of wallets)assert.equal(names.get(w.name),owner);
for(const a of assets.values()){
 assert.equal(a.totalRaw,String(sum.get(a.address)||0n));assert.equal(a.holders,holders.get(a.address)||0);assert.equal(a.totalAmount,unit(a.totalRaw,a.decimals));
 if(a.totalSupplyRaw!==null)assert.ok(BigInt(a.totalRaw)<=BigInt(a.totalSupplyRaw),'Holdings exceed token supply');
 const seen=new Set();let previous=null,total=0;
 for(let p=1;p<=a.pages;p++){
 const page=read(`holders/${a.address}/${p}.json`);assert.equal(page.snapshotBlock,m.snapshotBlock);assert.equal(page.assetId,a.address);assert.equal(page.page,p);assert.equal(page.total,a.rows);
 for(const row of page.items){assert.ok(!seen.has(row.owner));seen.add(row.owner);const w=wallets.get(row.owner);assert.equal(row.name,w.name);const b=w.balances.find(b=>b.assetId===a.address);assert.equal(row.raw,b?.raw||'0');assert.equal(row.amount,unit(row.raw,a.decimals));if(previous!==null)assert.ok(previous>=BigInt(row.raw));previous=BigInt(row.raw);total++;}
 }
 assert.equal(total,a.address==='native'?m.walletCount:a.holders);
}
console.log(`Holdings validated: ${m.walletCount} registered wallets, ${assets.size} assets, block ${m.snapshotBlock}`);
