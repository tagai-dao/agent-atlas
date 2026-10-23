export async function fetchJson<T>(url:string,signal?:AbortSignal):Promise<T>{
 const timeout=AbortSignal.timeout(15000);
 const response=await fetch(url,{signal:signal?AbortSignal.any([signal,timeout]):timeout});
 if(!response.ok)throw new Error(`请求失败（${response.status}）`);
 return response.json() as Promise<T>;
}
