import research from '@/data/research.json';
import activity from '@/public/activity/manifest.json';
import holdings from '@/public/holdings/manifest.json';
export function GET(){return Response.json({storageAvailable:false,research,holdings,activity:{snapshotBlock:activity.snapshotBlock,snapshotTime:activity.snapshotTime,totals:activity.totals,tokens:activity.tokens,nft:activity.nft,discovery:activity.discovery}},{headers:{'cache-control':'public, max-age=60'}});}
