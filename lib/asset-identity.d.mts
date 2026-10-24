type AssetRef={assetId?:string;address?:string;asset?:string;symbol?:string};
export const LEGACY_ASSETS:Readonly<Record<string,string>>;
export function assetId(row:AssetRef):string;
export function matchesAsset(row:AssetRef,selector:string):boolean;
