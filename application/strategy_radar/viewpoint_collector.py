"""Read-only ViewPoint chart export through a dedicated signed-in Edge profile."""
from datetime import datetime, timezone
from hashlib import sha256
import re
from urllib.parse import urlsplit

from application.opportunities.zebra_instruments import mappings
from scripts.local_runtime import process_lock
from .intraday_adapters import viewpoint_table_csv
from .intraday_store import IntradayCache
from .viewpoint_inbox import _EXPORT, _MAX_BYTES

VIEWPOINT = 'https://viewpoint.iress.co.za/st/'


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
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            return {'state': 'PLAYWRIGHT_REQUIRED', 'instruments': {}}
        registered = mappings(self.service.folder.parent / 'radar-public-prices')
        instruments = dict.fromkeys(w['instrument'] for w in watches)
        instruments.update(dict.fromkeys(w.get('benchmark') for w in watches if w.get('benchmark')))
        result = {}
        cache = IntradayCache(self.service.folder / 'intraday.sqlite3')
        try:
            with process_lock(self.service.folder / 'viewpoint-collector.lock'), sync_playwright() as browser:
                context = browser.chromium.launch_persistent_context(
                    str(self.profile), channel='msedge', headless=False, accept_downloads=True, timeout=12000)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.set_default_timeout(2500)
                    page.goto(VIEWPOINT, wait_until='domcontentloaded', timeout=10000)
                    if urlsplit(page.url).hostname != 'viewpoint.iress.co.za':
                        return {'state': 'SIGN_IN_REQUIRED', 'instruments': {}}
                    try:
                        page.get_by_role('button', name='Table View', exact=True).wait_for(state='visible', timeout=12000)
                    except Error:
                        return {'state': 'SIGN_IN_OR_CHART_SETUP_REQUIRED', 'instruments': {}}
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
                finally:
                    context.close()
        except (Error, OSError):
            return {'state': 'BROWSER_UNAVAILABLE', 'instruments': result}
        return {'state': 'CHECKED', 'instruments': result}
