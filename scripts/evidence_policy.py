"""Public X association strength, independent of review status and wallet ownership.

Only complete, directly attached single-identity images and the author's own
display-name identity can be strongest. Incomplete OCR is never positive proof.
"""
import hashlib
import json
import re
from pathlib import Path

VERSION = 'single-identity-v1'
NAME = re.compile(r'(?<![\w.@/-])([a-z0-9-]{1,40})\s*\.\s*ai\b', re.I)


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
            keys = post.get('attachments', {}).get('media_keys', [])
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
                   'text': post.get('note_tweet', {}).get('text') or post.get('text', ''),
                   'repost': any(r.get('type') == 'retweeted' for r in post.get('referenced_tweets', [])),
                   'media': photos, 'source': str(path.relative_to(root))}
            old = context.get(str(post['id']))
            # Never replace a full attachment expansion with a partial response.
            if not old or sum(p['ocrComplete'] for p in photos) > sum(p['ocrComplete'] for p in old.get('media', [])):
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
        if any(len(m.get('names', [])) > 1 for m in media):
            image_excluded = True
            image_reason = 'multi_identity_image'
        elif len(media) > 1:
            image_excluded = True
            image_reason = 'multiple_images'
        elif len(media) == 1:
            m = media[0]
            text = c.get('text', '')
            own = bool(re.search(r'\bmy\b.{0,45}(agent|identity|id)|\bi\s+(?:just\s+)?(?:claimed|registered|got)|我的|我(?:刚|已|申请|注册|领取)|分享.*agent\s*id|agent\s*id\s*[—–-]\s*(?:one name|您的)', text, re.I))
            third_party = bool(re.search(r'tutorial|教程|排行榜|leaderboard|名单|someone\s+else|他的|她的|their\s+agent', text, re.I))
            if not image_excluded and m.get('type') == 'photo' and m.get('ocrComplete') and m.get('names') == [name] and m.get('identityCard') and own and not third_party:
                strongest.append('own_single_identity_image')
    # A post's known multi-ID image also invalidates older OCR-only rows whose
    # target media was not persisted. Independent text/profile evidence survives.
    image_only = bool(methods & {'image_ocr'}) and not bool(methods - {'image_ocr', 'manual_review'})
    strength = 'strongest' if strongest else 'excluded' if image_excluded and image_only and image_reason == 'multi_identity_image' else 'weak'
    reason = '+'.join(strongest) if strongest else image_reason if strength == 'excluded' else 'other_or_incomplete_evidence'
    result = {'associationStrength': strength, 'associationReasons': strongest or [reason],
              'associationPolicy': VERSION}
    if image_excluded:
        result['excludedImageReason'] = image_reason
        result['excludedImageNames'] = sorted(set(image_names) | set(known_names))
    if matched:
        result['displayName'] = c.get('displayName', '')
        result['associationContext'] = {'authorId': c['authorId'], 'postId': post_id,
                                        'mediaCount': len(c.get('media', [])),
                                        'imageNames': image_names, 'source': c['source']}
        if 'own_single_identity_image' in strongest:
            result['mediaUrl'] = c['media'][0]['url']
    return result


def apply_policy(evidence, research, context):
    by_url = {}
    for c in context.values():
        for m in c.get('media', []):
            if m.get('url'):
                by_url.setdefault(m['url'], set()).update(m.get('names', []))
    for e in evidence:
        if e.get('mediaUrl') and 'image_ocr' in e.get('extractionMethods', []):
            by_url.setdefault(e['mediaUrl'], set()).add(e['name'].lower())
    for e in evidence:
        for key in ['associationStrength', 'associationReasons', 'associationPolicy', 'associationContext', 'excludedImageReason', 'excludedImageNames']:
            e.pop(key, None)
        e.update(classify(e, context, by_url))
    active = [e for e in evidence if e['associationStrength'] != 'excluded']
    research.update(evidenceItems=len(active), linkedNames=len({e['name'] for e in active}),
                    rawEvidenceItems=len(evidence), excludedEvidenceItems=len(evidence)-len(active),
                    strongestEvidenceItems=sum(e['associationStrength']=='strongest' for e in active),
                    weakEvidenceItems=sum(e['associationStrength']=='weak' for e in active),
                    selfDeclaredItems=sum(e['status']=='self_declared' for e in active),
                    candidateItems=sum(e['status']=='candidate' for e in active),
                    associationPolicy=VERSION)
    return evidence


def context_fingerprint(context):
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
