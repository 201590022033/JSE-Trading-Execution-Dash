"""Read-only ViewPoint chart export through a dedicated signed-in Edge profile."""
from datetime import datetime, timezone
from hashlib import sha256
import re
from time import monotonic, sleep
import json
from uuid import uuid4
from urllib.parse import urlsplit

from application.opportunities.ost_data import atomic_json
from application.opportunities.zebra_instruments import mappings
from scripts.local_runtime import process_lock
from .intraday_adapters import viewpoint_table_csv
from .intraday_store import IntradayCache
from .viewpoint_inbox import _EXPORT, _MAX_BYTES

VIEWPOINT = 'https://viewpoint.iress.co.za/st/'

OST = 'https://securities.standardbank.co.za/ost/sp/frontofficesecure/legacy/newframes.asp'


def _viewpoint_chart(context):
    for page in context.pages:
        if urlsplit(page.url).hostname == 'viewpoint.iress.co.za':
            if page.get_by_role('button', name='Table View', exact=True).first.is_visible():
                return page
    return None


def _wait_for_ost_launch(context, ost_page, *, timeout_seconds):
    """Follow the normal OST launcher and detect either a popup or same-tab chart."""
    deadline = monotonic() + timeout_seconds
    launched = False
    while monotonic() < deadline:
        chart = _viewpoint_chart(context)
        if chart:
            return chart
        if not launched and not ost_page.is_closed():
            for frame in ost_page.frames:
                if urlsplit(frame.url).hostname != 'securities.standardbank.co.za':
                    continue
                link = frame.get_by_role('link', name='ViewPoint', exact=True)
                if link.count() == 1 and link.is_visible():
                    link.click(timeout=2000, no_wait_after=True)
                    launched = True
                    break
        pages = context.pages
        if not pages:
            break
        # Pump browser events while waiting for the OST sign-in or its popup.
        pages[0].wait_for_timeout(500)
    return None



def _export(page, symbol):
    dialog = page.get_by_role('dialog', name='Data Table')
    if dialog.is_visible():
        dialog.get_by_role('button', name='close', exact=True).click()
    chart = page.get_by_role('img', name=re.compile(
        r'5 minute candle chart displays price over time for symbol ' + re.escape(symbol) + r'\b'))
    if not chart.is_visible():
        search = page.get_by_role('dialog', name='Search for security')
        if not search.is_visible():
            page.get_by_role('button', name='Security Search', exact=True).click()
        field = search.get_by_role('combobox', name='Input Search Text')
        field.fill('')
        field.press_sequentially(symbol)
        search.get_by_role('list', name='Results').get_by_text(symbol, exact=True).click()
    chart.wait_for(state='visible')
    page.get_by_role('button', name='Table View', exact=True).click()
    dialog.get_by_role('heading', name=f'Symbol: {symbol}', exact=True).wait_for(state='visible')
    if not dialog.get_by_role('columnheader', name='Volume', exact=True).count():
        dialog.get_by_role('switch', name='Show Additional Columns').click()
    dialog.get_by_role('columnheader', name='Volume', exact=True).wait_for(state='visible')
    with page.expect_download(timeout=7000) as pending:
        dialog.get_by_role('button', name='Download', exact=True).click()
    download = pending.value
    name = download.suggested_filename
    match = _EXPORT.fullmatch(name)
    if not match or match[1].upper() + '.JSE' != symbol:
        raise ValueError('Unexpected export instrument')
    with download.path().open('rb') as stream:
        return name, stream.read(_MAX_BYTES + 1)


class ViewPointCollector:
    def __init__(self, service):
        self.service = service
        self.profile = service.folder / 'viewpoint-edge-profile'

    def collect(self, watches):
        if not (self.profile / 'Local State').is_file():
            return {'state': 'BROWSER_SETUP_REQUIRED', 'instruments': {}}
        try:
            import playwright.sync_api
        except ImportError:
            return {'state': 'PLAYWRIGHT_REQUIRED', 'instruments': {}}
        queue = self.service.folder / 'viewpoint-requests'
        try:
            if not 0 <= monotonic() - float((queue / 'heartbeat').read_text()) <= 120:
                raise ValueError('collector heartbeat expired')
        except (OSError, ValueError):
            return {'state': 'START_OST_SETUP', 'instruments': {}}
        request = queue / f'{uuid4().hex}.json'
        response = request.with_suffix('.result')
        atomic_json(request, {'watches': watches})
        try:
            deadline = monotonic() + 90
            while monotonic() < deadline:
                if response.exists():
                    return json.loads(response.read_text(encoding='utf-8'))
                sleep(0.25)
            return {'state': 'COLLECTOR_TIMEOUT', 'instruments': {}}
        finally:
            request.unlink(missing_ok=True)
            response.unlink(missing_ok=True)

    def export_watches(self, page, watches):
        from playwright.sync_api import Error

        page.set_default_timeout(2500)
        registered = mappings(self.service.folder.parent / 'radar-public-prices')
        instruments = dict.fromkeys(w['instrument'] for w in watches)
        instruments.update(dict.fromkeys(w.get('benchmark') for w in watches if w.get('benchmark')))
        result = {}
        cache = IntradayCache(self.service.folder / 'intraday.sqlite3')
        try:
            charts = page.get_by_role('img', name=re.compile('5 minute candle chart'))
            if not charts.count():
                page.get_by_role('button', name='Periodicity', exact=True).click()
                page.get_by_role('menuitem', name='5 Min', exact=True).click()
                charts.wait_for(state='visible')
            for instrument in instruments:
                code = registered.get(instrument)
                if not code:
                    result[instrument] = 'MAPPING_UNAVAILABLE'
                    continue
                try:
                    symbol = f'{code}.JSE'
                    name, raw = _export(page, symbol)
                    now = datetime.now(timezone.utc)
                    records = viewpoint_table_csv(raw, instrument, symbol, now, file_name=name,
                                                 accept_operator_conventions=True)
                    digest = sha256(raw).hexdigest()
                    old = [row for row in cache.read(instrument) if row.get('source_raw_sha256') == digest]
                    if not old or (any(row['provisional'] for row in old)
                                   and not any(row['provisional'] for row in records)):
                        cache.put_batch(records, raw, evidence=True)
                    result[instrument] = 'IMPORTED' if not old else 'ALREADY_RETAINED'
                except (Error, OSError, ValueError):
                    result[instrument] = 'EXPORT_UNAVAILABLE'
        except (Error, OSError):
            return {'state': 'BROWSER_UNAVAILABLE', 'instruments': result}
        return {'state': 'CHECKED', 'instruments': result}

    def serve(self, context):
        queue = self.service.folder / 'viewpoint-requests'
        queue.mkdir(parents=True, exist_ok=True)
        heartbeat = queue / 'heartbeat'
        try:
            while context.pages:
                heartbeat.write_text(str(monotonic()), encoding='utf-8')
                for request in sorted(queue.glob('*.json')):
                    if not re.fullmatch(r'[0-9a-f]{32}', request.stem):
                        continue
                    response = request.with_suffix('.result')
                    if response.exists():
                        continue
                    try:
                        watches = json.loads(request.read_text(encoding='utf-8'))['watches']
                    except (OSError, ValueError, KeyError):
                        continue
                    chart = _viewpoint_chart(context)
                    result = (self.export_watches(chart, watches) if chart else
                              {'state': 'OST_SIGN_IN_OR_CHART_SETUP_REQUIRED', 'instruments': {}})
                    if request.exists():
                        atomic_json(response, result)
                context.pages[0].wait_for_timeout(500)
        finally:
            heartbeat.unlink(missing_ok=True)


def setup():
    from playwright.sync_api import Error, sync_playwright
    from .service import RadarService

    collector = ViewPointCollector(RadarService())
    try:
        with process_lock(collector.service.folder / 'viewpoint-collector.lock'), sync_playwright() as browser:
            context = browser.chromium.launch_persistent_context(
                str(collector.profile), channel='msedge', headless=False)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(OST, wait_until='domcontentloaded')
                print('Sign in to Standard Bank OST in this Edge window. '
                      'The script will open ViewPoint when the launcher appears. '
                      'Open a chart in ViewPoint if needed.', flush=True)
                if _wait_for_ost_launch(context, page, timeout_seconds=300):
                    print('ViewPoint chart verified. Leave this Edge window and terminal open for Radar.', flush=True)
                    collector.serve(context)
                    return 0
                print('No ViewPoint chart appeared. Run setup again to retry.')
                return 1
            finally:
                context.close()
    except (Error, OSError):
        print('Could not complete OST setup. Close any dedicated collector Edge windows and retry.')
        return 1


if __name__ == '__main__':
    raise SystemExit(setup())
