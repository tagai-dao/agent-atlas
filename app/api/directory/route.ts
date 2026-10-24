import research from '@/data/research.json';
import activity from '@/public/activity/manifest.json';
export function GET(){return Response.json({storageAvailable:false,research,activity:{snapshotBlock:activity.snapshotBlock,snapshotTime:activity.snapshotTime,totals:activity.totals,tokens:activity.tokens,nft:activity.nft,discovery:activity.discovery}},{headers:{'cache-control':'public, max-age=60'}});}
