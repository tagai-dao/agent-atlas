export type HoldingAsset={address:string;symbol:string;name:string;kind:string;decimals:number;totalSupplyRaw:string|null;holders:number;totalRaw:string;totalAmount:string;rows:number;pages:number};
export type HoldingsManifest={schemaVersion:number;chainId:number;snapshotBlock:number;snapshotHash:string;snapshotTime:string;walletCount:number;identityCoverage:string;assetCoverage:string;assets:HoldingAsset[];notes:string[]};
export type WalletHoldingsData={owner:string;name:string;balances:{assetId:string;raw:string;amount:string}[]};
export type HoldingsShard={snapshotBlock:number;wallets:Record<string,WalletHoldingsData>};
export type HolderPage={snapshotBlock:number;assetId:string;items:{owner:string;name:string;raw:string;amount:string}[];total:number;page:number;pages:number};
