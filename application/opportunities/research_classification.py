"""Versioned research groupings; unknown instruments remain visible."""
from .radar_price_capture import research_catalog

VERSION = 'research-sector-taxonomy-2026-11-04-v1'
_DETAILS = {
    'BTI': ('Consumer','Tobacco','https://dn.sharenet.co.za/v3/quickshare.php?scode=BTI'),
    'SASOL': ('Energy','Diversified chemicals','https://dn.sharenet.co.za/v3/quickshare.php?scode=SOL'),
    'EXX': ('Energy','Coal and energy resources','https://investor.exxaro.com/integrated-reports2025/downloads.php'),
    'TGA': ('Energy','Thermal coal','https://www.thungela.com/investors/'),
    'CSB': ('Retail','Home improvement retailers','https://www.sharenet.co.za/v3/quickshare.php?scode=CSB'),
    'DTC': ('Technology','Computer services','https://www9.sharenet.co.za/v3/quickshare.php?scode=DTC'),
    'GPL': ('Consumer','Casinos and gambling','https://www2.sharenet.co.za/v3/quickshare.php?scode=GPL'),
    'HET': ('Real Estate','Retail REITs','https://www.sharenet.co.za/v3/quickshare.php?scode=HET'),
    'HYP': ('Real Estate','Retail REITs','https://www.sharenet.co.za/v3/quickshare.php?scode=HYP'),
    'LHC': ('Healthcare','Health care facilities','https://www.sharenet.co.za/v3/quickshare.php?scode=LHC'),
    'MTH': ('Retail','Specialty retailers','https://www.sharenet.co.za/v3/quickshare.php?scode=MTH'),
    'NWL': ('Consumer','Consumer electronics','https://www.sharenet.co.za/v3/quickshare.php?scode=NWL'),
    'PRX': ('Technology','Software and computer services','https://www.jse.co.za/jse/instruments/3812'),
    'RNG': ('Mining','Gold mining','https://www.sharenet.co.za/v3/quickshare.php?scode=RNG'),
    'TEX': ('Real Estate','Office REITs','https://www.sharenet.co.za/v3/quickshare.php?scode=TEX'),
    'TMT': ('Real Estate','Real estate holding and development','https://www.sharenet.co.za/v3/quickshare.php?scode=TMT'),
    'TPC': ('Industrials','Containers and packaging','https://www.sharenet.co.za/v3/quickshare.php?scode=TPC'),
    'VIS': ('Real Estate','Real estate holding and development','https://www.sharenet.co.za/v3/quickshare.php?scode=VIS'),
    'AGOGE': ('Funds','Actively managed ETF','https://senspdf.jse.co.za/documents/SENS_20260223_S517452.pdf'),
}

# JSE industry labels as listed by Sharenet; broad sectors continue to use the
# dashboard's local research grouping rather than claiming an ICB hierarchy.
_INDUSTRIES = {
    'ABSPJ':'Banks', 'AGL':'General mining', 'BHP':'General mining',
    'BVT':'Diversified industrials', 'CFR':'Luxury items', 'CLS':'Drug retailers',
    'FSR':'Banks', 'GFI':'Gold mining', 'IMPJ':'Platinum and precious metals',
    'KIO':'Iron and steel', 'MTN':'Telecommunications services', 'NED':'Banks',
    'NPN':'Consumer digital services', 'REM':'Diversified financial services',
    'SHPJ':'Food retailers and wholesalers', 'TFMJ':'Apparel retailers',
    'VOD':'Telecommunications services',
}
_INDUSTRY_SOURCE = 'https://www.sharenet.co.za/v3/dnfile_full.php'


def classifications(instruments):
    catalog = research_catalog(); result = {}
    for key in sorted(set(instruments)):
        if key in _DETAILS:
            sector, industry, source = _DETAILS[key]
            result[key] = {'sector':sector,'industry':industry,'source':source,'status':'CURATED_RESEARCH_GROUP'}
        elif key in catalog:
            item=catalog[key]
            result[key]={'sector':item.get('sector') or 'Unclassified','industry':_INDUSTRIES.get(key,'Unspecified'),
                         'source':_INDUSTRY_SOURCE if key in _INDUSTRIES else 'local-public-research-catalog',
                         'status':'CURATED_RESEARCH_GROUP' if key in _INDUSTRIES else 'LOCAL_CATALOG_GROUP'}
        else:
            result[key]={'sector':'Unclassified','industry':'Unspecified','source':None,'status':'UNCLASSIFIED'}
    return {'version':VERSION,'basis':'CURRENT_RESEARCH_GROUPS_NOT_HISTORICAL_CLASSIFICATIONS','instruments':result}
