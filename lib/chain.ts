// Server-only RPC access. Never import this module from client components.
import {registry,normalize,validName,boundedJson,REGISTRY} from './atlas';
async function chainHandle(owner:string){
 const configured=process.env.BSC_RPC_URL;
 const endpoints=[...(configured?[configured]:[]),'https://bsc-dataseed2.binance.org','https://bsc-dataseed.binance.org'];
 const deadline=Date.now()+12000;
 for(const endpoint of endpoints){try{
 if(new URL(endpoint).protocol!=='https:')continue;
 async function rpc(method:string,params:unknown[]){const remaining=deadline-Date.now();if(remaining<=0)throw Error();const r=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(Math.min(4000,remaining))});if(!r.ok)throw Error();const reader=r.body?.getReader();if(!reader)throw Error();const chunks:Uint8Array[]=[];let size=0;try{while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>12000){await reader.cancel();throw Error();}chunks.push(part.value);}}finally{reader.releaseLock();}const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}const d=JSON.parse(new TextDecoder().decode(bytes));if(d.error||typeof d.result!=='string')throw Error();return d.result as string;}
 const block=await rpc('eth_blockNumber',[]);if(!/^0x[0-9a-f]+$/i.test(block))throw Error();
 const result=await rpc('eth_call',[{to:REGISTRY,data:'0xc50a1514'+owner.slice(2).toLowerCase().padStart(64,'0')},block]);
 const hex=result.slice(2);if(hex.length<128)throw Error();const offset=parseInt(hex.slice(0,64),16)*2,len=parseInt(hex.slice(offset,offset+64),16);if(!Number.isFinite(len)||len>256||hex.length<offset+64+len*2)throw Error();
 const handle=new TextDecoder().decode(Uint8Array.from((hex.slice(offset+64,offset+64+len*2).match(/.{2}/g)||[]).map(x=>parseInt(x,16))));return {handle,block:parseInt(block,16)};
 }catch{/* Do not log upstream URLs: a configured endpoint can contain an API key. */}}
 throw Error('链上节点暂不可用，请稍后重试');
}
export async function resolveAgent(input:string){
 const q=input.trim();
 if(/^0x[a-f0-9]{40}$/i.test(q)){const {handle,block}=await chainHandle(q);return handle?{name:handle+'.ai',owner:q.toLowerCase(),block,source:'BSC RPC',chainVerified:true,checkedAt:new Date().toISOString()}:null;}
 const name=normalize(q);if(!validName(name))throw Error('请输入3–32位 Agent ID 或完整 EVM 地址');let known=registry.find(a=>a.name===name);
 if(!known){const x=await boundedJson('https://bnb.fan/api/agent-id/search?q='+encodeURIComponent(name),{},200000);if(!x.ok)throw Error('参考索引暂未返回有效结果');if(x.status!=='taken'||!x.claim)return null;const owner=String(x.claim.owner);if(!/^0x[a-f0-9]{40}$/i.test(owner))throw Error('参考索引返回地址无效');known={name,owner:owner.toLowerCase(),source:'bnb.fan',chainVerified:false};}
 const {handle,block}=await chainHandle(known.owner);if(handle.toLowerCase()!==name.slice(0,-3))throw Error('当前链上记录与目录快照不一致');return {...known,block,source:'BSC RPC',chainVerified:true,checkedAt:new Date().toISOString()};
}
