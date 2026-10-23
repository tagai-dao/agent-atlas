# Agent ID ATLAS

Agent ID directory, public X association evidence, BSC token trading activity and Relic NFT mint activity.

Existing public site: https://agent-atlas.silly-owlet-8650.chatgpt.site/

## Quick start

Requires Node.js 22.13 or newer.

```sh
npm ci --ignore-scripts
npm run dev
```

Local preview: http://localhost:5173

```sh
node scripts/check-data.mjs
node scripts/check-activity.mjs
npx tsc --noEmit
npm run build
```

## Current data

- X source snapshot: 2026-10-23T07:33:38.842Z (15:33 Beijing time).
- 1,944 evidence records across 1,896 names; 1,935 chain-checked directory records.
- Latest local-source import accepted 1,852 rows and quarantined 12 malformed or known false OCR matches.
- Chain ownership checks for the latest import use fixed BSC block 129288331.
- X association evidence does not prove wallet control; new associations remain candidates, preserving source confidence.
- Token and NFT data have their own snapshot dates and coverage boundaries in `public/activity/manifest.json`.

## Deployment handoff

This repository preserves the existing Sites/Vinext application, including its UI, server routes, static activity assets and D1 schema. It is independent of the tagai-ui repository. No deployment is triggered by pushing this repository.

`.openai/hosting.json` retains the existing public site's identity and DB binding. It is metadata, not a credential. Publishing to that existing site requires an authorized Sites session and its source synchronization workflow; a GitHub push alone does not update it. The latest data version (7) was saved, but its publish attempt returned `Unauthorized`.

For separate infrastructure, engineers must configure their own Worker/D1 bindings, migrations, hostname and production authentication. The current local mock identity must not be used as production authentication. Sites identity and connector integration are platform-specific; the repository is not presented as a ready-to-deploy generic Docker service. The existing `tagai-ui` PR #209 contains a separate Node/Vite deployment adaptation if that architecture is preferred: https://github.com/tagai-dao/tagai-ui/pull/209 .

## Synchronization

The desktop source is `agent-id-site/data/mappings_v2.json`, served at localhost:8787. The hosted site uses an imported snapshot and cannot access an engineer's localhost. A six-hour desktop automation is configured in Codex; that schedule and its credentials are not part of this repository. To migrate automation, provide an authorized source and deployment environment, preserve reviewed evidence, handle source removals, validate records, and recheck names through fixed-block Multicall3 before republishing. Do not commit API tokens, cookies, wallet credentials or raw private research.

Source snapshot commit: `ad9572ba2fa357e35ffb9c1e904002ce13c59c95`.

## Detailed implementation notes

The following historical notes document collection and activity semantics. Earlier numerical totals are historical; current totals are in `data/research.json` and the section above.

## Features
- Search curated Agent IDs, wallet addresses and X usernames.
- Resolve additional names through the public bnb.fan index, then verify `handleOf(address)` directly against BSC. Address reverse lookup is direct RPC.
- Show X public statements separately from on-chain registration. No X association is labeled wallet-control verified.
- Preserve evidence URLs and short excerpts. Signed-in owner can add a claim or import an X API/xurl JSON; new records remain unverified candidates in D1.
- CSV export of the filtered directory, pagination and profile details.

## Data and provenance
`data/registry.json`: 240 on-chain checked records, including the original 92 AIPRO trader handles. This is a sample, not a full registry mirror.
`data/evidence.json`: 180 evidence items across 160 names. The 2026-10-23 research merged 800 unique posts, downloaded/OCR-checked 464 images or video/GIF preview frames, and resolved 145 extracted names against BSC at block 129213787. Not every posted name is a registered name.
`data/research.json`: target window, counts and explicit incomplete-search status. The X API returned 402 credits depleted after 7 pages / 698 posts. This is NOT a complete seven-day X index. Older stored posts and the two user-supplied posts supplement this result but do not close the pagination gap.
OCR corrections were reviewed for 0/o, l/i and q/g. Registry-list screenshots are not attributed wholesale to their publishers. Reserved/unbound names remain candidates. Explicit self-statements are never cryptographic ownership proof.
All seed datasets contain public records only. No keys, cookies or tokens are included.

## Collect fresh public evidence
On a machine with xurl already signed in, run `node scripts/collect-x.mjs`. The collector paginates until exhaustion or an API error, writes `outputs/x-week.json`, and retains the next cursor. Resume with `node scripts/collect-x.mjs --resume`; set X_RESEARCH_FILE to an existing saved research file. A very old cursor or a window outside recent-search retention may need a new search or full-archive entitlement.
Import reviewed batches of at most 100 posts in the website. The import parser reads long-post note_tweet entities and official Binance /agent-id/NAME links. It never trusts imported claims as verified ownership.
Offline `scripts/ocr-media.swift` uses macOS Vision on local images. `scripts/analyze-x.py RESEARCH_DIRECTORY` reads combined.json and ocr.jsonl, emits extraction/audit JSON, and records evidence methods. Public dataset updates require a reviewed source update and republish. Video content is limited to preview frames, not full transcription. Raw research and cursors are stored outside the published source under the workspace outputs folder.

The server does not receive local X credentials. Automated continuous X search requires a separately authorized API integration and is intentionally not claimed by this version.

## Run and publish
Follow Sites skill helpers. `npm run dev` launches the local preview; `npm run db:generate` generates schema-only D1 migrations. `.openai/hosting.json` declares DB. New evidence writes require the visitor identity supplied by Sites and same-origin requests.


## On-chain activity integration (2026-10-23)
- The public directory merges `public/activity/agents.json` after loading. Large immutable data is served as static assets, avoiding bundling 24k+ identities or 39k+ NFT events into a Worker.
- `public/activity/manifest.json` records the BSC snapshot block, per-asset coverage and limitations. `feed.json` is limited to 200 recent events per asset. Complete wallet histories for the scanned contracts/pools are partitioned by the first address byte in `wallets/00.json` through `ff.json`.
- AIPRO uses the token's curve trade event (topic `0x9adcf0ad0cda63c4d50f26a48925cf6405df27d422a39c456b5f03f661c82982`). Agentic Inu `.ai` uses `Buy(address,uint256,uint256)` and `Sell(address,uint256,uint256)`. GANG uses the manager's identified Buy/Sell topics filtered to the exact token address. Transfers alone are never treated as trades.
- Flaip is the user-corrected curve/share contract `0xb8fb293b3e8e3c5fd741e34ac5810dd5dc9f2c7f`, not a normal ERC20. The original supplied address is its creator. `metadata()` identifies Flaip, `quoteToken()` identifies BNCB. Its Bought/Sold events represent curve shares, in 18-decimal units. The displayed quote is the event's value, not a normalized all-fees trade cost.
- External activity uses Swap events from 6 pools discovered through DexScreener, with token0 independently read from each pool. Attribution uses transaction.from; relayed/AA transactions can be missed. Multi-hop swaps can produce multiple events. This does not claim coverage of every possible pool or intermediary.
- Relic NFT contract `0xe8c6b38b5e63377a96b268319b66638f772254bb`, Game `0xb0d5f3108af164f5f7046f53ab59fd2779812d10`, deployment block 129129391: only Minted/MintedWithBnb events count. Recipient names are read with registry.handleOf, and each UTF-8 handle's keccak256 must match the mint event's handleHash. Public-sale totals reconcile to 95,000 NFTs and 39,214 mint events. Team allocation and ordinary NFT transfers are excluded.
- Names are current registration snapshots, with the lookup block retained per identity. Historic token activity does not prove that the name was registered at transaction time. X evidence remains independent.
- Research source/caches are in the workspace `outputs/agent-atlas/activity` directory, outside the deployed source. The normalized ledger retains transaction hashes and log indices. To regenerate reviewed static data: `python scripts/activity/normalize.py /absolute/path/to/activity-source`. Requires httpx/eth-abi/pycryptodome for collection and pycryptodome for normalization. The site is a fixed snapshot, with no unattended sync claimed.
- Run `node scripts/check-activity.mjs` for ledger/summary, asset, unit and mint-cap reconciliation. Existing data checks and TypeScript validation still apply.

## Grok local source import (2026-10-23)

Read-only snapshot from the user-supplied Desktop agent-id-site/data/mappings_v2.json. Source reports 3,461 posts and 1,563 OCR images; these totals may overlap the previous research and are not added together. Accepted 1,732 rows, quarantined four invalid names, merged 86 existing pieces of evidence, adding 1,646. All new associations are candidates; original confidence is preserved separately. 1,712 distinct accepted names were independently checked via BSC registry ownerOf(keccak256(label)) at blocks 129229512–129229518; 1,666 registered. No wallet/X control proof is asserted. This is a static import; the hosted site does not call localhost.
