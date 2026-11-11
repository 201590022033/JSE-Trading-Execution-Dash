"""Explicit, bounded public MTN quote capture; never uses browser credentials."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import requests
from bs4 import BeautifulSoup

from .quote_store import QuoteStore

URL = 'https://www.sharedata.co.za/v2/Scripts/Quote.aspx'
SAST = ZoneInfo('Africa/Johannesburg')


class ShareDataRetentionError(Exception):
    """Raw provider evidence could not be retained locally."""


def parse_quote(raw, received_at, response_date):
    if not isinstance(raw, bytes) or len(raw) > 2_000_000:
        raise ValueError('invalid provider response')
    if received_at.tzinfo is None or response_date.tzinfo is None:
        raise ValueError('aware receipt and response dates required')
    soup = BeautifulSoup(raw, 'html.parser')
    def field(identifier):
        item = soup.select_one('#' + identifier)
        if item is None:
            raise ValueError('missing provider field')
        return item.get_text(' ', strip=True)
    if field('LatestIntradayData_LblJSECode') != 'MTN':
        raise ValueError('instrument mismatch')
    date_element = soup.select_one('#IntradayChart_Intraday1DDate')
    if date_element is None:
        raise ValueError('provider session date missing')
    day = datetime.strptime(date_element.get('value', ''), '%a %d %b %Y').date()
    if day != received_at.astimezone(SAST).date() or day != response_date.astimezone(SAST).date():
        raise ValueError('provider session date is not current')
    if field('LatestIntradayData_LblLastTradeDay'):
        raise ValueError('provider reports a previous trade day')
    label = field('LatestIntradayData_LblTradeTime')
    match = re.fullmatch(r'As at\s+(\d{1,2}:\d{2}\s*[ap]m),\s*15 mins delayed\*', label, re.I)
    if not match:
        raise ValueError('unrecognised quote time or delay')
    tm = datetime.strptime(match.group(1).replace(' ', '').lower(), '%I:%M%p').time()
    source = datetime.combine(day, tm, SAST)
    if source > received_at or received_at-source < timedelta(minutes=15):
        raise ValueError('quote time inconsistent with stated delay')
    last = field('LatestIntradayData_lblLastTrade').replace(',', '')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', last):
        raise ValueError('invalid last price')
    return {'instrument':'MTN','provider':'SHAREDATA','kind':'DELAYED','unit':'ZAR',
            'source_time':source.isoformat(),'received_at':received_at.isoformat(),
            'delay_seconds':900,'last':last,
            'source_ref':'ShareData MTN public quote; session date from 1D chart metadata; delay is at least 15 minutes'}


def capture(folder):
    response = requests.get(URL, params={'c':'MTN','x':'JSE'}, timeout=15,
                            headers={'User-Agent':'Mozilla/5.0'}, stream=True)
    try:
        response.raise_for_status()
        raw = response.raw.read(2_000_001, decode_content=True)
        received = datetime.now(timezone.utc)
        server_date = parsedate_to_datetime(response.headers['Date'])
    finally:
        response.close()
    record = parse_quote(raw, received, server_date)
    digest = sha256(raw).hexdigest()
    rawdir = Path(folder)/'sharedata-quote-raw'
    try:
        rawdir.mkdir(parents=True, exist_ok=True)
        target = rawdir/(digest+'.html')
        if not target.exists(): target.write_bytes(raw)
    except OSError as exc:
        raise ShareDataRetentionError('raw provider response could not be retained') from exc
    record['source_ref'] += '; raw sha256 ' + digest
    QuoteStore(Path(folder)/'quotes.sqlite3').put(record, evidence=True)
    return {'state':'CAPTURED','source_time':record['source_time'],
            'received_at':record['received_at'],'raw_sha256':digest,
            'delay':'at least 15 minutes','last':record['last']}
