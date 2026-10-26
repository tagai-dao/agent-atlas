"""Reclassify existing public evidence without changing reviews or chain snapshots."""
import argparse
import json
from pathlib import Path
from evidence_policy import VERSION, load_context, apply_policy, context_fingerprint

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--raw-root', type=Path, required=True)
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
data = root / 'data'
cp = data / 'x-evidence-context.json'
context = load_context(args.raw_root, json.loads(cp.read_text()) if cp.exists() else {})
evidence = json.loads((data / 'evidence.json').read_text())
# Persist only the exact public posts used for classification (plus explicit
# display-name identities), rather than publishing unrelated cached X posts.
ids = {e['sourceUrl'].split('/')[-1] for e in evidence}
context = {k: v for k, v in context.items() if k in ids}
research = json.loads((data / 'research.json').read_text())
apply_policy(evidence, research, context)
for path, value in [(cp, context), (data / 'evidence.json', evidence), (data / 'research.json', research)]:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: research[k] for k in ['associationPolicy', 'rawEvidenceItems', 'evidenceItems', 'strongestEvidenceItems', 'weakEvidenceItems', 'excludedEvidenceItems', 'linkedNames']}))
