import {getDb} from '@/db';import {evidence} from '@/db/schema';import {registry,seedEvidence} from '@/lib/atlas';
import research from '@/data/research.json';
export const dynamic='force-dynamic';
export async function GET(){let records=seedEvidence;let storageAvailable=true;try{const saved=await getDb().select().from(evidence).limit(1000);const all=new Map(seedEvidence.map(e=>[e.id,e]));for(const e of saved)all.set(e.id,e);records=[...all.values()].filter(e=>e.status!=='rejected');}catch{storageAvailable=false;}return Response.json({agents:registry,evidence:records,storageAvailable,research,dataAsOf:'2026-10-23',limitations:'X公开内容不等同于钱包控制权证明。'+research.limitReason},{headers:{'cache-control':'no-store'}});}
