import type {ActivitySummary} from '@/lib/activity-types';
import registryData from '@/data/registry.json';
import evidenceData from '@/data/evidence.json';
export type Evidence={id:string;name:string;xHandle:string;sourceUrl:string;excerpt:string;status:string;publishedAt?:string|null;collectedAt:string;displayName?:string;sourceType?:string;chainVerified?:boolean;extractionMethods?:string[];matchedText?:string;mediaUrl?:string|null;sourceOrigin?:string;sourceConfidence?:string;sourceSnapshotAt?:string;nameRegistered?:boolean;reviewNote?:string};
export type Agent={name:string;owner:string;source:string;chainVerified:boolean;block?:number;registeredAt?:number;tx?:string;tradeCount?:number;buyCount?:number;sellCount?:number;activity?:ActivitySummary};
export const registry=registryData as Agent[],seedEvidence=evidenceData as Evidence[];
export const REGISTRY='0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F';
export const normalize=(s:string)=>s.trim().toLowerCase().replace(/\.ai$/,'')+'.ai';
export const validName=(s:string)=>/^[a-z0-9-]{3,32}\.ai$/.test(s);
export async function boundedJson(url:string,init:RequestInit={},limit=1500000){
 const r=await fetch(url,{...init,signal:AbortSignal.timeout(12000)});if(!r.ok)throw new Error(`数据源返回 HTTP ${r.status}`);if(Number(r.headers.get('content-length')||0)>limit)throw new Error('数据源响应过大');
 const reader=r.body?.getReader();if(!reader)throw new Error('数据源为空');let size=0;const chunks:Uint8Array[]=[];
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();throw new Error('数据源响应超过限制');}chunks.push(value);}}finally{reader.releaseLock();}
 const all=new Uint8Array(size);let offset=0;for(const c of chunks){all.set(c,offset);offset+=c.length;}return JSON.parse(new TextDecoder().decode(all));
}
export async function chainHandle(owner:string){
 if(!/^0x[a-f0-9]{40}$/i.test(owner))throw new Error('钱包地址格式不正确');let last='链上节点暂不可用';
 for(const rpc of ['https://bsc-dataseed2.binance.org','https://bsc-dataseed.binance.org']){try{const x=await boundedJson(rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'eth_call',params:[{to:REGISTRY,data:'0xc50a1514'+owner.slice(2).toLowerCase().padStart(64,'0')},'latest']})},10000);if(x.error)throw new Error(x.error.message);const hex=String(x.result).slice(2);if(hex.length<128)throw new Error('无效链上响应');const offset=parseInt(hex.slice(0,64),16)*2,len=parseInt(hex.slice(offset,offset+64),16);if(!Number.isFinite(len)||len>256)throw new Error('名称长度无效');return new TextDecoder().decode(Uint8Array.from((hex.slice(offset+64,offset+64+len*2).match(/.{2}/g)||[]).map(x=>parseInt(x,16))));}catch(e){last=e instanceof Error?e.message:last;}}
 throw new Error(last);
}
export async function resolveAgent(input:string){
 const q=input.trim();if(/^0x[a-f0-9]{40}$/i.test(q)){const h=await chainHandle(q);return h?{name:h+'.ai',owner:q.toLowerCase(),source:'BSC RPC',chainVerified:true,checkedAt:new Date().toISOString()}:null;}
 const name=normalize(q);if(!validName(name))throw new Error('请输入3–32位 Agent ID 或完整 EVM 地址');const known=registry.find(a=>a.name===name);
 if(known){const h=await chainHandle(known.owner);if(h.toLowerCase()!==name.slice(0,-3))throw new Error('当前链上记录与目录快照不一致');return {...known,chainVerified:true,source:'BSC RPC',checkedAt:new Date().toISOString()};}
 const x=await boundedJson('https://bnb.fan/api/agent-id/search?q='+encodeURIComponent(name),{},200000);if(!x.ok)throw new Error('参考索引暂未返回有效结果');if(x.status!=='taken'||!x.claim)return null;const h=await chainHandle(x.claim.owner);if(h.toLowerCase()!==name.slice(0,-3))throw new Error('参考索引与链上名称不一致');return {name,owner:String(x.claim.owner).toLowerCase(),registeredAt:x.claim.ts,tx:x.claim.tx,source:'bnb.fan + BSC RPC',chainVerified:true,checkedAt:new Date().toISOString()};
}
export function extractX(data:unknown):Evidence[]{
 const x=data as {data?:Record<string,unknown>[];includes?:{users?:{id:string;username:string;name?:string}[]}};if(!x||!Array.isArray(x.data)||x.data.length>100)throw new Error('请导入最多100条的 xurl / X API JSON，需包含 data 和 includes.users');const users=new Map((x.includes?.users||[]).map(u=>[u.id,u]));const output:Evidence[]=[];
 for(const p of x.data){const note=p.note_tweet as {text?:string;entities?:{urls?:{display_url?:string;expanded_url?:string;unwound_url?:string}[]}}|undefined;const text=String(note?.text||p.text||'');const ent=(note?.entities||p.entities) as {urls?:{display_url?:string;expanded_url?:string;unwound_url?:string}[]}|undefined;const urls=(ent?.urls||[]).map(u=>[u.display_url,u.expanded_url,u.unwound_url].filter(Boolean).join(' ')).join(' ');const body=text+' '+urls;if(!/agent\s*(id|ic|identity)|#MyAgentID|代理\s*ID|我的.*ID/i.test(body))continue;const u=users.get(String(p.author_id));if(!u||!/^\w{1,15}$/.test(u.username)||!/^\d{5,25}$/.test(String(p.id)))continue;const shareNames=[...urls.matchAll(/https?:\/\/web3\.binance\.com\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?agent-id\/([a-z0-9-]{3,32})(?=[/?#\s]|$)/gi)].map(m=>m[1].toLowerCase()+'.ai');const plainNames=[...body.matchAll(/(?<![\w./@-])([a-z0-9-]{3,32})\.ai\b/gi)].map(m=>m[1].toLowerCase()+'.ai');const own=/my.{0,30}agent.{0,8}id|我的.{0,15}(id|身份)|我申请了|我注册了/i.test(text);for(const name of new Set([...shareNames,...(own?plainNames:[])])){if(!validName(name)||['gmgn.ai','openai.ai','xxx.ai','registered.ai','asksurf.ai','authsec.ai'].includes(name))continue;output.push({id:String(p.id)+'-'+name.slice(0,-3),name,xHandle:u.username,sourceUrl:`https://x.com/${u.username}/status/${p.id}`,excerpt:[...text].slice(0,130).join(''),status:'candidate',publishedAt:typeof p.created_at==='string'?p.created_at:null,collectedAt:new Date().toISOString(),sourceType:'x',extractionMethods:[shareNames.includes(name)?'binance_share_link':text.toLowerCase().includes(name)?'text':'expanded_url'],matchedText:name,reviewNote:'自动导入，尚未经人工核实；图片需另行OCR分析'});}}
 return output.slice(0,100);
}
