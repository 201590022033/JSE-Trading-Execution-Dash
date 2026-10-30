"""Local-only export ingress. No login, session, cookie or password endpoint."""
from datetime import datetime, timezone
import os
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from .ost_data import coverage, install_exports, read_primary, ROOT


def create_ost_blueprint(factory, folder=ROOT):
    bp = Blueprint('ost_onboarding', __name__)

    def local_import_allowed():
        return (os.environ.get('OST_LOCAL_IMPORT_ENABLED') == '1'
            and not os.environ.get('RAILWAY_ENVIRONMENT_ID')
            and request.remote_addr in ('127.0.0.1', '::1')
            and urlsplit(request.host_url).hostname in ('127.0.0.1', 'localhost', '::1'))

    @bp.get('/api/v1/ost/onboarding')
    def status():
        now = datetime.now(timezone.utc)
        if not os.environ.get('RAILWAY_ENVIRONMENT_ID'):
            data = read_primary(folder)
        else:
            from .swing_research import latest_dataset
            repo = factory()
            try: data = latest_dataset(repo)
            finally: repo.close()
        result = coverage(data, now)
        from .source_resolution import audit, local_audit, attach_iress_research
        result['source_resolution'] = (audit(data, now) if os.environ.get('RAILWAY_ENVIRONMENT_ID')
                                       else local_audit(data, now, folder))
        from .supplemental_data import input_status
        preview_data = data if os.environ.get('RAILWAY_ENVIRONMENT_ID') or not data else attach_iress_research(data, now, folder)
        result['numerical_research'] = input_status(preview_data, now)
        if not os.environ.get('RAILWAY_ENVIRONMENT_ID'):
            from .iress_price_only import latest
            price = latest(folder, now)
            if price:
                from .supplemental_data import hlc_research
                result['numerical_research']['price_only_sasol'] = {
                    'state': 'AVAILABLE', 'provider': price['provider'],
                    'source_sha256': price['source_sha256'], 'acquired_at': price['acquired_at'],
                    'last_session': price['bars'][-1]['timestamp'], 'sessions': len(price['bars']),
                    'volume_basis': price['volume_basis'], 'historical_availability': price['historical_availability'],
                    'technical': hlc_research(price, now), 'research_only': True}
        if not os.environ.get('RAILWAY_ENVIRONMENT_ID'):
            from .prospective_prices import capture_summary, prospective_outcomes
            result['prospective_prices'] = capture_summary(folder)
            result['prospective_outcomes'] = prospective_outcomes(folder)
        result['local_import_available'] = local_import_allowed()
        return jsonify(result)

    @bp.get('/api/v1/ost/price-only/<instrument>')
    def price_only(instrument):
        from .iress_price_only import latest
        chart = None if os.environ.get('RAILWAY_ENVIRONMENT_ID') or instrument != 'SASOL' else latest(folder, datetime.now(timezone.utc))
        response = jsonify({'state': 'AVAILABLE' if chart else 'UNAVAILABLE', 'chart': chart,
                            'live_execution': False})
        response.headers['Cache-Control'] = 'no-store'
        return response, 200 if chart else 503

    @bp.post('/api/v1/ost/import')
    def import_export():
        if not local_import_allowed() or request.headers.get('Origin') != request.host_url.rstrip('/'):
            return jsonify(error='Import requires the local dashboard and same-origin request'), 403
        if request.content_length is None or request.content_length > 2_700_000:
            return jsonify(error='Maximum request size is 2.7 MB'), 413
        try:
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or data.get('instrument_confirmed') is not True:
                raise ValueError('instrument confirmation required')
            rows = data['exports']
            if not isinstance(rows, list) or not 1 <= len(rows) <= 34:
                raise ValueError('bounded exports required')
            exports = [{'instrument_id': row['instrument_id'], 'acquired_at': row['acquired_at'],
                        'raw': row['csv'].encode('utf-8')} for row in rows]
            result = install_exports(exports, datetime.now(timezone.utc), folder)
            result['upload_state'] = 'LOCAL_ONLY_NEXT_SCHEDULED_UPLOAD'
            return jsonify(result), 201
        except (ValueError, KeyError, TypeError, UnicodeError, OverflowError):
            return jsonify(error='Export rejected. Check OST headers, selected instrument, actual capture time, numeric values and duplicates.'), 422

    @bp.post('/api/v1/ost/alternative-import')
    def import_alternative():
        if not local_import_allowed() or request.headers.get('Origin') != request.host_url.rstrip('/'):
            return jsonify(error='Alternative import requires the local dashboard and same-origin request'), 403
        if request.content_length is None or request.content_length > 2_700_000:
            return jsonify(error='Maximum request size is 2.7 MB'), 413
        try:
            from .source_resolution import install_iress_candidate, local_audit
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or data.get('instrument_confirmed') is not True or data.get('provider') != 'IRESS':
                raise ValueError('exact provider and instrument confirmation required')
            now = datetime.now(timezone.utc)
            chart = install_iress_candidate(data['csv'].encode('utf-8'), data['instrument_id'],
                data['origin_symbol'], data['acquired_at'], now, folder)
            report = local_audit(read_primary(folder), now, folder)
            return jsonify({'state': 'WHOLE_SOURCE_CANDIDATE_REGISTERED_LOCAL_ONLY',
                'instrument_id': chart['instrument_id'], 'resolution': report['instruments'][chart['instrument_id']],
                'primary_policy_unchanged': True, 'real_data_admitted': False}), 201
        except (ValueError, KeyError, TypeError, UnicodeError, OverflowError):
            return jsonify(error='IRESS candidate rejected. Check exact JSE symbol, daily CSV columns, capture time and OHLCV values.'), 422

    @bp.errorhandler(Exception)
    def failed(exc):
        from werkzeug.exceptions import HTTPException
        return exc if isinstance(exc, HTTPException) else (jsonify(error='OST onboarding unavailable'), 503)
    return bp
