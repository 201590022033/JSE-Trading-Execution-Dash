"""Thin Flask adapter for canonical read-only opportunity services."""
from flask import Blueprint,jsonify,request
from .service import serialize_opportunity,serialize_policy,serialize_risk

def error(code,message,status):return jsonify(error={'code':code,'message':message,'http_status':status}),status
def create_blueprint(service, refresh=None, research_screen=None):
 bp=Blueprint('canonical_opportunities',__name__)
 @bp.after_request
 def no_cache(response):
  response.headers['Cache-Control']='no-store'
  return response
 @bp.errorhandler(Exception)
 def unavailable(exc):
  from werkzeug.exceptions import HTTPException
  if isinstance(exc,HTTPException):return exc
  return error('CANONICAL_UNAVAILABLE','canonical repository unavailable; no fallback data supplied',503)
 @bp.post('/api/v1/opportunities/refresh')
 def refresh_listing():
  if research_screen is not None and request.args.get('view')!='paper' and request.args.get('asset_class')!='index_etf':
   return jsonify(**research_screen.trigger(),live_execution=False),202
  if refresh is None:return error('REFRESH_UNAVAILABLE','research refresh is not configured',503)
  return jsonify(**refresh.trigger(),live_execution=False),202
 @bp.get('/api/v1/opportunities')
 def listing():
  raw=request.args.get('limit');
  try:
   limit=int(raw) if raw is not None else None
   asset_class=request.args.get('asset_class')
   if research_screen is not None and request.args.get('view')!='paper' and asset_class in (None,'cash_equity'):
    items=research_screen.listing(limit)
    return jsonify(opportunities=items,count=len(items),score_semantics='descriptive price-momentum comparison; not probability of profit',
                   refresh=research_screen.status(),research_screen=True,live_execution=False)
   if asset_class is not None:
    from .paper_host import DurablePaperOpportunities
    if not isinstance(service,DurablePaperOpportunities):raise ValueError('asset class listing requires the durable research worker')
    items=service.list_opportunities(limit,asset_class=asset_class)
   else:items=service.list_opportunities(limit)
  except ValueError as exc:return error('INVALID_REQUEST',str(exc),422)
  metadata=refresh.status() if refresh is not None else {'state':'NOT_CONFIGURED'}
  return jsonify(opportunities=[serialize_opportunity(x) for x in items],count=len(items),score_semantics='comparative research score; not probability of profit',refresh=metadata,live_execution=False)
 @bp.get('/api/v1/opportunities/<oid>')
 def detail(oid):
  if research_screen is not None and oid.startswith('zebra-research-'):
   item=research_screen.detail(oid)
   return (jsonify(opportunity=item,live_execution=False),200) if item else error('OPPORTUNITY_NOT_FOUND','research opportunity not found',404)
  try:return jsonify(opportunity=serialize_opportunity(service.get_opportunity(oid)))
  except KeyError:return error('OPPORTUNITY_NOT_FOUND','opportunity not found',404)
 @bp.get('/api/v1/opportunities/<oid>/policy')
 def policy(oid):
  if research_screen is not None and oid.startswith('zebra-research-'):return error('RESEARCH_ONLY','research screen does not create paper policies',409)
  try:return jsonify(policy=serialize_policy(service.get_policy(oid)))
  except KeyError:
   if oid not in service._opportunities:return error('OPPORTUNITY_NOT_FOUND','opportunity not found',404)
   return error('POLICY_UNAVAILABLE','required upstream policy unavailable',503)
 @bp.get('/api/v1/opportunities/<oid>/risk')
 def risk(oid):
  if research_screen is not None and oid.startswith('zebra-research-'):return error('RESEARCH_ONLY','research screen does not create paper risk decisions',409)
  try:return jsonify(risk=serialize_risk(service.get_risk(oid)))
  except KeyError:
   if oid not in service._opportunities:return error('OPPORTUNITY_NOT_FOUND','opportunity not found',404)
   return error('RISK_UNAVAILABLE','required upstream risk evaluation unavailable',503)
 @bp.get('/api/v1/opportunities/<oid>/intent')
 def intent(oid):
  if research_screen is not None and oid.startswith('zebra-research-'):return error('RESEARCH_ONLY','research screen does not create trade intents',409)
  try:value=service.get_trade_intent_preview(oid)
  except KeyError:
   if oid not in service._opportunities:return error('OPPORTUNITY_NOT_FOUND','opportunity not found',404)
   return error('UPSTREAM_STATE_UNAVAILABLE','required upstream state unavailable',503)
  body={'intent':value.to_dict()}
  return (jsonify(body),200) if value.execution_readiness=='READY_FOR_PREVIEW' else (jsonify(**body,error={'code':'PREREQUISITE_UNRESOLVED','message':'trade intent prerequisites are unresolved','http_status':409}),409)
 return bp
