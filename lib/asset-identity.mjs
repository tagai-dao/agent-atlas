export const LEGACY_ASSETS=Object.freeze({AIPRO:'0xfa81c13f979f0dff4a40b68c4aba147fa0723333','.ai':'0x7ffcf7b3b52adcc00c76f50ce2e37bf3c7e215dc',GANG:'0x0c6302401aa5325c2e36f170f52c00b1d220b405',Flaip:'0xb8fb293b3e8e3c5fd741e34ac5810dd5dc9f2c7f','Relic NFT':'0xe8c6b38b5e63377a96b268319b66638f772254bb'});
export function assetId(row){return (row.assetId||row.address||LEGACY_ASSETS[row.asset||row.symbol]||'').toLowerCase();}
export function matchesAsset(row,selector){if(selector==='全部')return true;const target=LEGACY_ASSETS[selector]||selector.toLowerCase();return assetId(row)===target;}
