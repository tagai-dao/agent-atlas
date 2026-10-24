import {test} from 'node:test';
import assert from 'node:assert/strict';
import {matchesAsset,assetId,LEGACY_ASSETS} from '../lib/asset-identity.mjs';
import {queryAgents} from '../lib/agent-query.mjs';
const first='0xbdfcd595f1d8d2d9b8c7e9754e2636cf29fd7777',second='0x3437febd7b451a2293787fb84fcdf2f9c9797777';
test('same .ai ticker is isolated by contract and legacy alias stays canonical',()=>{
 const a={symbol:'.ai',address:first},b={asset:'.ai',assetId:second};
 assert.equal(matchesAsset(a,first),true);assert.equal(matchesAsset(b,first),false);assert.equal(matchesAsset(a,'.ai'),false);assert.equal(matchesAsset({symbol:'.ai',address:LEGACY_ASSETS['.ai']},'.ai'),true);assert.equal(assetId(b),second);
});
test('an automatically discovered token named AIPRO cannot enter canonical AIPRO cohort',()=>{
 const fake={name:'fake.ai',owner:'0x'+'1'.repeat(40),activity:{nftMintCount:0,tokens:[{symbol:'AIPRO',address:first,inner:1,outer:0,buys:1,sells:0}]}};
 assert.equal(queryAgents([fake],[],new URLSearchParams({filter:'AIPRO 参与者'})).total,0);
});
test('cohort and direction filters use the selected CA despite duplicate symbols',()=>{
 const agents=[first,second].map((address,i)=>({name:`agent${i}.ai`,owner:'0x'+String(i+1).repeat(40),activity:{nftMintCount:0,lastBlock:1,tokens:[{address,symbol:'.ai',inner:0,outer:1,outerBuys:i===0?1:0,outerSells:i===1?1:0,buys:i===0?1:0,sells:i===1?1:0}]}}));
 const query=p=>queryAgents(agents,[],new URLSearchParams({mode:'activity',...p}));
 assert.equal(query({asset:first,market:'外盘',direction:'仅买入'}).total,1);assert.equal(query({asset:second,market:'外盘',direction:'仅买入'}).total,0);assert.equal(query({asset:second,direction:'仅卖出'}).items[0].name,'agent1.ai');
});
