// Resumable seven-day X search. Credentials stay inside the local xurl CLI.
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import fs from 'node:fs/promises';
const run=promisify(execFile),file=process.env.X_RESEARCH_FILE||'outputs/x-week.json';
const resume=process.argv.includes('--resume');
let result;
if(resume){result=JSON.parse(await fs.readFile(file,'utf8'));if(result.complete){console.log('This search is already complete.');process.exit(0);}}
else{const end=new Date(Date.now()-60000),start=new Date(end.getTime()-7*86400000+120000);result={query:process.argv[2]||'("Agent ID" OR AgentID OR #MyAgentID OR "Agent Identity" OR "Agentic ID" OR "代理ID" OR "代理 ID") -is:retweet',start:start.toISOString().replace(/\.\d{3}Z/,'Z'),end:end.toISOString().replace(/\.\d{3}Z/,'Z'),data:[],includes:{users:[],media:[]},pages:0,nextToken:null,complete:false};}
await fs.mkdir(file.slice(0,file.lastIndexOf('/'))||'.',{recursive:true});
const save=()=>fs.writeFile(file,JSON.stringify(result,null,2));
while(true){const q=new URLSearchParams({query:result.query,start_time:result.start,end_time:result.end,max_results:'100','tweet.fields':'created_at,entities,attachments,author_id,note_tweet,referenced_tweets',expansions:'author_id,attachments.media_keys','user.fields':'username,name','media.fields':'url,preview_image_url,alt_text,type',sort_order:'recency'});if(result.nextToken)q.set('next_token',result.nextToken);
 let page;try{const {stdout}=await run('xurl',['/2/tweets/search/recent?'+q],{timeout:90000,maxBuffer:5000000});page=JSON.parse(stdout);}catch(e){let body;try{body=JSON.parse(e.stdout);}catch{}result.failure=body?.detail||'X API request failed; cursor preserved';result.complete=false;await save();console.error(result.failure);process.exitCode=1;break;}
 if(!Array.isArray(page.data)){if(page.meta?.result_count===0){result.complete=true;result.nextToken=null;await save();break;}result.failure=page.detail||'Unexpected API response';await save();process.exitCode=1;break;}
 const posts=new Map(result.data.map(p=>[p.id,p]));for(const p of page.data)posts.set(p.id,p);result.data=[...posts.values()];for(const [kind,key] of [['users','id'],['media','media_key']]){const m=new Map(result.includes[kind].map(v=>[v[key],v]));for(const v of page.includes?.[kind]||[])m.set(v[key],v);result.includes[kind]=[...m.values()];}result.pages++;result.nextToken=page.meta?.next_token||null;result.complete=!result.nextToken;delete result.failure;await save();console.log(JSON.stringify({pages:result.pages,posts:result.data.length,complete:result.complete}));if(result.complete)break;}
console.log(`Saved ${file}; complete=${result.complete}. This is research data; import reviewed batches of at most 100 posts through the website.`);
