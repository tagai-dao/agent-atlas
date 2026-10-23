import {allAgents} from '@/lib/server-agents';
import {seedEvidence} from '@/lib/atlas';
import {queryAgents} from '@/lib/agent-query.mjs';
export const dynamic='force-dynamic';
export function GET(req:Request){
 const p=new URL(req.url).searchParams;
 if(p.get('format')==='csv'){
 const rows=[['Agent ID','Wallet','Token trades','Internal trades','DEX trades','NFT minted','NFT mint transactions']];
 for(const a of queryAgents(allAgents,seedEvidence,p).items)rows.push([a.name,a.owner,String(a.activity?.tokenTrades??a.tradeCount??0),String(a.activity?.innerTrades||0),String(a.activity?.outerTrades||0),String(a.activity?.nftMintCount||0),String(a.activity?.nftMintTransactions||0)]);
 return new Response('\uFEFF'+rows.map(row=>row.map(s=>'"'+(/^[=+@-]/.test(s)?"'":'')+s.replaceAll('"','""')+'"').join(',')).join('\r\n'),{headers:{'content-type':'text/csv;charset=utf-8','content-disposition':'attachment; filename="agent-atlas.csv"'}});
 }
 return Response.json({...queryAgents(allAgents,seedEvidence,p),counts:{identities:allAgents.length,aipro:allAgents.filter(a=>a.tradeCount||a.activity?.tokens.some(t=>t.symbol==='AIPRO')).length}},{headers:{'cache-control':'public, max-age=60'}});
}
