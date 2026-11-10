"""Fail-closed browser audit of retained issuer-news UI and selection races."""
import argparse
import asyncio
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
PARSER = argparse.ArgumentParser()
PARSER.add_argument('--snapshot', required=True, type=Path)
PARSER.add_argument('--edge', default=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
ARGS = PARSER.parse_args()
SNAP = json.loads(ARGS.snapshot.read_text(encoding='utf-8'))
TEMPLATE = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r'/static/\1', (ROOT/'templates/dashboard.html').read_text(encoding='utf-8'))


async def main():
    requests, errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=ARGS.edge, headless=True)
        page = await browser.new_page(viewport={'width': 1672, 'height': 941})
        page.on('pageerror', lambda error: errors.append(str(error)))

        async def route(r):
            req = r.request
            url = urlparse(req.url)
            requests.append((req.method, url.netloc, url.path))
            if url.netloc != 'localhost:37777' or req.method != 'GET':
                return await r.abort()
            if url.path == '/':
                return await r.fulfill(status=200, content_type='text/html; charset=utf-8', body=TEMPLATE)
            if url.path.startswith('/static/'):
                path = (ROOT/url.path.lstrip('/')).resolve()
                if path.is_relative_to(ROOT/'static') and path.is_file():
                    return await r.fulfill(status=200, content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream', body=path.read_bytes())
                return await r.abort()
            if url.path == '/api/v1/strategy-radar/watches':
                data = SNAP[url.path]
                watch = data['watches'][0]
                return await r.fulfill(json={**data, 'watches': [{**watch, 'instrument': key} for key in ('MTN', 'VOD')]})
            if url.path == '/api/v1/strategy-radar/swing':
                evidence = SNAP[url.path]['evaluations']['MTN']
                return await r.fulfill(json={'evaluations': {key: {**evidence, 'instrument': key} for key in ('MTN', 'VOD')}})
            if url.path == '/api/v1/strategy-radar/catalog':
                return await r.fulfill(json={'instruments': ['MTN', 'VOD']})
            if url.path.startswith('/api/market-intelligence/issuer-news/'):
                key = url.path.rsplit('/', 1)[-1]
                if key == 'MTN':
                    await asyncio.sleep(1)
                return await r.fulfill(json={'state': 'AVAILABLE', 'limitations': 'Direct mention is not an event prediction.', 'items': [{
                    'headline': key + ' synthetic retained headline', 'source_kind': 'RETAINED_SENS',
                    'source_window': 'OUTSIDE_SOURCE_WINDOW', 'published_at': None,
                    'publication_detail': {'value': '2026-11-01', 'precision': 'date'},
                    'observed_at': '2026-11-02T12:00:00Z', 'source_url': 'https://example.test/sens'}]})
            return await r.fulfill(status=503, json={'error': 'offline fixture'})

        await page.route('**/*', route)
        await page.goto('http://localhost:37777/', wait_until='load')
        await page.locator('#radar-points button').filter(has_text='MTN').wait_for()
        await page.locator('#radar-points button').filter(has_text='MTN').click()
        await page.locator('#radar-points button').filter(has_text='VOD').click()
        await asyncio.sleep(1.2)
        text = await page.locator('#radar-news-context').text_content()
        assert 'VOD synthetic retained headline' in text and 'MTN synthetic retained headline' not in text, text
        assert 'OUTSIDE_SOURCE_WINDOW' in text and '2026-11-01 (date)' in text and 'observed 2026-11-02T12:00:00Z' in text, text
        assert 'No scheduled event date inferred' in text, text
        assert not errors, errors
        assert all(host == 'localhost:37777' for method, host, path in requests), requests
        print(f'PASS issuer news provenance and delayed selection race; {len(requests)} intercepted requests')
        await browser.close()


asyncio.run(main())
