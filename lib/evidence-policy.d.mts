import type {Evidence} from './atlas';
export function isAssociationEvidence(e:Evidence):boolean;
export function strengthRank(e:Evidence):number;
export function strengthLabel(e:Evidence):string;
export function strengthReason(e:Evidence):string;
export function compareEvidence(a:Evidence,b:Evidence):number;
