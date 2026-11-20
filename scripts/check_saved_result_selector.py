"""Exercise the Backtest Lab selector and Flask endpoints in headless Edge."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Environment
from playwright.sync_api import expect, sync_playwright

from application.backtest_lab.exact_run_job import available_profiles

from test_backtest_lab import BacktestLabTests


def check_selector():
    root = Path(__file__).resolve().parents[1]
    template = (root / 'templates/dashboard.html').read_text(encoding='utf-8')
    lab = template[template.index('<section id="backtest-lab"'):template.index('<section id="portfolio"')]
    lab = Environment(autoescape=True).from_string(lab).render(
        backtest_shares=['MTN', 'VOD'], backtest_profiles=available_profiles(),
    )
    html = (
        '<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/lab.css">'
        '<nav><button data-tab="backtest-lab">Backtest Lab</button></nav>' + lab +
        '<script src="/lab.js"></script>'
    )
    script = (root / 'static/js/backtest-lab.js').read_text(encoding='utf-8')
    stylesheet = (root / 'static/css/backtest-lab.css').read_text(encoding='utf-8')
    BacktestLabTests.setUpClass()
    fixture = BacktestLabTests()
    visited = []
    with TemporaryDirectory() as folder:
        initial_id = fixture.save(folder)
        exact = deepcopy(fixture.report)
        exact['bars']['VOD'] = exact['bars']['SOL']
        exact['meta'].update(grade='REAL', source_receipts=[{
            'instrument': 'VOD', 'product': 'cash_equity', 'provider': 'FIXTURE',
            'acquired_at': '2026-11-19T10:00:00+02:00', 'source_sha256': 'a' * 64,
        }])
        profile = exact['strategies'][0]
        profile['timeframe'] = '1d'
        exact_id = fixture.rehash(exact)
        fixture.save(folder, exact)
        client = fixture.app(folder)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                headless=True,
            )
            page = browser.new_page(viewport={'width': 390, 'height': 844})

            sector_timeouts = {exact_id}
            held_index = []
            hold_first_index = True

            def serve(route):
                nonlocal hold_first_index
                method = route.request.method
                url = route.request.url
                prefix = 'http://backtest-fixture.test'
                if not url.startswith(prefix + '/'):
                    route.abort()
                    return
                path = url[len(prefix):]
                visited.append((method, path))
                resources = {'/': (html, 'text/html'), '/lab.js': (script, 'text/javascript'),
                             '/lab.css': (stylesheet, 'text/css')}
                if path in resources:
                    body, content_type = resources[path]
                    route.fulfill(body=body, content_type=content_type)
                elif path == '/api/v1/strategy-radar/watches':
                    route.fulfill(json={'watches': [{'instrument': 'MTN'}, {'instrument': 'VOD'}]})
                elif path.startswith('/api/v1/backtest-lab/runs/index?') and hold_first_index:
                    hold_first_index = False
                    held_index.append(route)
                elif path.endswith('/sector-research') and any(
                    f'/runs/{run_id}/' in path for run_id in sector_timeouts
                ):
                    sector_timeouts.clear()
                    route.fulfill(status=503, json={'state': 'READ_TIMED_OUT'})
                elif path.startswith('/api/v1/backtest-lab/'):
                    response = client.get(path)
                    route.fulfill(status=response.status_code, body=response.get_data(),
                                  content_type=response.content_type)
                else:
                    route.fulfill(status=404, json={})

            page.route('**/*', serve)
            page.goto('http://backtest-fixture.test/')
            page.get_by_role('button', name='Backtest Lab').click()
            steps = page.locator('#backtest-lab > section > h3').all_text_contents()
            assert steps == ['1. Choose a share', '2. Choose a hypothesis',
                             '3. Choose a strategy and version', '4. Review the result'], steps
            assert page.locator('#backtest-lab > details').count() == 4
            assert page.locator('#backtest-lab > details[open]').count() == 0
            assert page.locator('#bl-step-result').evaluate(
                "el => ['bl-trades','bl-price'].every(id => el.parentElement.contains(document.getElementById(id)))")
            share = page.get_by_label('Share', exact=True)
            expect(share).to_have_value('MTN')
            status = page.locator('#bl-status')
            expect(status).to_have_text('Loading saved results…')
            share.select_option('VOD', timeout=2000)
            page.get_by_role('button', name='Run a backtest for this share').click(timeout=2000)
            profiles = page.get_by_label('Exact strategy version')
            expect(profiles).to_be_enabled(timeout=2000)
            profiles.select_option(index=1, timeout=2000)
            assert len(held_index) == 1
            held_index.pop().fulfill(status=503, json={'state': 'READ_TIMED_OUT'})
            expect(status).to_contain_text('Timed out')
            share.select_option('MTN', timeout=2000)
            expect(profiles).to_be_enabled(timeout=2000)
            expect(page.get_by_label('Saved result', exact=True)).to_be_hidden()
            status.get_by_role('button', name='Retry').click()
            expect(status).to_have_text('No saved results for MTN.')
            share.select_option('VOD')
            selector = page.get_by_label('Saved result', exact=True)
            expect(selector.locator('option')).to_have_count(1)
            expect(selector).to_have_value(exact_id)
            expect(selector.locator('option')).to_contain_text('VOD')
            expect(selector.locator('option')).not_to_contain_text(exact_id)
            expect(page.locator('#bl-run-details')).to_be_visible()
            page.locator('#bl-fold-research summary').first.click()
            sector_status = page.locator('#bl-research-choice')
            expect(sector_status).to_contain_text('Timed out')
            sector_status.get_by_role('button', name='Retry').click()
            expect(sector_status).not_to_contain_text('Loading sector research')
            expect(sector_status).not_to_contain_text('Timed out')
            expect(page.locator('#bl-trades-title')).to_have_text('Trades · VOD')
            expect(page.locator('#bl-price-title')).to_have_text('Price chart · VOD')
            expect(page.locator('#bl-trades th').first).to_have_text('Instrument')
            expect(page.locator('#bl-result-banner')).to_contain_text('30-closed-trade floor')
            expect(page.locator('#bl-w06-sample')).to_contain_text('3 original-rule trades')
            assert set(page.locator('#bl-trades tbody tr td:first-child').all_text_contents()) <= {'VOD'}
            portfolio = page.get_by_label('Show whole portfolio')
            portfolio.check()
            expect(page.locator('#bl-trades-title')).to_have_text('Trades · Whole portfolio')
            expect(page.locator('#bl-instruments')).to_be_visible()
            portfolio.uncheck()
            expect(page.locator('#bl-instruments')).to_be_hidden()
            page.locator('#bl-run-details summary').click()
            expect(page.locator('#bl-run-metadata')).to_contain_text(exact_id)
            share.select_option('SOL')
            expect(selector.locator('option')).to_have_count(2)
            selector.select_option(initial_id)
            expect(page.locator('#bl-run-metadata')).to_contain_text(initial_id)
            share.select_option('MTN')
            expect(page.locator('#bl-content')).to_be_hidden()
            expect(page.locator('#bl-run-details')).to_be_hidden()
            page.evaluate('selection => {window.strategyRadarHandoff = Object.freeze(selection);}', {
                'instrument': 'VOD', 'product': 'CASH_SHARE', 'strategy_id': profile['strategy_profile_id'],
                'strategy_version': profile['strategy_profile_version'], 'timeframe_minutes': None,
            })
            page.get_by_role('button', name='Backtest Lab').click()
            expect(share).to_have_value('VOD')
            expect(selector).to_have_value(exact_id)
            expect(page.locator('#bl-status')).to_contain_text('Exact selected profile and instrument')
            browser.close()
    assert all(method == 'GET' for method, _ in visited)
    assert any(path.startswith('/api/v1/backtest-lab/runs/index?instrument=VOD') for _, path in visited)
    print('PASS selectable share and version during slow and timed-out index, retry, saved result and exact Radar handoff')


if __name__ == '__main__':
    check_selector()
