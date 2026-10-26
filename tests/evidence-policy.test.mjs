import assert from 'node:assert/strict';
import test from 'node:test';
import {queryAgents} from '../lib/agent-query.mjs';
import {compareEvidence,isAssociationEvidence,strengthLabel} from '../lib/evidence-policy.mjs';
const agents=['alice.ai','bob.ai','carol.ai'].map(name=>({name,owner:'0x111',chainVerified:true}));
const evidence=[{name:'alice.ai',xHandle:'shared',associationStrength:'weak',status:'self_declared'},{name:'bob.ai',xHandle:'best',associationStrength:'strongest',status:'candidate'},{name:'carol.ai',xHandle:'excluded',associationStrength:'excluded'}];
test('strongest associations outrank reviewed weak ones without changing reviews',()=>{
 assert.deepEqual(queryAgents(agents,evidence,new URLSearchParams()).items.map(a=>a.name),['bob.ai','alice.ai','carol.ai']);assert.equal([...evidence].sort(compareEvidence)[0].name,'bob.ai');assert.equal(evidence[0].status,'self_declared');
});
test('multi-name images never enter X search or linked filters',()=>{
 assert.equal(queryAgents(agents,evidence,new URLSearchParams({q:'excluded'})).total,0);assert.equal(queryAgents(agents,evidence,new URLSearchParams({filter:'有 X 线索'})).total,2);assert.equal(evidence.filter(isAssociationEvidence).length,2);
});
test('strength filters use the same rules for paginated API and complete CSV results',()=>{
 for(const format of ['', 'csv']){assert.equal(queryAgents(agents,evidence,new URLSearchParams({filter:'最强关联',format})).items[0].name,'bob.ai');assert.equal(queryAgents(agents,evidence,new URLSearchParams({filter:'仅弱相关',format})).items[0].name,'alice.ai');}
 assert.equal(strengthLabel({sourceConfidence:'high'}),'弱相关证据');
});
