import type {Agent,Evidence} from './atlas';
export function queryAgents(agents:Agent[],evidence:Evidence[],params:URLSearchParams):{items:Agent[];total:number;page:number;pages:number};
