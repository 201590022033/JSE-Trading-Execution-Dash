"""Map locally registered and retained JSE instruments to ShareData codes."""
from pathlib import Path
import json
import re
from .radar_price_capture import research_catalog, latest_close_history


def mappings(capture_dir):
    result = {}
    for key, item in research_catalog().items():
        symbol = item.get('yahoo_symbol', '')
        if re.fullmatch(r'[A-Z][A-Z0-9]{1,7}\.JO', symbol):
            result[key] = symbol[:-3]
    # Retained discovered issuer captures were previously identity-checked by
    # the Yahoo adapter; re-run that check before treating their codes as JSE.
    for path in Path(capture_dir).glob('*.json'):
        key = path.name.split('-', 1)[0]
        if key in result or not re.fullmatch(r'[A-Z]{2,8}', key): continue
        try:
            history = latest_close_history(capture_dir, key)
            if history.get('identity_basis') in {'SENS_CODE_YAHOO_METADATA','SCREEN_YAHOO_METADATA'}: result[key] = key
        except (OSError, ValueError, KeyError, TypeError):
            continue
    # Research-intake histories carry a raw-hash-bound exact JSE symbol and
    # can identify a share even when it was never in the public radar catalog.
    try:
        root = Path(capture_dir).resolve().parents[2].parent
        intake = root/'jse-strategy-research/data/p1-prospective-events-2026-10-28/intake'
        from application.backtest_lab.observed_history import research_intake_history
        for path in (intake/'normalized').glob('*.json'):
            if path.stat().st_size > 4_000_000: continue
            item=json.loads(path.read_text(encoding='utf-8'))
            key=item.get('instrument_id','')
            if key not in result and re.fullmatch(r'[A-Z]{2,8}',key) and research_intake_history(key,intake):
                result[key]=key
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    return dict(sorted(result.items()))
