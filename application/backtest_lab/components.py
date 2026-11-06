"""Versioned, declarative swing-component research; no execution authority."""
from dataclasses import dataclass, asdict
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from math import isfinite
from application.opportunities.swing_technical import snapshot
from domain.backtest.component_engine import Signal
from domain.evaluation.experiment import configuration_hash
from domain.strategy import DEFAULT_STRATEGY_REGISTRY

VERSION='swing-component-research-v1'

@dataclass(frozen=True)
class Components:
 family:str='swing'
 entry:str='breakout_or_reclaim'
 trend:bool=True
 momentum:bool=True
 rsi_min:float=50
 rsi_max:float=70
 volume_mode:str='threshold'
 volume_min:float=1.0
 benchmark_mode:str='outperform'
 stop_mode:str='snapshot'
 stop_pct:float=0.05
 atr_multiple:float=1.0
 target_r:float|None=2.0
 horizon:int=3
 trail:str='NONE'
 trail_k:float=1.5
 trail_activation_r:float=1.0
 exit_mode:str='HORIZON_OR_TARGET'
 max_notional:float=420000
 risk_budget:float=12000
 profile_id:str='jse_swing_3_5d'
 profile_version:str='1.3.0'
 def __post_init__(self):
  profiles={'swing':'jse_swing_3_5d','box':'box_breakout_daily_research',
            'vcp':'vcp_daily_research','pull':'pullback_daily_research'}
  if self.family not in profiles or self.profile_id!=profiles[self.family]:raise ValueError('exact family/profile identity required')
  entries=('breakout_or_reclaim','breakout','reclaim','trend_only') if self.family=='swing' else ('family_default','trigger_only','trend_only')
  if self.entry not in entries:raise ValueError('unsupported entry')
  if self.volume_mode not in ('off','threshold') or self.benchmark_mode not in ('off','outperform'):raise ValueError('unsupported filter')
  if self.stop_mode not in ('snapshot','family','atr','structure','percent') or self.trail not in ('NONE','ATR','STRUCTURE'):raise ValueError('unsupported stop')
  if self.horizon not in (3,4,5):raise ValueError('unsupported horizon')
  if self.exit_mode not in ('HORIZON_OR_TARGET','EMA21_CLOSE'):raise ValueError('unsupported exit')
  nums=(self.rsi_min,self.rsi_max,self.volume_min,self.stop_pct,self.atr_multiple,self.trail_k,self.trail_activation_r,self.max_notional,self.risk_budget)
  if any(not isfinite(float(x)) for x in nums) or not 0<=self.rsi_min<=self.rsi_max<=100 or self.volume_min<0 or not 0<self.stop_pct<1 or min(self.atr_multiple,self.trail_k,self.trail_activation_r,self.max_notional,self.risk_budget)<=0:raise ValueError('invalid component value')
  if self.target_r is not None and (not isfinite(float(self.target_r)) or self.target_r<=0):raise ValueError('invalid target')
  DEFAULT_STRATEGY_REGISTRY.resolve(self.profile_id,self.profile_version)
 @property
 def config_hash(self):return configuration_hash({'version':VERSION,**asdict(self)})


def _rule(name,value,state,description):
 return {'c':name,'t':description,'v':value,'state':'UNKNOWN' if state is None else 'PASS' if state else 'FAIL','ok':state is True}


def _family_without_volume(family, rows):
 """Price-only equivalent of the existing family rules when volume is off.

 The formula parity is tested against the pinned family evaluator; no activity
 is invented. A volume threshold still requires real observed activity.
 """
 from statistics import mean
 from domain.features.technical import _ema
 from application.backtest_lab.strategies import condition
 if len(rows)<51:return [],None
 close=[float(r['close']) for r in rows];high=[float(r['high']) for r in rows];low=[float(r['low']) for r in rows]
 e9,e21=_ema(close,9),_ema(close,21);trend=close[-1]>e9>e21
 if family=='vcp':
  recent=mean(high[j]-low[j] for j in range(len(rows)-6,len(rows)-1))
  prior=mean(high[j]-low[j] for j in range(len(rows)-21,len(rows)-6))
  ratio=recent/prior if prior else None
  rules=[condition('Trend','Close above EMA9 above EMA21',close[-1]-e9,trend),
   condition('Contraction','Prior five-bar range ≤ 0.8× previous fifteen',ratio,ratio is not None and ratio<=.8),
   condition('Breakout','Close above prior 10-bar high',close[-1]-max(high[-11:-1]),close[-1]>max(high[-11:-1])),
   condition('Volume','Volume at least 1.3× prior 20-bar average',None,True)]
  stop=min(low[-6:])
 elif family=='box':
  top,bottom=max(high[-9:-1]),min(low[-9:-1]);width=(top-bottom)/close[-2]*100
  rules=[condition('Trend','Close above EMA9 above EMA21',close[-1]-e9,trend),
   condition('Tight box','Prior eight-bar range ≤ 6%',width,width<=6),
   condition('Breakout','Close above prior box high',close[-1]-top,close[-1]>top),
   condition('Volume','Volume at least 1.2× prior average',None,True)]
  stop=bottom
 elif family=='pull':
  dd=(1-close[-2]/max(high[-11:-2]))*100
  rules=[condition('Trend','EMA9 above EMA21 and EMA21 rising over five bars',e9-e21,e9>e21 and e21>_ema(close[:-5],21)),
   condition('Pullback','Prior close 1–7% below earlier high',dd,1<=dd<=7),
   condition('Trigger','Close above prior high',close[-1]-high[-2],close[-1]>high[-2]),
   condition('Volume','Volume at least 1.1× prior average',None,True)]
  stop=min(low[-4:])
 else:raise ValueError('unsupported family')
 rules.append(condition('Stop geometry','Positive stop below signal close',stop,0<stop<close[-1]))
 return rules,stop


def evaluate(config,instrument,index,charts,*,reference_sessions=None):
 """Call the actual swing snapshot; missing optional filters remain optional."""
 rows=charts[instrument][:index+1]
 if not rows:return [],None
 day=rows[-1]['timestamp'][:10]
 decision=datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1,seconds=1)
 chart={'interval':'1d','currency':'ZAR','symbol':instrument,'bars':rows}
 bench=[r for r in charts.get('ETF_STX40',[]) if r['timestamp'][:10]<=day]
 bchart={'interval':'1d','currency':'ZAR','symbol':'ETF_STX40','bars':bench} if bench else None
 result=snapshot(chart,evaluated_at=decision,benchmark_chart=bchart)
 if result.get('state')=='UNAVAILABLE':return [_rule('Snapshot',None,None,'Swing snapshot unavailable')],None
 c=result['conditions'];v=result['values']; close=result['last_close']
 if config.family!='swing':
  # Reuse the existing family rules and stop exactly; missing required inputs
  # remain unknown rather than filling the family evaluator with fake volume.
  from application.backtest_lab.zebra_field_windows import evaluate_mixed
  try:
   if config.volume_mode=='off' and any(r.get('volume') is None for r in rows):
    original,family_stop=_family_without_volume(config.family,rows)
   else:original,family_stop=evaluate_mixed(config.family,instrument,index,charts,reference_sessions=reference_sessions)
  except (TypeError,ValueError,KeyError,ZeroDivisionError):original=[];family_stop=None
  if not original:return [_rule('Family inputs',None,None,'Complete family history unavailable')],None
  rules=[]
  for rule in original:
   name=rule['c']
   if name=='Stop geometry':continue
   value=rule['v'];state=rule['ok']
   disabled_entry=(config.entry=='trend_only' and name in ('Contraction','Tight box','Pullback','Breakout','Trigger')) or (config.entry=='trigger_only' and name in ('Contraction','Tight box','Pullback'))
   if disabled_entry:state=True
   if name=='Trend' and not config.trend:state=True
   if name in ('Volume','Volume surge'):
    state=True if config.volume_mode=='off' else None if value is None else value>=config.volume_min
   rules.append(_rule(name,value,state,rule['t'] + (' (entry condition disabled)' if disabled_entry else '')))
  if config.momentum:
   rsi=v['rsi14_wilder'];rules.append(_rule('Momentum',rsi,None if rsi is None else config.rsi_min<=rsi<=config.rsi_max,'Wilder RSI range'))
  if config.benchmark_mode=='outperform':rules.append(_rule('Benchmark',v['relative_return20'],c['outperforming_benchmark20'],'Benchmark outperformance'))
  if config.stop_mode=='family':stop=family_stop
  elif config.stop_mode=='snapshot':stop=result['geometry'].get('stop')
  elif config.stop_mode=='structure':stop=v['prior_low10']
  elif config.stop_mode=='atr':stop=None if v['atr14_wilder'] is None else close-config.atr_multiple*v['atr14_wilder']
  else:stop=close*(1-config.stop_pct)
  rules.append(_rule('Stop geometry',stop,None if stop is None else 0<stop<close,config.stop_mode))
  return rules,stop
 if config.entry=='breakout':entry=c['breakout20']
 elif config.entry=='reclaim':entry=c['ema20_reclaim']
 elif config.entry=='trend_only':entry=c['ema_uptrend']
 else:
  a,b=c['breakout20'],c['ema20_reclaim'];entry=True if a is True or b is True else False if a is False and b is False else None
 rules=[_rule('Trend',v['ema20'],c['ema_uptrend'] if config.trend else True,'EMA uptrend' if config.trend else 'Trend filter disabled'),
        _rule('Entry',None,entry,config.entry),
        _rule('Momentum',v['rsi14_wilder'],(None if v['rsi14_wilder'] is None else config.rsi_min<=v['rsi14_wilder']<=config.rsi_max) if config.momentum else True,'RSI range' if config.momentum else 'Momentum filter disabled'),
        _rule('Volume',v['relative_volume20'],(None if v['relative_volume20'] is None else v['relative_volume20']>config.volume_min) if config.volume_mode=='threshold' else True,'Relative-volume filter' if config.volume_mode=='threshold' else 'Volume filter disabled'),
        _rule('Benchmark',v['relative_return20'],c['outperforming_benchmark20'] if config.benchmark_mode=='outperform' else True,'Benchmark outperformance' if config.benchmark_mode=='outperform' else 'Benchmark filter disabled')]
 if config.stop_mode in ('snapshot','family'):stop=result['geometry'].get('stop')
 elif config.stop_mode=='structure':stop=v['prior_low10']
 elif config.stop_mode=='atr':stop=None if v['atr14_wilder'] is None else close-config.atr_multiple*v['atr14_wilder']
 else:stop=close*(1-config.stop_pct)
 rules.append(_rule('Stop geometry',stop,None if stop is None else 0<stop<close,config.stop_mode))
 return rules,stop


def signal_for(config,instrument,session,decision_at,stop):
 return Signal(instrument+'-'+session,instrument,session,decision_at,Decimal(str(stop)),
  Decimal(str(config.max_notional)),Decimal(str(config.risk_budget)),horizon=config.horizon,
  target_r=None if config.target_r is None else Decimal(str(config.target_r)),trail=config.trail,
  trail_k=Decimal(str(config.trail_k)),trail_activation_r=Decimal(str(config.trail_activation_r)),
  exit_mode=config.exit_mode,strategy_profile_id=config.profile_id,strategy_profile_version=config.profile_version)
