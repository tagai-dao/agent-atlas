import activityData from '@/public/activity/agents.json';
import {registry,seedEvidence,type Agent} from './atlas';
const map=new Map<string,Agent>(registry.map(a=>[a.name,a]));
for(const a of activityData as Agent[]){const old=map.get(a.name);map.set(a.name,{...old,...a,...(old&&Number(old.block)>Number(a.block)?{owner:old.owner,block:old.block,source:old.source}: {})});}
for(const e of seedEvidence)if(!map.has(e.name))map.set(e.name,{name:e.name,owner:'',source:'X公开声明',chainVerified:false});
export const allAgents=[...map.values()];
