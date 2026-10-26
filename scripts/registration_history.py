"""Daily first registrations from complete ERC721 registry history, in UTC+8.

Historical block headers locate exact day boundaries with binary search. No
wallet balances, contract calls, timestamp estimates or transaction samples.
"""
import bisect
import csv
import datetime as dt
import json
from pathlib import Path

REGISTRY = '0x60b9262456de011f7d15a54cdd8c48baaa8b022f'
DEPLOY = 127950748
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ZONE = dt.timezone(dt.timedelta(hours=8))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    temp.replace(path)


def build_history(logs, anchor, rpc, out, previous=None, deploy=DEPLOY):
    out = Path(out)
    cache_path = out / 'registration-blocks.json'
    boundary_path = out / 'registration-boundaries.json'
    def cached(name):
        p = out / name
        if not p.exists() and previous:
            p = Path(previous) / name
        return json.loads(p.read_text()) if p.exists() else {}
    headers = cached(cache_path.name)
    boundaries = cached(boundary_path.name)
    head = anchor['number']
    def header(n):
        assert deploy <= n <= head, 'Registration header outside fixed snapshot'
        if str(n) not in headers:
            b = rpc('eth_getBlockByNumber', [hex(n), False])
            assert int(b['number'], 16) == n and b.get('hash')
            headers[str(n)] = {'hash': b['hash'], 'timestamp': int(b['timestamp'], 16)}
            save(cache_path, headers)
        return headers[str(n)]
    # Recheck the anchor even when restoring a cached day-boundary search.
    live = rpc('eth_getBlockByNumber', [hex(head), False])
    assert live['hash'] == anchor['hash'] and int(live['timestamp'], 16) == anchor['timestamp']
    headers[str(head)] = {'hash': anchor['hash'], 'timestamp': anchor['timestamp']}
    first, last = {}, set()
    mint_events = 0
    for row in sorted(logs, key=lambda r: (int(r['blockNumber'], 16), int(r['logIndex'], 16))):
        assert row['address'].lower() == REGISTRY and not row.get('removed')
        assert len(row['topics']) == 4 and row['topics'][0].lower() == TRANSFER
        block = int(row['blockNumber'], 16)
        assert deploy <= block <= head
        key = (row['transactionHash'], row['logIndex'])
        assert key not in last, 'Duplicate registry event'
        last.add(key)
        if int(row['topics'][1], 16) == 0:
            assert int(row['topics'][2], 16) != 0
            mint_events += 1
            first.setdefault(row['topics'][3].lower(), block)
    start_day = dt.datetime.fromtimestamp(header(deploy)['timestamp'], ZONE).date()
    last_day = dt.datetime.fromtimestamp(anchor['timestamp'], ZONE).date()
    days = [start_day + dt.timedelta(days=i) for i in range((last_day-start_day).days+1)]
    starts = [deploy]
    for day in days[1:]:
        target = int(dt.datetime.combine(day, dt.time(), ZONE).timestamp())
        key = str(target)
        if key in boundaries:
            block = boundaries[key]
            assert deploy < block <= head
        else:
            lo, hi = starts[-1], head + 1
            while lo < hi:
                mid = (lo + hi) // 2
                if header(mid)['timestamp'] < target:
                    lo = mid + 1
                else:
                    hi = mid
            block = lo
        assert header(block-1)['timestamp'] < target <= header(block)['timestamp'], 'Inexact daily boundary'
        boundaries[key] = block
        starts.append(block)
        save(boundary_path, boundaries)
    counts = [0] * len(days)
    for block in first.values():
        counts[bisect.bisect_right(starts, block)-1] += 1
    cumulative, rows = 0, []
    for i, day in enumerate(days):
        cumulative += counts[i]
        rows.append({'date': day.isoformat(), 'registrations': counts[i], 'cumulative': cumulative,
                     'complete': i < len(days)-1, 'fromBlock': starts[i],
                     'toBlock': starts[i+1]-1 if i+1 < len(starts) else head})
    history = {'schemaVersion': 1, 'chainId': 56, 'registry': REGISTRY, 'registryDeployBlock': deploy,
               'timeZone': 'Asia/Shanghai', 'metric': 'first-mint-per-token-id',
               'coverage': 'all-registry-transfers-since-deployment', 'snapshotBlock': head,
               'snapshotHash': anchor['hash'], 'snapshotTime': dt.datetime.fromtimestamp(anchor['timestamp'], dt.timezone.utc).isoformat(),
               'totalRegistrations': len(first), 'mintEvents': mint_events, 'repeatMints': mint_events-len(first), 'days': rows}
    assert cumulative == len(first)
    assert rpc('eth_getBlockByNumber', [hex(head), False])['hash'] == anchor['hash'], 'Snapshot reorganization'
    save(cache_path, headers)
    save(out / 'registration-history.json', history)
    return history


def publish_history(history, destination, anchor):
    assert history['snapshotBlock'] == anchor['number'] and history['snapshotHash'] == anchor['hash']
    assert history['metric'] == 'first-mint-per-token-id' and history['timeZone'] == 'Asia/Shanghai'
    assert sum(r['registrations'] for r in history['days']) == history['totalRegistrations']
    destination = Path(destination)
    save(destination / 'registrations.json', history)
    p = destination / 'registrations.csv'
    temp = p.with_suffix('.csv.tmp')
    with temp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['Date (Asia/Shanghai)', 'New Agent IDs (first registration)', 'Cumulative first registrations', 'Complete day', 'Snapshot block'])
        for row in history['days']:
            w.writerow([row['date'], row['registrations'], row['cumulative'], row['complete'], history['snapshotBlock']])
    temp.replace(p)
