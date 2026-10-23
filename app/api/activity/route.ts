import feed from '@/public/activity/feed.json';
import {seedEvidence} from '@/lib/atlas';
export function GET(req:Request){
 const p=new URL(req.url).searchParams,q=(p.get('q')||'').toLowerCase().replace(/^@/,'').slice(0,64),asset=p.get('asset')||'全部',market=p.get('market')||'全部市场',direction=p.get('direction')||'买卖均含';
 const names=new Set(seedEvidence.filter(e=>e.xHandle.toLowerCase().includes(q)).map(e=>e.name));
 const venue=(v:string)=>v==='inner'?'内盘':v==='outer'?'外盘':'NFT 铸造';
 const items=feed.filter(r=>(asset==='全部'||r.asset===asset)&&(market==='全部市场'||venue(r.venue)===market)&&(direction==='买卖均含'||direction==='仅买入'&&r.direction==='buy'||direction==='仅卖出'&&r.direction==='sell')&&(!q||r.name.includes(q)||r.owner.includes(q)||names.has(r.name))).slice(0,20);
 return Response.json(items,{headers:{'cache-control':'public, max-age=60'}});
}
