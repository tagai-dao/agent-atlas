"""Backfill daily registrations from an already verified full holdings snapshot."""
import argparse
import json
import os
from pathlib import Path
import re
from holdings.refresh import Snapshot, registry_owners
from registration_history import build_history, publish_history

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
p.add_argument('--publish', type=Path)
p.add_argument('--rpc-env-file', type=Path)
p.add_argument('--rpc-env-name', default='BSC_RPC_URL')
args = p.parse_args()
if args.rpc_env_file:
    assert re.fullmatch('[A-Z_][A-Z0-9_]*', args.rpc_env_name)
    m = re.search(r'^\s*'+re.escape(args.rpc_env_name)+r'\s*=\s*(.*?)\s*$', args.rpc_env_file.read_text(), re.M)
    assert m, 'Named RPC variable missing; endpoint redacted'
    endpoint = m[1].strip().strip('\"\'')
    assert endpoint.startswith('https://'), 'HTTPS RPC required; endpoint redacted'
    os.environ['BSC_RPC_URL'] = endpoint
source = args.source.resolve()
anchor = json.loads((source/'snapshot-block.json').read_text())
complete = json.loads((source/'complete.json').read_text())
assert complete['allRegisteredIds'] and complete['snapshotBlock'] == anchor['number'] and complete['snapshotHash'] == anchor['hash']
logs = json.loads((source/'registry-transfers.json').read_text())
assert complete['registryLogs'] == len(logs) and len(registry_owners(logs)) == complete['walletCount']
args.out.mkdir(parents=True, exist_ok=True)
(args.out/'snapshot-block.json').write_text(json.dumps(anchor))
snapshot = Snapshot(args.out)
history = build_history(logs, anchor, snapshot.rpc, args.out, source)
if args.publish:
    publish_history(history, args.publish, anchor)
print(json.dumps({'snapshotBlock': anchor['number'], 'days': len(history['days']), 'registrations': history['totalRegistrations'], 'mintEvents': history['mintEvents']}))
