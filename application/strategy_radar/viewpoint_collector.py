"""Read-only ViewPoint chart export through a dedicated signed-in Edge profile."""
from datetime import datetime, timezone
from hashlib import sha256
import re
from time import monotonic, sleep
import json
import sqlite3
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



def _activate(locator, *, key='Enter'):
    """Use the normal control, with keyboard activation if pointer input times out."""
    from playwright.sync_api import TimeoutError

    try:
        locator.click(no_wait_after=True)
    except TimeoutError:
        locator.focus()
        locator.press(key, no_wait_after=True)


def _download_table(page, dialog):
    from playwright.sync_api import TimeoutError

    button = dialog.get_by_role('button', name='Download', exact=True)
    try:
        with page.expect_download(timeout=7000) as pending:
            try:
                button.click(no_wait_after=True)
            except TimeoutError:
                # A download may already have fired before click's wait failed.
                # Let the download event decide; do not discard its bytes.
                pass
        return pending.value
    except TimeoutError:
        with page.expect_download(timeout=7000) as pending:
            button.focus()
            button.press('Enter', no_wait_after=True)
        return pending.value


def _failure(exc, stage):
    # Keep diagnostics useful without retaining raw page text, URLs or credentials.
    message = str(exc).lower()
    reasons = [reason for reason in (
        'intercepts pointer events', 'outside of the viewport', 'not visible',
        'not enabled', 'not stable', 'detached', 'navigation', 'timeout',
    ) if reason in message]
    return {'stage': stage, 'error': type(exc).__name__, 'reasons': reasons}


class ExportFailure(ValueError):
    def __init__(self, stage, cause):
        self.detail = _failure(cause, stage)
        super().__init__(f'ViewPoint export failed at {stage}')


def _step(stage, action):
    from playwright.sync_api import Error
    try:
        return action()
    except (Error, OSError, ValueError) as exc:
        raise ExportFailure(stage, exc) from exc


def _dismiss(dialog):
    from playwright.sync_api import TimeoutError

    close = dialog.get_by_role('button', name='close', exact=True)
    try:
        _activate(close)
        dialog.wait_for(state='hidden')
    except TimeoutError:
        if dialog.is_visible():
            dialog.press('Escape')
            dialog.wait_for(state='hidden')


def _export(page, symbol):
    dialog = page.get_by_role('dialog', name='Data Table')
    if dialog.is_visible():
        _step('close prior table', lambda: _dismiss(dialog))
    chart = page.get_by_role('img', name=re.compile(
        r'5 minute candle chart displays price over time for symbol ' + re.escape(symbol) + r'\b'))
    search = page.get_by_role('dialog', name='Search for security')
    if not chart.is_visible():
        if not search.is_visible():
            _step('open security search', lambda: _activate(page.get_by_role('button', name='Security Search', exact=True)))
        field = search.get_by_role('combobox', name='Input Search Text')
        _step('clear security search', lambda: field.fill(''))
        _step('type security symbol', lambda: field.press_sequentially(symbol))
        _step('select exact security', lambda: _activate(search.get_by_role('list', name='Results').get_by_text(symbol, exact=True)))
    elif search.is_visible():
        _step('close Search for security dialog', lambda: _dismiss(search))
    _step('verify five minute symbol', lambda: chart.wait_for(state='visible', timeout=15000))
    _step('open data table', lambda: _activate(page.get_by_role('button', name='Table View', exact=True)))
    _step('verify table symbol', lambda: dialog.get_by_role('heading', name=f'Symbol: {symbol}', exact=True).wait_for(state='visible'))
    if not dialog.get_by_role('columnheader', name='Volume', exact=True).count():
        _step('enable volume', lambda: _activate(dialog.get_by_role('switch', name='Show Additional Columns'), key='Space'))
    _step('verify volume', lambda: dialog.get_by_role('columnheader', name='Volume', exact=True).wait_for(state='visible'))
    download = _step('download table', lambda: _download_table(page, dialog))
    name = download.suggested_filename
    match = _EXPORT.fullmatch(name)
    if not match or match[1].upper() + '.JSE' != symbol:
        raise ExportFailure('verify native filename', ValueError('Unexpected export instrument'))
    path = _step('finish download', download.path)
    with path.open('rb') as stream:
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
        deadline = monotonic() + 90

        def send(selected):
            request = queue / f'{uuid4().hex}.json'
            response = request.with_suffix('.result')
            atomic_json(request, {'watches': selected})
            try:
                while monotonic() < deadline:
                    if response.exists():
                        return json.loads(response.read_text(encoding='utf-8'))
                    sleep(0.25)
                return {'state': 'COLLECTOR_TIMEOUT', 'instruments': {}}
            finally:
                request.unlink(missing_ok=True)
                response.unlink(missing_ok=True)

        first = send(watches)
        retry = [key for key, error in first.get('errors', {}).items()
                 if first.get('state') == 'CHECKED'
                 and first.get('instruments', {}).get(key) == 'EXPORT_UNAVAILABLE'
                 and error.get('stage') == 'verify five minute symbol'
                 and error.get('error') == 'TimeoutError']
        if not retry or monotonic() >= deadline:
            return first
        # An older collector may switch away before the preceding chart renders.
        # Recover one exact symbol at a time; keep every attempt and the shared
        # 90-second budget. No successful export is requested again.
        result = {**first, 'attempts': [first]}
        for field in ('instruments', 'evidence', 'errors'):
            result[field] = dict(first.get(field, {}))
        for key in retry:
            for _ in range(2):
                if monotonic() >= deadline:
                    break
                attempt = send([{'instrument': key}])
                result['attempts'].append(attempt)
                for field in ('instruments', 'evidence', 'errors'):
                    result[field].update(attempt.get(field, {}))
                state = attempt.get('instruments', {}).get(key)
                if state in ('IMPORTED', 'ALREADY_RETAINED'):
                    result['errors'].pop(key, None)
                    break
                if attempt.get('state') != 'CHECKED':
                    result['retry_state'] = attempt.get('state')
                    break
                error = attempt.get('errors', {}).get(key, {})
                if (error.get('stage'), error.get('error')) != ('verify five minute symbol', 'TimeoutError'):
                    break
        return result

    def export_watches(self, page, watches):
        from playwright.sync_api import Error

        page.set_default_timeout(2500)
        registered = mappings(self.service.folder.parent / 'radar-public-prices')
        instruments = dict.fromkeys(w['instrument'] for w in watches)
        instruments.update(dict.fromkeys(w.get('benchmark') for w in watches if w.get('benchmark')))
        result = {}
        errors = {}
        evidence = {}
        cache = IntradayCache(self.service.folder / 'intraday.sqlite3')
        stage = 'prepare chart'
        try:
            page.bring_to_front()
            charts = page.get_by_role('img', name=re.compile('5 minute candle chart'))
            if not charts.is_visible():
                for name in ('Search for security', 'Data Table'):
                    dialog = page.get_by_role('dialog', name=name)
                    if dialog.is_visible():
                        stage = f'close {name} dialog'
                        _dismiss(dialog)
                stage = 'open periodicity menu'
                _activate(page.get_by_role('button', name='Periodicity', exact=True))
                stage = 'select 5 minute interval'
                _activate(page.get_by_role('menuitem', name='5 Min', exact=True))
                stage = 'wait for 5 minute chart'
                charts.wait_for(state='visible')
            for instrument in instruments:
                code = registered.get(instrument)
                if not code:
                    result[instrument] = 'MAPPING_UNAVAILABLE'
                    continue
                try:
                    stage = 'export table'
                    symbol = f'{code}.JSE'
                    name, raw = _export(page, symbol)
                    stage = 'parse CSV'
                    now = datetime.now(timezone.utc)
                    records = viewpoint_table_csv(raw, instrument, symbol, now, file_name=name,
                                                 accept_operator_conventions=True)
                    digest = sha256(raw).hexdigest()
                    stage = 'retain evidence'
                    old = [row for row in cache.read(instrument)
                           if row.get('source_raw_sha256') == digest and row.get('bar_end')]
                    retained = {(row['bar_end'], row['provisional']) for row in old}
                    new_rows = [row for row in records
                                if (row['bar_end'], row['provisional']) not in retained
                                and (row['bar_end'], False) not in retained]
                    if new_rows:
                        cache.put_batch(new_rows, raw, evidence=True)
                    result[instrument] = 'IMPORTED' if new_rows else 'ALREADY_RETAINED'
                    evidence[instrument] = {'file_name': name, 'sha256': digest,
                                            'records': len(records),
                                            'checked_at': now.isoformat(),
                                            'received_at': now.isoformat() if new_rows else max(row['received_at'] for row in old),
                                            'latest_bar_end': max(row['bar_end'] for row in records)}
                except (Error, OSError, ValueError, sqlite3.Error) as exc:
                    errors[instrument] = exc.detail if isinstance(exc, ExportFailure) else _failure(exc, stage)
                    print(f'ViewPoint export failed for {instrument}: {json.dumps(errors[instrument])}', flush=True)
                    result[instrument] = 'EXPORT_UNAVAILABLE'
        except (Error, OSError) as exc:
            detail = _failure(exc, stage)
            print(f'ViewPoint chart setup failed: {json.dumps(detail)}', flush=True)
            return {'state': 'BROWSER_UNAVAILABLE', 'instruments': result, 'error': detail}
        return {'state': 'CHECKED', 'instruments': result, 'errors': errors, 'evidence': evidence}

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
                str(collector.profile), channel='msedge', headless=False, chromium_sandbox=True)
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
