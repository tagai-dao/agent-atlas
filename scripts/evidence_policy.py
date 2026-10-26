"""Public X association strength, independent of review status and wallet ownership.

Only complete, directly attached single-identity images and the author's own
display-name identity can be strongest. Incomplete OCR is never positive proof.
"""
import hashlib
import json
import re
from pathlib import Path

VERSION = 'single-identity-v3'
NAME = re.compile(r'(?<![\w.@/-])([a-z0-9-]{1,40})\.ai\b', re.I)


def names(text):
    return sorted({m[1].lower() + '.ai' for m in NAME.finditer(text or '')})


def load_context(raw_root, previous=None):
    """Read cached public X responses and OCR only; no network or new OCR calls."""
    context = dict(previous or {})
    root = Path(raw_root)
    paths = sorted([*root.glob('*.txt'), *root.glob('*.json'),
                    *(root / 'v2').glob('*.txt'), *(root / 'v2').glob('*.json')])
    for path in paths:
        text = path.read_text(errors='replace')
        try:
            data = json.loads(text[text.index('{'):text.rindex('}') + 1])
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        users = {str(u['id']): u for u in data.get('includes', {}).get('users', [])}
        media = {m['media_key']: m for m in data.get('includes', {}).get('media', [])}
        # Referenced tweets are not the current author's images or display name.
        for post in data.get('data', []):
            user = users.get(str(post.get('author_id')))
            if not user:
                continue
            photos = []
            article = post.get('article') or {}
            article_keys = [k for k in [article.get('cover_media'), *article.get('media_entities', [])] if isinstance(k, str)]
            keys = list(dict.fromkeys(post.get('attachments', {}).get('media_keys', []) + article_keys))
            for key in keys:
                item = media.get(key, {})
                ocr = root / 'v2' / 'media' / (re.sub(r'\W', '_', key) + '.jpg.txt')
                content = ocr.read_text(errors='replace') if ocr.exists() else ''
                photos.append({'key': key, 'type': item.get('type'),
                               'url': item.get('url'), 'names': names(content),
                               'ocrComplete': bool(content.strip()),
                               'identityCard': bool(re.search(r'agent\s*id|binance|agentic\s*wallet', content, re.I))})
            row = {'authorId': str(user['id']), 'xHandle': user['username'],
                   'displayName': user.get('name', ''), 'postId': str(post['id']),
                   'publishedAt': post.get('created_at'),
                   'text': article.get('plain_text') or post.get('note_tweet', {}).get('text') or post.get('text', ''),
                   'articleComplete': bool(article.get('plain_text')),
                   'mediaInventoryComplete': all(key in media for key in keys),
                   'repost': any(r.get('type') == 'retweeted' for r in post.get('referenced_tweets', [])),
                   'media': photos, 'source': str(path.relative_to(root))}
            old = context.get(str(post['id']))
            # Never replace a full attachment expansion with a partial response.
            if not old or (not old.get('articleComplete') and row.get('articleComplete')) or (not old.get('articleComplete') and sum(p['ocrComplete'] for p in photos) > sum(p['ocrComplete'] for p in old.get('media', []))):
                context[str(post['id'])] = row
    return context


def profile_mappings(context, existing):
    """Explicit .ai in an author's display name; never infer from @handle similarity."""
    seen = {(r['agentId'].lower(), r['xHandle'].lower()) for r in existing}
    output = []
    for c in sorted(context.values(), key=lambda c: c.get('publishedAt') or '', reverse=True):
        ns = names(c.get('displayName', ''))
        if len(ns) != 1 or c.get('repost'):
            continue
        name = ns[0]
        key = (name, c['xHandle'].lower())
        if key in seen:
            continue
        seen.add(key)
        output.append({'agentId': name, 'xHandle': c['xHandle'], 'postId': c['postId'],
                       'postUrl': f"https://x.com/{c['xHandle']}/status/{c['postId']}",
                       'postDate': c.get('publishedAt'), 'text': c.get('text', ''),
                       'sourceType': 'display-name', 'confidence': 'high',
                       'evidence': 'Exact .ai in the post author display name; cached public X response'})
    return output


def classify(evidence, context, image_names_by_url=None):
    post_id = evidence['sourceUrl'].rstrip('/').split('/')[-1]
    c = context.get(post_id)
    matched = c and c['xHandle'].lower() == evidence['xHandle'].lower()
    methods = set(evidence.get('extractionMethods', []))
    name = evidence['name'].lower()
    strongest = []
    image_excluded = False
    image_reason = None
    image_names = []
    known_names = (image_names_by_url or {}).get(evidence.get('mediaUrl'), [])
    if len(known_names) > 1 and 'image_ocr' in methods:
        image_excluded = True
        image_reason = 'multi_identity_image'
    if matched and not c.get('repost'):
        profile = names(c.get('displayName', ''))
        if profile == [name]:
            strongest.append('author_display_name')
        media = c.get('media', [])
        image_names = sorted({n for m in media for n in m.get('names', [])})
        bad_images = [m for m in media if len(m.get('names', [])) > 1]
        cards = [m for m in media if m.get('type') in ['photo', 'animated_gif'] and m.get('ocrComplete') and m.get('identityCard') and len(m.get('names', [])) == 1]
        if bad_images:
            image_excluded = True
            image_reason = 'multi_identity_image'
        # Count identity images, not article covers or unrelated wallet screenshots.
        # No required language, template, or "my Agent ID" keyword.
        if len(cards) == 1 and cards[0]['names'] == [name]:
            text = c.get('text', '')
            base = re.escape(name[:-3])
            own_target = bool(re.search(r'(?:我的(?:就是|\s*(?:agent\s*id|身份|ID))|my\s+(?:agent\s*id|id)(?:\s+is)?)[^\n]{0,35}\b' + base + r'(?:\.ai)?\b', text, re.I))
            third_party = bool(re.search(r'一姐.{0,40}分享|(?:截图来自|转自|他人的|她的|他的)|(?:for example|例如|示意)[^\n]{0,40}\b' + base + r'\.ai\b', text, re.I))
            if own_target or not third_party:
                strongest.append('own_single_identity_image')
        elif len(cards) > 1:
            image_reason = image_reason or 'multiple_identity_images'
    # A post's known multi-ID image also invalidates older OCR-only rows whose
    # target media was not persisted. Independent text/profile evidence survives.
    image_only = bool(methods & {'image_ocr'}) and not bool(methods - {'image_ocr', 'manual_review'})
    strength = 'strongest' if strongest else 'excluded' if image_excluded and image_only and image_reason == 'multi_identity_image' else 'weak'
    incomplete = not matched or any(m.get('type') in ['photo','animated_gif'] and not m.get('ocrComplete') for m in (c.get('media', []) if matched else []))
    reason = '+'.join(strongest) if strongest else image_reason if strength == 'excluded' else ('image_review_pending' if incomplete else 'other_or_incomplete_evidence')
    result = {'associationStrength': strength, 'associationReasons': strongest or [reason],
              'associationPolicy': VERSION, 'associationReviewStatus': 'pending_source' if strength == 'weak' and incomplete else 'assessed'}
    if image_excluded:
        result['excludedImageReason'] = image_reason
        result['excludedImageNames'] = sorted(set(image_names) | set(known_names))
    if matched:
        result['displayName'] = c.get('displayName', '')
        result['associationContext'] = {'authorId': c['authorId'], 'postId': post_id,
                                        'mediaCount': len(c.get('media', [])),
                                        'imageNames': image_names, 'source': c['source']}
        if 'own_single_identity_image' in strongest:
            result['mediaUrl'] = next(m['url'] for m in c['media'] if m.get('identityCard') and m.get('names') == [name])
    return result


def apply_policy(evidence, research, context):
    by_url = {}
    for c in context.values():
        for m in c.get('media', []):
            if m.get('url'):
                by_url.setdefault(m['url'], set()).update(m.get('names', []))
    for e in evidence:
        for key in ['associationStrength', 'associationReasons', 'associationPolicy', 'associationContext', 'excludedImageReason', 'excludedImageNames', 'associationReviewStatus']:
            e.pop(key, None)
        e.update(classify(e, context, by_url))
    active = [e for e in evidence if e['associationStrength'] != 'excluded']
    research.update(evidenceItems=len(active), linkedNames=len({e['name'] for e in active}),
                    rawEvidenceItems=len(evidence), excludedEvidenceItems=len(evidence)-len(active),
                    strongestEvidenceItems=sum(e['associationStrength']=='strongest' for e in active),
                    weakEvidenceItems=sum(e['associationStrength']=='weak' for e in active),
                    selfDeclaredItems=sum(e['status']=='self_declared' for e in active),
                    candidateItems=sum(e['status']=='candidate' for e in active),
                    associationPendingReviewItems=sum(e.get('associationReviewStatus')=='pending_source' for e in active),
                    associationPolicy=VERSION)
    return evidence


def context_fingerprint(context):
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
