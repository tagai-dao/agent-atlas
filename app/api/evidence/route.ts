import {seedEvidence} from '@/lib/atlas';
import {compareEvidence} from '@/lib/evidence-policy.mjs';
export function GET(req:Request){
 const p=new URL(req.url).searchParams,strength=p.get('strength'),q=(p.get('q')||'').slice(0,64).toLowerCase().replace(/^@/,'');
 const rows=seedEvidence.filter(e=>(!strength||(e.associationStrength||'weak')===strength)&&(!q||[e.name,e.xHandle,e.excerpt].some(s=>s.toLowerCase().includes(q)))).sort(compareEvidence);
 const size=Math.min(100,Math.max(1,Number(p.get('size'))||30)),pages=Math.max(1,Math.ceil(rows.length/size)),page=Math.min(pages,Math.max(1,Math.floor(Number(p.get('page'))||1)));
 return Response.json({items:rows.slice((page-1)*size,page*size),total:rows.length,page,pages},{headers:{'cache-control':'public, max-age=60'}});
}
export async function POST(){return Response.json({error:'当前部署为公开只读模式'},{status:403});}
