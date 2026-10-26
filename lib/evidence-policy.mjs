// Source confidence and manual review are independent of association strength.
export const isAssociationEvidence=e=>e.associationStrength!=='excluded';
export const strengthRank=e=>e.associationStrength==='strongest'?2:isAssociationEvidence(e)?1:0;
export const strengthLabel=e=>e.associationStrength==='strongest'?'最强关联证据':e.associationStrength==='excluded'?'不作为关联证据':'弱相关证据';
export const strengthReason=e=>({own_single_identity_image:'作者发布的单张、单一 .ai 身份图片',author_display_name:'作者 X 显示名明确写有该 .ai',multi_identity_image:'图片中有多个 .ai，图片证据已排除',multiple_images:'包含多张图片，图片证据已排除',other_or_incomplete_evidence:'正文、链接、引用或图片信息不完整，仅作弱相关'})[(e.associationReasons||[])[0]]||'公开内容线索，非钱包控制权证明';
export function compareEvidence(a,b){return strengthRank(b)-strengthRank(a)||Number(b.status==='self_declared')-Number(a.status==='self_declared')||(b.publishedAt||'').localeCompare(a.publishedAt||'');}
