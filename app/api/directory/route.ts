import research from '@/data/research.json';
export function GET(){return Response.json({storageAvailable:false,research},{headers:{'cache-control':'public, max-age=60'}});}
