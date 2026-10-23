import {resolveAgent} from '@/lib/chain';export const dynamic='force-dynamic';
export async function GET(req:Request){try{const q=new URL(req.url).searchParams.get('q')||'';if(q.length>64)throw new Error('查询过长');return Response.json({agent:await resolveAgent(q)},{headers:{'cache-control':'no-store'}});}catch(e){return Response.json({error:e instanceof Error?e.message:'查询失败'},{status:502});}}
