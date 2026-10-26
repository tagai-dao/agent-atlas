'use client';
import {useId,useMemo,useState} from 'react';
import {Download,TrendingUp} from 'lucide-react';
import history from '@/public/holdings/registrations.json';

const number=(n:number)=>n.toLocaleString('zh-CN');
const stamp=new Date(history.snapshotTime).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
export default function RegistrationTrend(){
 const [range,setRange]=useState('30'),[point,setPoint]=useState<number|null>(null);
 const id=useId().replaceAll(':','');
 const rows=useMemo(()=>range==='all'?history.days:history.days.slice(-Number(range)),[range]);
 const selected=rows[Math.min(point??rows.length-1,rows.length-1)];
 const peak=Math.max(1,...rows.map(r=>r.registrations));
 const step=10**Math.floor(Math.log10(peak));
 const max=Math.max(4,Math.ceil(peak/(4*step))*4*step);
 const x=(i:number)=>rows.length===1?500:i/(rows.length-1)*1000;
 const y=(n:number)=>220-n/max*200;
 const line=rows.map((r,i)=>`${i?'L':'M'}${x(i)},${y(r.registrations)}`).join(' ');
 const latest=history.days.at(-1)!;
 const yesterday=history.days.at(-2);
 const selectedIndex=rows.indexOf(selected);
 const pct=rows.length===1?50:selectedIndex/(rows.length-1)*100;
 return <section className="panel registration-trend" aria-labelledby="registration-title">
  <div className="registration-heading"><div><div className="eyebrow"><TrendingUp size={12}/> REGISTRATION GROWTH</div><h2 id="registration-title">每日新注册 Agent ID</h2><p>链上首次注册 · 按北京时间（UTC+8）统计</p></div><div className="registration-actions"><div className="registration-ranges" role="group" aria-label="注册趋势时间范围">{[['7','近7天'],['30','近30天'],['all','全部']].map(([value,label])=><button key={value} aria-pressed={range===value} onClick={()=>{setRange(value);setPoint(null);}}>{label}</button>)}</div><a href="/holdings/registrations.csv" download aria-label="下载每日注册 CSV"><Download size={14}/><span>CSV</span></a></div></div>
  <div className="registration-stats"><div><span>累计首次注册</span><strong>{number(history.totalRegistrations)}<small>个</small></strong></div><div><span>{yesterday?`${yesterday.date.slice(5).replace('-','/')} 新增（完整日）`:'前一日新增'}</span><strong>{yesterday?number(yesterday.registrations):'—'}<small>个</small></strong></div><div><span>{latest.date.slice(5).replace('-','/')} 新增 · 截至 {stamp.split(' ').at(-1)}</span><strong>{number(latest.registrations)}<small>个</small></strong></div></div>
  <div className="registration-chart" role="group" tabIndex={0} aria-label="每日注册走势图，使用左右方向键查看每天的数据" onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();setPoint(e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,selectedIndex+(e.key==='ArrowLeft'?-1:1))));}}}>
   <div className="registration-axis" aria-hidden="true">{[1,.75,.5,.25,0].map(v=><span key={v} style={{top:`${(220-v*200)/220*100}%`}}>{number(max*v)}</span>)}</div>
   <div className="registration-plot" onPointerMove={e=>{const rect=e.currentTarget.getBoundingClientRect();setPoint(Math.round(Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width))*(rows.length-1)));}} onPointerDown={e=>{const rect=e.currentTarget.getBoundingClientRect();setPoint(Math.round(Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width))*(rows.length-1)));}} onPointerLeave={()=>setPoint(null)}>
    <svg viewBox="0 0 1000 220" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#fe913f" stopOpacity=".24"/><stop offset="100%" stopColor="#fe913f" stopOpacity=".015"/></linearGradient></defs>{[1,.75,.5,.25,0].map(v=><line key={v} x1="0" x2="1000" y1={y(max*v)} y2={y(max*v)} stroke="#eee7e0" strokeDasharray="4 5" vectorEffect="non-scaling-stroke"/>)}<path d={`${line} L${x(rows.length-1)},220 L${x(0)},220 Z`} fill={`url(#${id})`}/><path d={line} fill="none" stroke="#f68c3c" strokeWidth="2.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke"/><line x1={x(selectedIndex)} x2={x(selectedIndex)} y1="0" y2="220" stroke="#edb892" strokeDasharray="3 5" vectorEffect="non-scaling-stroke"/><ellipse cx={x(selectedIndex)} cy={y(selected.registrations)} rx="4" ry="4" fill="#f68c3c" stroke="white" strokeWidth="2" vectorEffect="non-scaling-stroke"/></svg>
    <div className="registration-tooltip" style={{left:`clamp(85px, ${pct}%, calc(100% - 85px))`}} aria-live="polite" aria-atomic="true"><span>{selected.date.replaceAll('-','/')} {!selected.complete&&'· 未结束'}</span><strong>新增 {number(selected.registrations)} 个</strong></div>
    <div className="registration-dates" aria-hidden="true"><span>{rows[0].date.slice(5).replace('-','/')}</span>{rows.length>2&&<span>{rows[Math.floor((rows.length-1)/2)].date.slice(5).replace('-','/')}</span>}<span>{rows.at(-1)!.date.slice(5).replace('-','/')}</span></div>
   </div>
  </div>
  <div className="registration-footnote"><p>截至 {stamp}（北京时间）。每个名称的链上 ID 仅在首次注册时计入；转移、销毁及同一 ID 再次铸造不计新增。最新一天尚未结束，每两小时随持仓快照更新。</p><details><summary>查看每日明细与统计来源</summary><p>官方 BSC 注册合约：<a href={`https://bscscan.com/address/${history.registry}`} target="_blank" rel="noreferrer">{history.registry}</a> · 快照区块 {history.snapshotBlock.toLocaleString('zh-CN')}。从部署区块完整重放 ERC721 Transfer，按精确区块时间归入自然日；累计注册包含后来被销毁的身份，与当前有效身份数口径不同。</p><div className="registration-table"><table><thead><tr><th>日期（北京时间）</th><th>新注册</th><th>累计首次注册</th><th>日完整性</th></tr></thead><tbody>{[...history.days].reverse().map(r=><tr key={r.date}><td>{r.date}</td><td>{number(r.registrations)}</td><td>{number(r.cumulative)}</td><td>{r.complete?'完整日':`截至 ${stamp}`}</td></tr>)}</tbody></table></div></details></div>
 </section>;
}
