import {matchesAsset} from './asset-identity.mjs';
export function queryAgents(agents,evidence,params){
 const q=(params.get('q')||'').slice(0,64).trim().toLowerCase().replace(/^@/,'');
 const mode=params.get('mode')||'directory',filter=params.get('filter')||'全部身份',sort=params.get('sort')||'关联优先';
 const asset=params.get('asset')||'全部',market=params.get('market')||'全部市场',direction=params.get('direction')||'买卖均含';
 const byName=new Map();for(const e of evidence){const es=byName.get(e.name)||[];es.push(e);byName.set(e.name,es);}
 const rows=agents.filter(a=>{
 const es=byName.get(a.name)||[],x=a.activity;
 if(q&&!a.name.includes(q)&&!a.owner.toLowerCase().includes(q)&&!es.some(e=>e.xHandle.toLowerCase().includes(q)))return false;
 if(mode!=='activity')return (filter!=='有 X 线索'||es.length>0)&&(filter!=='待核实'||es.some(e=>e.status==='candidate'))&&(filter!=='AIPRO 参与者'||a.tradeCount||x?.tokens.some(t=>matchesAsset(t,'AIPRO')))&&(filter!=='代币交易'||x?.tokenTrades)&&(filter!=='NFT 铸造'||x?.nftMintCount);
 if(!x)return false;
 const nft=(asset==='全部'||matchesAsset({asset:'Relic NFT'},asset))&&(market==='全部市场'||market==='NFT 铸造')&&direction==='买卖均含'&&x.nftMintCount>0;
 const token=asset!=='Relic NFT'&&market!=='NFT 铸造'&&x.tokens.some(t=>{
 if(asset!=='全部'&&!matchesAsset(t,asset))return false;
 if(market==='内盘')return direction==='仅买入'?t.innerBuys>0:direction==='仅卖出'?t.innerSells>0:t.inner>0;
 if(market==='外盘')return direction==='仅买入'?t.outerBuys>0:direction==='仅卖出'?t.outerSells>0:t.outer>0;
 return direction==='仅买入'?t.buys>0:direction==='仅卖出'?t.sells>0:t.buys+t.sells>0;
 });return nft||token;
 }).sort((a,b)=>mode==='activity'?(b.activity?.lastBlock||0)-(a.activity?.lastBlock||0):sort==='名称 A–Z'?a.name.localeCompare(b.name):sort==='交易次数'?(b.activity?.tokenTrades??b.tradeCount??0)-(a.activity?.tokenTrades??a.tradeCount??0):Number(byName.has(b.name))-Number(byName.has(a.name))||(b.tradeCount||0)-(a.tradeCount||0)||a.name.localeCompare(b.name));
 const size=Math.min(100,Math.max(1,Number(params.get('size'))||20));
 const pages=Math.max(1,Math.ceil(rows.length/size)),page=Math.min(pages,Math.max(1,Math.floor(Number(params.get('page'))||1)));
 return {items:params.get('format')==='csv'?rows:rows.slice((page-1)*size,page*size),total:rows.length,page,pages};
}
