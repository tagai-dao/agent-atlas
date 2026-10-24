"""Read immutable transaction senders with bounded batches and safe retries.

Only eth_getTransactionByHash is used here, never contract reads or signing.
Provider errors are deliberately not included in exceptions (URLs can be secret).
"""
import re
import time

ADDRESS=re.compile(r'0x[0-9a-fA-F]{40}')

def fetch_senders(hashes, head, endpoints, post, save, sleep=time.sleep):
    missing=set(hashes)
    endpoints=list(dict.fromkeys(endpoints))
    for attempt,size in enumerate((20,10,5,1,1)):
        endpoint=endpoints[0] if attempt<2 else endpoints[-1]
        pending=sorted(missing)
        for start in range(0,len(pending),size):
            chunk=pending[start:start+size]
            expected=dict(enumerate(chunk))
            request=[{'jsonrpc':'2.0','id':i,'method':'eth_getTransactionByHash','params':[h]} for i,h in expected.items()]
            try:
                rows=post(endpoint,request)
                if not isinstance(rows,list):continue
                for row in rows:
                    tx=row.get('result');h=expected.get(row.get('id'))
                    if h not in missing or not isinstance(tx,dict):continue
                    if tx.get('hash','').lower()!=h.lower():continue
                    sender=tx.get('from','');recipient=tx.get('to') or ''
                    if not ADDRESS.fullmatch(sender) or recipient and not ADDRESS.fullmatch(recipient):continue
                    block=tx.get('blockNumber')
                    if not isinstance(block,str) or not block.startswith('0x'):continue
                    block=int(block,16)
                    if block>head:continue
                    save(h,{'from':sender.lower(),'to':recipient.lower(),'block':block})
                    missing.remove(h)
            except Exception:
                pass
        if not missing:return
        sleep(attempt+1)
    raise RuntimeError(f'Missing transaction senders after bounded retries: {len(missing)}')
