"""OI2 operational dashboard; analysis-only, with no live execution path."""
import os

from flask import Flask, g, jsonify, render_template, request
from flask_socketio import SocketIO
from instrument_registry import instrument_list, resolve_instrument
from market_chart_registry import market_chart_list, MARKET_CHART_INSTRUMENTS
from operational_intelligence import service
from dashboard_feeds import feeds
from market_intelligence.source_registry import SourceRegistry
from market_intelligence.store import MarketIntelligenceStore
from market_intelligence import TickerSelection
from datetime import datetime, timezone
from uuid import uuid4
from application.opportunities import OpportunityService
from application.opportunities.api import create_blueprint
from application.opportunities.service import serialize_opportunity
from application.opportunities.refresh import OpportunityRefresh
from application.opportunities.public_research import (
    public_instrument_classes, public_share_catalog, public_share_list, persisted_shadow_evidence,
    refresh_public_research,
)
from runtime_persistence import runtime_repository

def request_source_registry():
    registry=SourceRegistry(application_repository().store)
    registry.seed_defaults()
    return registry
portfolio_rows = []

app = Flask(__name__); app.config["SECRET_KEY"] = os.environ.get("PAPER_CONTROL_TOKEN") or "local-oi2-session"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                  SESSION_COOKIE_SECURE=bool(os.environ.get('RAILWAY_ENVIRONMENT_ID')))
socketio = SocketIO(app, cors_allowed_origins="*")
canonical_opportunity_service = OpportunityService()
def canonical_refresh_runner():
    from domain.strategy import DEFAULT_STRATEGY_REGISTRY
    from domain.strategy.attribution import freeze_profile
    profile = DEFAULT_STRATEGY_REGISTRY.resolve("jse_swing_3_5d", "1.0.1")
    evaluated_at = datetime.now(timezone.utc)
    repository = runtime_repository()
    try:
        repository.save_strategy_definition(freeze_profile(profile))
        news_snapshot = feeds.news()
        news_report = ({**news_snapshot["data"], "available_at": news_snapshot["last_success"]}
                       if news_snapshot.get("state") in {"AVAILABLE", "PARTIAL"}
                       and news_snapshot.get("data") and news_snapshot.get("last_success") else None)
        learned = persisted_shadow_evidence(repository, evaluated_at=evaluated_at)
        from application.opportunities.ost_data import read_primary, LocalOSTFetcher, SCHEMA
        from application.opportunities.swing_research import latest_dataset
        primary = latest_dataset(repository) if os.environ.get('RAILWAY_ENVIRONMENT_ID') else read_primary()
        research_fetcher = LocalOSTFetcher(primary, evaluated_at) if primary and primary.get('schema') == SCHEMA else None
        return refresh_public_research(fetcher=research_fetcher, evaluated_at=evaluated_at, news_report=news_report,
                                       learned_evidence=learned, strategy_profile=profile.reference)
    finally:
        repository.close()
from application.opportunities.paper_host import (
    configured_paper, DurablePaperOpportunities, PaperRefreshStatus, paper_status,
)
paper_config = configured_paper()
if paper_config:
    canonical_opportunity_service = DurablePaperOpportunities(runtime_repository, paper_config)
    canonical_opportunity_refresh = PaperRefreshStatus(runtime_repository, paper_config)
else:
    canonical_opportunity_refresh = OpportunityRefresh(canonical_opportunity_service,
                                                      runner=canonical_refresh_runner)
app.register_blueprint(create_blueprint(canonical_opportunity_service, canonical_opportunity_refresh))
from application.strategy_profiles import create_strategy_blueprint
app.register_blueprint(create_strategy_blueprint())
from application.opportunities.swing_research_api import create_research_blueprint
app.register_blueprint(create_research_blueprint(runtime_repository))
from application.opportunities.local_backtest_reports import create_local_backtest_blueprint
app.register_blueprint(create_local_backtest_blueprint())
from application.opportunities.learning_overview import create_learning_overview_blueprint
app.register_blueprint(create_learning_overview_blueprint(runtime_repository))
from application.opportunities.ost_data_api import create_ost_blueprint
app.register_blueprint(create_ost_blueprint(runtime_repository))
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
app.register_blueprint(create_weekly_brief_blueprint(runtime_repository))
from application.opportunities.operator_api import create_operator_blueprint, has_access
app.register_blueprint(create_operator_blueprint(runtime_repository, paper_config))
from connected_portfolio_api import create_connected_blueprint
app.register_blueprint(create_connected_blueprint(runtime_repository))

@app.get("/api/paper/status")
def paper_account_status():
    if paper_config is None:
        return jsonify(state="NOT_CONFIGURED", mode="PAPER", live_execution=False)
    try:
        return jsonify(**paper_status(application_repository(), paper_config), control_access=has_access())
    except Exception:
        return jsonify(state="UNAVAILABLE", mode="PAPER", live_execution=False), 503

def application_repository():
    """Canonical repository selection shared with the bounded worker."""
    if "application_repository" not in g:
        g.application_repository = runtime_repository()
    return g.application_repository

def application_reliability():
    from reliability_store import runtime_repository_reliability
    if 'application_reliability' not in g:
        g.application_reliability=runtime_repository_reliability(application_repository())
    return g.application_reliability

@app.teardown_appcontext
def close_market_store(error=None):
    store = g.pop("market_store", None)
    if store is not None:
        store.close()
    repository = g.pop("application_repository", None)
    if repository is not None: repository.close()

@app.get("/")
def index(): return render_template("dashboard.html")
@app.get("/health")
def health():
    mode = os.environ.get("APP_MODE", "DEVELOPMENT").upper()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    production = mode not in {"DEVELOPMENT", "RESEARCH"}
    database = "CONFIGURED_POSTGRES" if database_url.lower().startswith(("postgresql://", "postgres://")) else (
        "MISSING_POSTGRES" if production else "LOCAL_SQLITE")
    healthy = database != "MISSING_POSTGRES"
    state='UNAVAILABLE'
    if healthy:
        try: state=application_repository().readiness()['state']
        except Exception: state='UNAVAILABLE'
        healthy=state=='AVAILABLE'
    return jsonify(status="ok" if healthy else "degraded", application="trading-system",
                   service="oi2", database=database, database_state=state, mode=mode, live_execution=False), (200 if healthy else 503)
@app.get("/api/system/status")
def status(): return jsonify(service.status())
@app.get("/api/learning/status")
def learning_status():
    """Read-only persisted shadow-learning counters; never includes secrets."""
    try:
        repository = application_repository()
        status = repository.learning_status()
        if paper_config is not None:
            paper = paper_status(repository, paper_config)
            status["daily_swing"] = paper.get("learning", {
                "state": paper.get("state", "UNAVAILABLE"),
                "kind": "Ranked LONG swing effectiveness after declared costs",
            })
            status["candidate_learning"] = paper.get("candidate_learning", {
                "state": paper.get("state", "UNAVAILABLE"),
            })
        return jsonify(**status, live_execution=False)
    except Exception:
        return jsonify(database_state='UNAVAILABLE',live_execution=False),503
@app.get('/api/learning/reliability/<source_id>')
def learning_reliability(source_id):
    from dataclasses import asdict
    try:
        return jsonify(**asdict(application_reliability().summarize(source_id)),live_execution=False)
    except Exception:
        return jsonify(database_state='UNAVAILABLE',live_execution=False),503
@app.get("/api/market-intelligence/sources")
def intelligence_sources():
    return jsonify(sources=[s.__dict__ for s in request_source_registry().list_policies()])
@app.post("/api/market-intelligence/sources/<source_id>")
def intelligence_source_toggle(source_id):
    from application.opportunities.operator_api import has_access
    if not has_access():
        return jsonify(error='Unlock Portfolio controls before changing source policy'), 401
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or type(body.get('enabled')) is not bool:
        return jsonify(error='An explicit JSON boolean enabled value is required'), 422
    return jsonify(source=request_source_registry().enable(source_id, body['enabled']).__dict__)
@app.get("/api/market-intelligence")
def market_intelligence():
    store = request_source_registry().store
    narrative = store.latest_narrative()
    return jsonify(narrative=narrative.to_dict() if narrative else None,
                   sources=[s.__dict__ for s in request_source_registry().list_policies()],
                   selections=[s.__dict__ for s in store.active_ticker_selections()],
                   state="AVAILABLE" if narrative else "UNAVAILABLE",
                   live_execution=False)
@app.post("/api/market-intelligence/refresh")
def refresh_market_intelligence():
    """Run one bounded, read-only public-news intelligence refresh."""
    from market_intelligence.schemas import MarketNarrative, MarketTheme

    result = feeds.news()
    report = result.get("data") or {}
    if not report:
        return jsonify(state="LOADING", message="Public sources are still being fetched; retry shortly.",
                       live_execution=False), 202

    generated_at = datetime.now(timezone.utc).isoformat()
    themes = []
    for name, value in (report.get("macro") or {}).items():
        mentions = int(value.get("mentions") or 0)
        if not mentions:
            continue
        score = float(value.get("score") or 0)
        themes.append(MarketTheme(
            theme=name, direction=1 if score > 0 else -1 if score < 0 else 0,
            confidence=min(1.0, mentions / 5.0), expected_horizon="CURRENT_PUBLIC_NEWS",
            generated_at=generated_at,
        ))
    narrative = MarketNarrative(
        narrative_id=f"public-news:{uuid4().hex}", generated_at=generated_at,
        model="deterministic-keyword-summary", provider="public-news-feed",
        schema_version="market-intelligence-v2",
        summary=("Current public-news themes are available for investigation. "
                 "This is research context, not a recommendation or trading signal."),
        themes=themes, candidates=[],
        enabled_sources=list((report.get("sources") or {}).keys()),
        metadata={"analysis_method": report.get("analysis_method"), "research_only": True},
    )
    store = request_source_registry().store
    store.save_narrative(narrative)
    return jsonify(narrative=narrative.to_dict(), state="AVAILABLE", live_execution=False)
@app.post("/api/market-intelligence/pin")
def pin_intelligence():
    body = request.get_json(silent=True) or {}
    symbol, instrument_id = str(body.get("display_symbol", "")).strip(), str(body.get("instrument_id", "")).strip()
    if not symbol or not instrument_id or len(symbol) > 32 or len(instrument_id) > 64:
        return jsonify(error="instrument_id and display_symbol are required"), 400
    store = request_source_registry().store
    selection = TickerSelection(instrument_id, symbol, True, "User-pinned instrument", None, None,
                                [], datetime.now(timezone.utc).isoformat())
    store.save_ticker_selection(selection)
    return jsonify(selection=selection.__dict__, live_execution=False)
@app.get("/api/market-intelligence/provenance/<entity_type>/<entity_id>")
def intelligence_provenance(entity_type, entity_id):
    if entity_type not in {"document", "theme", "instrument_candidate", "watchlist"}:
        return jsonify(error="unsupported provenance entity"), 400
    return jsonify(edges=request_source_registry().store.provenance_for(entity_type, entity_id), live_execution=False)
@app.get("/api/market-intelligence/ticker")
def intelligence_ticker():
    selections = request_source_registry().store.active_ticker_selections()
    return jsonify(items=[s.__dict__ for s in selections], state="AVAILABLE" if selections else "UNAVAILABLE",
                   message="No pinned or AI-selected instruments are currently available." if not selections else None,
                   live_execution=False)
@app.post("/api/portfolio/csv")
def portfolio_csv():
    import csv, io
    global portfolio_rows
    body = request.get_json(silent=True) or {}
    text = body.get("csv", "")
    if not text.strip(): return jsonify(error="CSV content is required"), 400
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"instrument", "quantity"}
    if not rows or not required.issubset(rows[0]):
        return jsonify(error="CSV must include instrument and quantity columns"), 400
    portfolio_rows = rows
    return jsonify(rows=portfolio_rows, count=len(rows), state="IMPORTED_CSV", live_execution=False)
@app.get("/api/portfolio")
def portfolio(): return jsonify(rows=portfolio_rows, state="IMPORTED_CSV" if portfolio_rows else "NOT_LOADED", live_execution=False)
@app.get("/api/account/status")
def account_status():
    from connected_accounts import cached_ig_status
    return jsonify({**cached_ig_status(), "live_execution": False})
@app.get("/api/instruments")
def instruments(): return jsonify(instruments=instrument_list())
@app.get("/api/public-shares")
def public_shares():
    return jsonify(instruments=public_share_list(), classes=public_instrument_classes(),
                   state="CURATED_PUBLIC_CASH_SHARES", live_execution=False)
@app.get("/api/market-chart-instruments")
def market_chart_instruments():
    return jsonify(instruments=market_chart_list(), state="READ_ONLY_CHART_CATALOG",
                   canonical_ranking=False, live_execution=False)
@app.get("/api/feed/market/<instrument>")
def market_feed(instrument):
    if instrument in MARKET_CHART_INSTRUMENTS:
        return respond(lambda: feeds.reference_chart(instrument, request.args.get("period", "3mo")))
    if instrument in public_share_catalog() and instrument not in {item["instrument_id"] for item in instrument_list()}:
        return respond(lambda: feeds.public_chart(instrument, request.args.get("period", "3mo")))
    return respond(lambda: feeds.chart(instrument, request.args.get("period", "3mo")))
@app.get("/api/feed/news")
def news_feed(): return jsonify(feeds.news())
@app.get("/api/opportunities")
def opportunities():
    """Compatibility read model backed only by the canonical M13 service."""
    try:
        items = canonical_opportunity_service.list_opportunities(limit=10)
        status = canonical_opportunity_refresh.status()
    except Exception:
        return jsonify(state="UNAVAILABLE", canonical=True, live_execution=False), 503
    return jsonify(state="AVAILABLE" if items else "INSUFFICIENT_EVIDENCE",
                   data={"opportunities": [serialize_opportunity(item) for item in items],
                         "scanned": status["scanned"],
                         "method": "canonical M13 research ranking",
                         "execution_enabled": False},
                   canonical=True, live_execution=False)
@app.get("/api/market/<instrument>")
def market(instrument): return respond(lambda: service.market(instrument, request.args.get("provider", "historical")))
@app.post("/api/analysis/<instrument>")
def analysis(instrument):
    body=request.get_json(silent=True) or {}
    return respond(lambda: service.analyze(instrument, body.get("horizon","swing"), body.get("provider","historical"), bool(body.get("allow_network",False))))
@app.post("/api/analysis/<instrument>/technical")
def technical(instrument): return respond(lambda: service.technical(instrument))
@app.get("/api/technical-intelligence/<instrument>")
def technical_intelligence(instrument):
    result = service.technical(instrument)
    indicators = result.get("data", {}).get("metrics", {}) if result.get("success") else {}
    names = ("rsi", "sma", "breakout", "stochastic", "macd", "bollinger_mean_reversion", "adx_dmi", "ichimoku")
    rows = [{"name": name, "state": "CURRENTLY_CONTRIBUTING" if name in indicators or name in {"sma", "breakout", "stochastic"} else "RESEARCH_ONLY",
             "value": indicators.get(name), "signal": indicators.get(name + "_signal"),
             "reason": None if name in indicators or name in {"sma", "breakout", "stochastic"} else "Implemented in research path; not admitted to production UI scoring"}
            for name in names]
    return jsonify(instrument=resolve_instrument(instrument).to_dict(), technical=result,
                   indicators=rows, flow=[{"id":"instrument","label":"Instrument","state":"ACTIVE"},
                                          {"id":"technical","label":"Technical indicators","state":result.get("state")},
                                          {"id":"assessment","label":"Current assessment","state":"LEGACY BENCHMARK"}],
                   boundary="RESEARCH_ONLY; NO TRADE", live_execution=False)
@app.post("/api/analysis/<instrument>/news")
def news(instrument):
    body=request.get_json(silent=True) or {}
    return respond(lambda: service.news(instrument, bool(body.get("allow_network",False))))
@app.post("/api/scan/market")
def scan():
    body=request.get_json(silent=True) or {}
    return jsonify(runs=service.scan(body.get("horizon","swing")), live_execution=False)
@app.get("/api/analysis/run/<run_id>")
def run_detail(run_id):
    run=service.runs.get(run_id)
    return (jsonify(run.to_dict()),200) if run else (jsonify(error="run not found"),404)
@app.get("/api/research/<instrument>")
def research(instrument): return respond(lambda:{"instrument":resolve_instrument(instrument).to_dict(),"state":"RESEARCH","hr10":"validated no-trade boundary","promotion":"not authorized","message":"Historical diagnostics; not a current recommendation."})
@app.post("/api/trade/<suggestion_id>/manual")
def manual(suggestion_id): return jsonify(accepted=False,suggestion_id=suggestion_id,live_execution=False,reason="No OI2 strategy is admitted; broker handoff remains disabled."),409
@app.get("/api/snapshot")
def snapshot(): return jsonify(live=False,data_state="HISTORICAL",quotes=[])
@app.get("/api/demo-suggestion")
def demo(): return jsonify(state="rejected",direction="no_trade",safety={"actionable":False,"live_execution_available":False,"reasons":["demo_removed","no_admitted_strategy"]})
def respond(operation):
    try: return jsonify(operation())
    except KeyError as exc: return jsonify(error=str(exc)),404
    except ValueError as exc: return jsonify(error=str(exc)),400
if __name__ == "__main__":
    socketio.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
        allow_unsafe_werkzeug=True,
    )
