"""Authenticated bounded local-data ingress; research reads are public."""
from datetime import datetime, timezone
import hmac
import os
from flask import Blueprint, jsonify, request
from .swing_research import accept_dataset, research_status


def create_research_blueprint(factory):
    bp = Blueprint("swing_research", __name__)

    @bp.post("/api/v1/swing-research/datasets")
    def upload():
        expected = os.environ.get("SWING_DATA_UPLOAD_TOKEN", "")
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
            return jsonify(error="Data upload authentication required"), 401
        if request.content_length is None or request.content_length > 2_000_000:
            return jsonify(error="Bounded dataset body required"), 413
        payload = request.get_json(silent=True)
        repository = factory()
        try:
            return jsonify(accept_dataset(repository, payload, datetime.now(timezone.utc))), 202
        except (ValueError, TypeError, KeyError, OverflowError):
            return jsonify(error="Dataset rejected: check canonical identity, dates, raw fields and bounds"), 422
        finally:
            repository.close()

    @bp.get("/api/v1/swing-research/status")
    def status():
        repository = factory()
        try:
            return jsonify(research_status(repository, datetime.now(timezone.utc)))
        finally:
            repository.close()

    @bp.get('/api/v1/swing-research/historical-readiness')
    def historical_readiness():
        import json
        from .ost_data import ROOT
        from .research_classification import classifications
        from .swing_historical_inputs import prepare_v3_research
        try:
            dataset=json.loads((ROOT/'latest.json').read_bytes())
            ready=prepare_v3_research(dataset,datetime.now(timezone.utc),ROOT)
            keys=sorted(k for k in ready['charts'] if k!='ETF_STX40')
            labels=classifications(keys)['instruments']; sectors={}
            for key in keys: sectors.setdefault(labels[key]['sector'],[]).append(key)
            sector_sessions={sector:len({r['timestamp'] for key in members for r in ready['charts'][key]['bars']}) for sector,members in sectors.items()}
            state='HISTORICAL_RESEARCH_READY' if any(n>=130 for n in sector_sessions.values()) else 'MORE_HISTORY_REQUIRED'
            from .swing_research import swing_cloud_provider
            model_configured=bool(swing_cloud_provider()[1].key)
            response=jsonify(state=state,instruments=keys,sectors=sectors,sector_sessions=sector_sessions,
                freshness=ready['freshness'],instrument_freshness=ready.get('instrument_freshness',{}),source=ready['source'],limitations=ready['limitations'],
                model_configured=model_configured,model_called=False,live_execution=False)
            response.headers['Cache-Control']='no-store'
            return response
        except (OSError,ValueError,KeyError,TypeError,AttributeError,ArithmeticError):
            response=jsonify(state='HISTORICAL_INPUT_UNAVAILABLE',model_called=False,live_execution=False)
            response.headers['Cache-Control']='no-store'
            return response,503

    @bp.errorhandler(Exception)
    def unavailable(exc):
        from werkzeug.exceptions import HTTPException
        return exc if isinstance(exc, HTTPException) else (jsonify(error="Swing research unavailable"), 503)
    return bp
