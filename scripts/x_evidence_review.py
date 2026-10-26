"""Hydrate exact author/media evidence from cached public post and image reviews.

No wallet, credentials, private X endpoints or paid APIs are used. Article images
are assessed individually; a cover or unrelated screenshot isn't an identity card.
"""
import hashlib
import json
import re
from pathlib import Path
from evidence_policy import names


def image_result(url, cache):
    p = cache / 'media' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if not p.exists():
        return {'ocrComplete': False, 'names': [], 'identityCard': False}
    d = json.loads(p.read_text())
    assert d['url'] == url
    text = d['text']
    review_path = Path(__file__).resolve().parents[1] / 'data/evidence-image-reviews.json'
    visual_reviews = json.loads(review_path.read_text()) if review_path.exists() else {}
    visual = visual_reviews.get(d['sha256'], {})
    detected = set(names(text))
    corrections = []
    # Font-confusable suffix repair is limited to an actual identity-card layout
    # with the same stem independently repeated as its headline. Never apply to
    # display names, ordinary domains, body text or a target supplied by the caller.
    if re.search(r'agent\s*id|id\s*agen|one\s*and\s*only', text, re.I):
        for m in re.finditer(r'(?<![\w.@/-])([a-z0-9-]{1,40})\s*\.\s*a[l1|]\b', text, re.I):
            stem = m[1].lower()
            if re.search(r'^\s*' + re.escape(stem) + r'\s*$', text, re.I | re.M):
                detected.add(stem + '.ai')
                corrections.append({'raw': m[0], 'normalized': stem + '.ai', 'basis': 'identity-card heading repeats the same stem'})
    detected.difference_update(visual.get('ignoredOcrNames', []))
    return {'visualOcrReview': visual.get('reason'), 'ocrComplete': bool(text.strip()), 'names': sorted(detected),
            'ocrCorrections': corrections,
            'identityCard': bool(detected and (re.search(r'one\s*and\s*only', text, re.I) or (re.search(r'agent\s*id|id\s*agen', text, re.I) and re.search(r'share|分享|专属|unique\s*(?:name|id)|one name', text, re.I)))),
            'imageSha256': d['sha256'], 'ocrEngine': d['engine']}


def hydrate_context(context, cache):
    cache = Path(cache)
    for p in (cache / 'posts').glob('*.json'):
        d = json.loads(p.read_text())
        if d.get('id_str') != p.stem or not d.get('user'):
            continue
        user = d['user']
        text = d.get('text', '')
        # Expanded URLs are source content, never an ownership inference.
        for u in d.get('entities', {}).get('urls', []):
            text = text.replace(u.get('url', ''), u.get('expanded_url') or u.get('url', '')) if u.get('url') else text
        media = []
        for m in d.get('mediaDetails', []):
            url = m.get('media_url_https')
            if not url:
                continue
            media.append({'type': m.get('type'), 'url': url,
                          'representation': 'preview' if m.get('type') == 'animated_gif' else 'photo',
                          **image_result(url, cache)})
        old = context.get(p.stem, {})
        # An embedded article response may contain only its teaser/cover. Do not
        # discard complete article text and inlined images captured in public DOM.
        if old.get('articleComplete'):
            for item in old.get('media', []):
                reviewed = image_result((item.get('url') or ''), cache)
                if reviewed.get('imageSha256'):
                    item.update(reviewed)
            continue
        context[p.stem] = {'authorId': user['id_str'], 'xHandle': user['screen_name'],
                            'displayName': user.get('name', ''), 'postId': p.stem,
                            'publishedAt': d.get('created_at'), 'text': text, 'repost': False,
                            'media': media, 'source': 'public-embed:' + p.stem,
                            'mediaInventoryComplete': True}
    live = cache / 'live-posts.json'
    if live.exists():
        for pid, d in json.loads(live.read_text()).items():
            old = context.get(pid, {})
            links = [l for l in d['links'] if re.fullmatch(r'/\w{1,15}', l.get('href') or '')]
            author = next((l['text'][1:] for l in links if l['text'].startswith('@')), None)
            if not author or (old and old['xHandle'].lower() != author.lower()):
                continue
            display = next((l['text'] for l in links if l['text'] and not l['text'].startswith('@')), '')
            media = [{'type': 'photo', 'url': m['src'], **image_result(m['src'], cache)}
                     for m in d['images'] if m['src'].startswith('https://pbs.twimg.com/media/')]
            context[pid] = {**old, 'authorId': old.get('authorId', ''), 'postId': pid,
                            'xHandle': author, 'displayName': display, 'text': d['text'],
                            'repost': False, 'media': media, 'articleComplete': any('/article/' in (l.get('href') or '') for l in d['links']),
                            'source': 'public-post-dom:' + pid, 'mediaInventoryComplete': True}
    return context


def refresh_review_cache(evidence, cache, context=None):
    """Fetch only uncached public posts/images for subsequent changed-source imports.

    Native OCR stays local. A missing post or OCR engine is recorded separately;
    it is never taken as proof that the author's image is a weak association.
    """
    import concurrent.futures
    import os
    import shutil
    import subprocess
    import sys
    import time
    import httpx
    cache = Path(cache)
    (cache / 'posts').mkdir(parents=True, exist_ok=True)
    (cache / 'media').mkdir(exist_ok=True)
    ids = sorted({e['sourceUrl'].rstrip('/').split('/')[-1] for e in evidence})
    missing = [i for i in ids if not (cache / 'posts' / (i+'.json')).exists() and not (cache / 'posts' / (i+'.unavailable')).exists()]
    tokens = {}
    if missing:
        js = r'''const ids=JSON.parse(process.argv[1]);console.log(JSON.stringify(Object.fromEntries(ids.map(id=>[id,((Number(id)/1e15)*Math.PI).toString(36).replace(/(0+|\.)/g,"")]))));'''
        tokens = json.loads(subprocess.check_output(['node','--input-type=module','-e',js,json.dumps(missing)], text=True))
    client = httpx.Client(timeout=30, limits=httpx.Limits(max_connections=2))
    rate_limited = False
    def fetch(pid):
        nonlocal rate_limited
        if rate_limited:
            return
        try:
            r = client.get('https://cdn.syndication.twimg.com/tweet-result', params={'id':pid,'lang':'en','token':tokens[pid]})
            if r.status_code == 429:
                rate_limited = True
                return
            r.raise_for_status()
            d = r.json()
            if d.get('id_str') == pid and d.get('user'):
                (cache/'posts'/(pid+'.json')).write_text(json.dumps(d, ensure_ascii=False))
            else:
                (cache/'posts'/(pid+'.unavailable')).write_text('Public embed did not return a post; not an ownership or deletion finding.\n')
            time.sleep(.2)
        except (httpx.HTTPError, ValueError):
            return
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(fetch, missing))
    urls = set()
    for p in (cache/'posts').glob('*.json'):
        d = json.loads(p.read_text())
        for m in d.get('mediaDetails', []):
            url = m.get('media_url_https') or ''
            if m.get('type') in ['photo','animated_gif'] and url.startswith(('https://pbs.twimg.com/media/','https://pbs.twimg.com/tweet_video_thumb/')):
                urls.add(url)
    for pid, post in (context or {}).items():
        if pid in ids:
            for m in post.get('media', []):
                url = m.get('url') or ''
                if m.get('type') in ['photo','animated_gif'] and url.startswith(('https://pbs.twimg.com/media/','https://pbs.twimg.com/tweet_video_thumb/')):
                    urls.add(url)
    needed = [u for u in urls if not (cache/'media'/(hashlib.sha256(u.encode()).hexdigest()+'.json')).exists()]
    engine = None
    if needed and sys.platform == 'darwin' and shutil.which('swiftc'):
        binary = cache/'vision-ocr'
        source = Path(__file__).with_name('x_evidence_ocr.swift')
        if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
            subprocess.run(['swiftc',str(source),'-o',str(binary)], check=True, capture_output=True)
        engine = [str(binary)]
    elif needed and shutil.which('tesseract'):
        engine = ['tesseract']
    failures = 0
    for url in needed if engine else []:
        key = hashlib.sha256(url.encode()).hexdigest()
        image = cache/'media'/(key+'.image')
        try:
            with client.stream('GET', url) as r:
                r.raise_for_status()
                body = bytearray()
                for part in r.iter_bytes():
                    body.extend(part)
                    if len(body) > 8*1024*1024:
                        raise ValueError('Image size exceeds review bound')
            image.write_bytes(body)
            if engine == ['tesseract']:
                result = subprocess.run(['tesseract',str(image),'-','-l','eng'], check=True, capture_output=True, text=True, timeout=45)
                text = result.stdout
                label = 'Tesseract full image'
            else:
                result = subprocess.run(engine, input=json.dumps({'path':str(image)})+'\n', check=True, capture_output=True, text=True, timeout=45)
                text = '\n'.join(x['text'] for x in json.loads(result.stdout)['lines'])
                label = 'Apple Vision accurate (language correction off)'
            (cache/'media'/(key+'.json')).write_text(json.dumps({'url':url,'sha256':hashlib.sha256(body).hexdigest(),'engine':label,'text':text},ensure_ascii=False))
        except (httpx.HTTPError, ValueError, subprocess.SubprocessError):
            failures += 1
    summary = {'postIds':len(ids),'publicPostsCached':sum((cache/'posts'/(i+'.json')).exists() for i in ids),'rateLimited':rate_limited,'imagesRequested':len(needed),'imageReadFailures':failures,'ocrUnavailable':bool(needed and not engine)}
    (cache/'review-status.json').write_text(json.dumps(summary,indent=2))
    return summary
