import manifest from '@/public/holdings/manifest.json';
export function GET(){return Response.json({...manifest,paths:{wallets:'/holdings/wallets/{owner-prefix}.json',names:'/holdings/names/{sha256-name-prefix}.json',holders:'/holdings/holders/{assetId}/{page}.json',csv:'/holdings/balances.csv'}},{headers:{'cache-control':'public, max-age=60'}});}
