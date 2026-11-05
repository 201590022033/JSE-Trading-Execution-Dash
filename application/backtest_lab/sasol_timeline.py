"""Retrospective source-linked issuer and market research timeline."""
from datetime import date
from application.backtest_lab.proxy_context import prior_return

def supplementary_facts(text):
    """Extract explicit per-share dividend values, retaining ambiguous context."""
    import re
    pattern=re.compile(r'\b((?:interim|final)\s+dividend)\s*\(\s*rand per share\s*\)\s+(\d+(?:[.,]\d{1,2})?)(?![\d,.])',re.I)
    return [{'metric':m.group(1).lower(),'value':float(m.group(2).replace(',','.')),
             'unit':'ZAR_per_share','period_basis':'UNKNOWN','raw':m.group(0),
             'span':[m.start(),m.end()],'basis':'EXPLICIT_PRINTED_VALUE_UNREVIEWED'} for m in pattern.finditer(text)]

def topic_quotes(text):
    """Bounded source quotes identify relevant topics without inventing figures."""
    import re
    topics={'production':r'\bproduction\b','sales':r'\bsales\b','debt':r'\b(?:net )?debt\b','dividend':r'\bdividend\b'}
    out=[]
    for topic,pattern in topics.items():
        m=re.search(pattern,text,re.I)
        if m:out.append({'topic':topic,'quote':text[max(0,m.start()-60):min(len(text),m.end()+140)].strip(),
                         'basis':'SOURCE_MENTION_NOT_EXTRACTED_FINANCIAL_FACT'})
    return out

def price_window(rows,day):
    """Use observed sessions, preserving gaps and each selected row's source."""
    ordered=sorted((r for r in rows if r.get('close') is not None),key=lambda r:r['session'])
    before=[r for r in ordered if r['session']<=day]
    after=[r for r in ordered if r['session']>day]
    last=before[-1] if before else None
    return {'last_on_or_before':last,'next_observed':after[:5],
            'basis':'OBSERVED_PROVIDER_SESSIONS_GAPS_NOT_INFERRED'}

def context_at(day,stock,sector,brent,fx):
    date.fromisoformat(day)
    def as_proxy(rows):
        return [{'session':r['session'],'close':r.get('close'),'current_session_not_completed':False} for r in rows]
    return {'stock':price_window(stock,day),
        'sector_5_observed_session_return':prior_return(as_proxy(sector),day),
        'brent_5_observed_session_return':prior_return(brent,day),
        'usdzar_5_observed_session_return':prior_return(fx,day),
        'basis':'RETROSPECTIVE_REFERENCES_NOT_PROOF_OF_KNOWLEDGE_OR_CAUSE'}

def hypothesis_labels(context):
    """Explicit questions, not a rating or a claim about an event's cause."""
    output=[]
    for label,key in [('Was Brent falling?','brent_5_observed_session_return'),
                      ('Was the sector falling?','sector_5_observed_session_return'),
                      ('Was the rand weakening?','usdzar_5_observed_session_return')]:
        item=context.get(key)
        value=item.get('return') if item else None
        expected=(value>0 if key=='usdzar_5_observed_session_return' else value<0) if value is not None else None
        output.append({'question':label,'state':'UNKNOWN' if value is None else 'YES' if expected else 'NO',
                       'value':value,'reference':item,'basis':'FIVE_PRIOR_OBSERVED_SESSIONS'})
    return output
