'use client';
import {useEffect,useState} from 'react';
import {ArrowUpRight,Search,Download,Wallet,Layers,Users,Clock} from 'lucide-react';
import data from '@/public/holdings/manifest.json';
import {fetchJson} from '@/lib/client-fetch';
import type {Agent} from '@/lib/atlas';
import type {HoldingsManifest,HoldingsShard,WalletHoldingsData,HolderPage} from '@/lib/holdings-types';
const manifest=data as HoldingsManifest;
const short=(s:string)=>s==='native'?'BNB':s.slice(0,6)+'…'+s.slice(-4);
const number=(s:string)=>{const [whole,part]=s.split('.');return BigInt(whole).toLocaleString('zh-CN')+(part?'.'+part.slice(0,8)+(part.length>8?'…':''):'');};
const bnbTotal=manifest.assets[0].totalAmount;
const bnbMetric=BigInt(bnbTotal.split('.')[0]).toLocaleString('zh-CN')+(bnbTotal.includes('.')?'.'+bnbTotal.split('.')[1].slice(0,4):'');
const date=new Date(manifest.snapshotTime).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'});
async function walletSnapshot(owner:string,signal?:AbortSignal){
 const shard=await fetchJson<HoldingsShard>('/holdings/wallets/'+owner.slice(2,4)+'.json?v='+manifest.snapshotBlock,signal);
 if(shard.snapshotBlock!==manifest.snapshotBlock)throw Error('快照已更新，请刷新页面后重试');
 return shard.wallets[owner]||null;
}
export function WalletHoldings({owner}:{owner:string}){
 const [row,setRow]=useState<WalletHoldingsData|null>(null),[state,setState]=useState('loading'),[retry,setRetry]=useState(0);
 useEffect(()=>{const c=new AbortController();setRow(null);setState('loading');
 if(!/^0x[0-9a-f]{40}$/i.test(owner)){setState('missing');return;}
 void walletSnapshot(owner.toLowerCase(),c.signal).then(r=>{if(!c.signal.aborted){setRow(r);setState(r?'ready':'missing');}}).catch(()=>{if(!c.signal.aborted)setState('error');});return()=>c.abort();},[owner,retry]);
 return <div className="detail-section wallet-holdings"><h3>当前资产持仓 <span className="badge green">BSC 快照</span></h3><p className="muted activity-caption">{date}（北京时间） · 区块 {manifest.snapshotBlock}。仅覆盖 BNB、追踪代币及 Relic NFT；不含曲线份额等未覆盖资产。</p>{state==='loading'?<p>正在读取持仓…</p>:state==='error'?<p role="alert">持仓快照暂不可用。<button onClick={()=>setRetry(v=>v+1)}>重试</button></p>:!row?<p>此地址不在该区块的当前注册钱包集合中；未查询到不代表零余额。</p>:<><p className="muted activity-caption">持仓快照中的注册身份：{row.name}</p><div className="table-scroll"><table><thead><tr><th>资产 / CA</th><th>当前余额</th></tr></thead><tbody>{row.balances.map(b=>{const a=manifest.assets.find(t=>t.address===b.assetId)!;return <tr key={b.assetId}><td><strong>{a.symbol}</strong><small className="activity-wallet">{a.kind==='erc721'?'NFT · ':''}{b.assetId==='native'?'原生资产':<a href={'https://bscscan.com/address/'+b.assetId} target="_blank" rel="noreferrer">{short(b.assetId)}</a>}</small></td><td title={b.amount}>{number(b.amount)} {a.kind==='erc721'?'枚':''}</td></tr>;})}</tbody></table></div>{!row.balances.length&&<p>覆盖范围内的全部资产余额为零。</p>}<p className="muted activity-caption">已读取 {manifest.assets.length} 类资产，表格仅展示非零余额；未列出的已覆盖合约为零。</p></>}</div>;
}
export default function HoldingsHub({onSelect}:{onSelect:(a:Agent)=>void}){
 const [asset,setAsset]=useState('native'),[page,setPage]=useState(1),[rows,setRows]=useState<HolderPage|null>(null),[q,setQ]=useState(''),[found,setFound]=useState<WalletHoldingsData|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 const selected=manifest.assets.find(t=>t.address===asset)!;
 useEffect(()=>{const c=new AbortController();setLoading(true);setRows(null);setError('');void fetchJson<HolderPage>('/holdings/holders/'+asset+'/'+page+'.json?v='+manifest.snapshotBlock,c.signal).then(d=>{if(d.snapshotBlock!==manifest.snapshotBlock)throw Error();if(!c.signal.aborted)setRows(d);}).catch(()=>{if(!c.signal.aborted)setError('持仓列表暂不可用，请重试或刷新页面。');}).finally(()=>{if(!c.signal.aborted)setLoading(false);});return()=>c.abort();},[asset,page,retry]);
 async function search(){setBusy(true);setError('');setFound(null);try{let input=q.trim().toLowerCase(),owner=input;
 if(!/^0x[0-9a-f]{40}$/.test(input)){
 if(!input.endsWith('.ai'))input+='.ai';if(!/^[a-z0-9-]{3,32}\.ai$/.test(input))throw Error('请输入完整 .ai 名称或钱包地址');
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input));const prefix=[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('').slice(0,2);
 const d=await fetchJson<{snapshotBlock:number;names:Record<string,string>}>('/holdings/names/'+prefix+'.json?v='+manifest.snapshotBlock);if(d.snapshotBlock!==manifest.snapshotBlock)throw Error('快照已更新，请刷新页面');owner=d.names[input];if(!owner)throw Error('该快照未找到此注册身份；可能为之后新增或尚未注册。');
 }
 const result=await walletSnapshot(owner);if(!result)throw Error('该区块的当前注册集合中没有此地址；不代表零余额。');setFound(result);
 }catch(e){setError(e instanceof Error?e.message:'持仓查询失败，请重试');}finally{setBusy(false);}}
 const select=(name:string,owner:string)=>onSelect({name,owner,block:manifest.snapshotBlock,chainVerified:true,source:'BSC registry + fixed-block holdings'});
 return <><section className="panel holdings-intro"><strong>全部 BSC .ai 注册钱包 · 每 2 小时同步</strong><p>已核验 {manifest.walletCount.toLocaleString()} 个当前注册钱包，含无交易记录的身份。持仓与交易 / 铸造历史独立统计。</p><p className="muted">资产范围：BNB、{manifest.assets.filter(t=>t.kind==='erc20').length} 个追踪 ERC20 和 Relic NFT；尚未接入全钱包资产发现，不代表钱包所有资产。</p></section><section className="activity-summary">{[[Users,manifest.walletCount.toLocaleString(),'已核验注册钱包'],[Wallet,'≈ '+bnbMetric,'注册钱包合计 BNB'],[Layers,manifest.assets.length,'已覆盖资产类别'],[Clock,'2 小时','自动同步频率']].map(([Icon,n,label])=>{const I=Icon as typeof Wallet;return <article className="panel" key={String(label)}><I size={20}/><strong title={label==='注册钱包合计 BNB'?bnbTotal:undefined}>{String(n)}</strong><span>{String(label)}</span></article>;})}</section>
 <section className="panel holdings-search"><form onSubmit={e=>{e.preventDefault();void search();}}><label><Search size={18}/><input disabled={busy} aria-label="查询资产持仓" placeholder="输入完整 .ai 名称或 0x 钱包地址" value={q} onChange={e=>{setQ(e.target.value);setFound(null);}}/></label><button className="primary-btn" disabled={busy}>{busy?'查询中…':'查询持仓'}</button></form>{found&&<div className="holdings-found"><button onClick={()=>select(found.name,found.owner)}><strong>{found.name}</strong><ArrowUpRight size={16}/></button><WalletHoldings owner={found.owner}/></div>}</section>
 <section className="panel activity-directory"><div className="panel-heading"><h2>资产持有人<span>{selected.rows.toLocaleString()}</span></h2><a className="source-link" href="/holdings/balances.csv" download>导出全部持仓 CSV<Download size={16}/></a></div><div className="activity-controls"><select aria-label="持仓资产" value={asset} onChange={e=>{setAsset(e.target.value);setPage(1);}}>{manifest.assets.map(t=><option value={t.address} key={t.address}>{t.symbol} · {short(t.address)}</option>)}</select><span className="muted">按当前数量排序 · {selected.address==='native'?'含零余额注册钱包':selected.holders.toLocaleString()+' 个非零持有人'} · 合计 {number(selected.totalAmount)} {selected.symbol}</span></div>{asset!=='native'&&<a className="contract-address" href={'https://bscscan.com/address/'+asset} target="_blank" rel="noreferrer">{asset}<ArrowUpRight size={12}/></a>}{error&&<p role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>重试</button></p>}{loading?<p className="empty">正在加载持仓列表…</p>:rows&&<><div className="table-scroll"><table><thead><tr><th>Agent ID / 钱包</th><th>当前持有 {selected.symbol}</th><th/></tr></thead><tbody>{rows.items.map(w=><tr tabIndex={0} key={w.owner} onClick={()=>select(w.name,w.owner)} onKeyDown={e=>{if(e.key==='Enter')select(w.name,w.owner);}}><td><strong>{w.name}</strong><small className="activity-wallet">{short(w.owner)}</small></td><td title={w.amount}>{number(w.amount)} {selected.kind==='erc721'?'枚':''}</td><td><ArrowUpRight size={14}/></td></tr>)}</tbody></table></div><div className="pagination"><span>点击查看钱包持仓及活动</span><div><button disabled={page<=1} onClick={()=>setPage(v=>v-1)}>上一页</button><span>{page} / {rows.pages}</span><button disabled={page>=rows.pages} onClick={()=>setPage(v=>v+1)}>下一页</button></div></div></>}</section>
 <section className="activity-coverage"><h3>持仓覆盖范围与核验方式</h3><p>{date}（北京时间） · BSC 区块 {manifest.snapshotBlock}</p>{manifest.notes.map(n=><p key={n}>{n}</p>)}</section></>;
}
