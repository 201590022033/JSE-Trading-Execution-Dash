"""
JSE Data Adapter Module
Fetches real JSE prices and South African news sources
Feeds data into the unified pipeline

Supports:
- Real-time price data (Yahoo Finance, Finnhub, or mock)
- South African news sources (NewsAPI, Reddit)
- JSE ticker mapping and metadata
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple, Type
import requests
from enum import Enum
from abc import ABC, abstractmethod

from data_pipeline import (
    MarketData,
    NewsItem,
    SentimentLabel,
    UnifiedDataPipeline
)


class DataSourceType(Enum):
    """Supported data sources"""
    YAHOO_FINANCE = "yahoo"
    FINNHUB = "finnhub"
    MOCK = "mock"


# =========================
# JSE Ticker Mapping
# =========================

JSE_TICKERS = {
    "NPN": {
        "name": "Naspers",
        "sector": "Technology",
        "description": "Media and e-commerce company",
        "yahoo_symbol": "NPN.JO"
    },
    "SASOL": {
        "name": "Sasol",
        "sector": "Energy",
        "description": "Chemical and energy company",
        "yahoo_symbol": "SOL.JO"
    },
    "BHP": {
        "name": "BHP Group",
        "sector": "Mining",
        "description": "Global mining company",
        "yahoo_symbol": "BHG.JO"
    },
    "IMPJ": {
        "name": "Impala Platinum",
        "sector": "Mining",
        "description": "Platinum miner",
        "yahoo_symbol": "IMP.JO"
    },
    "SHPJ": {
        "name": "Shoprite",
        "sector": "Retail",
        "description": "Retail and grocery",
        "yahoo_symbol": "SHP.JO"
    },
    "TFMJ": {
        "name": "Foschini Group",
        "sector": "Retail",
        "description": "Fashion retail",
        "yahoo_symbol": "TFG.JO"
    },
    "ABSPJ": {
        "name": "Absa Group",
        "sector": "Financial Services",
        "description": "Banking and financial services",
        "yahoo_symbol": "ABG.JO"
    },
    "JDIJ": {
        "name": "JD Group (inactive legacy identity)",
        "sector": "Retail",
        "description": "Retained only for durable paper-account configuration compatibility",
        "yahoo_symbol": "JDI.JO",
        "research_enabled": False,
        "status": "INVALID_PROVIDER_MAPPING"
    },
    "CLS": {
        "name": "Clicks Group",
        "sector": "Retail",
        "description": "Health, beauty and pharmacy retail",
        "yahoo_symbol": "CLS.JO"
    },
    "AGL": {"name": "Anglo American", "sector": "Mining", "description": "Diversified mining", "yahoo_symbol": "AGL.JO"},
    "BTI": {"name": "British American Tobacco", "sector": "Consumer", "description": "Tobacco and consumer products", "yahoo_symbol": "BTI.JO"},
    "CFR": {"name": "Richemont", "sector": "Luxury Goods", "description": "Luxury goods", "yahoo_symbol": "CFR.JO"},
    "FSR": {"name": "FirstRand", "sector": "Financial Services", "description": "Banking and financial services", "yahoo_symbol": "FSR.JO"},
    "GFI": {"name": "Gold Fields", "sector": "Mining", "description": "Gold mining", "yahoo_symbol": "GFI.JO"},
    "KIO": {"name": "Kumba Iron Ore", "sector": "Mining", "description": "Iron ore mining", "yahoo_symbol": "KIO.JO"},
    "MTN": {"name": "MTN Group", "sector": "Telecommunications", "description": "Telecommunications", "yahoo_symbol": "MTN.JO"},
    "NED": {"name": "Nedbank", "sector": "Financial Services", "description": "Banking and financial services", "yahoo_symbol": "NED.JO"},
    "REM": {"name": "Remgro", "sector": "Investment", "description": "Investment holding company", "yahoo_symbol": "REM.JO"},
    "VOD": {"name": "Vodacom", "sector": "Telecommunications", "description": "Telecommunications", "yahoo_symbol": "VOD.JO"}
}

# South African news sources
SA_NEWS_SOURCES = [
    "business-day",  # NewsAPI source ID
    "financial-times",
    "ft.com",
    "reuters",
    "bloomberg"
]

SA_NEWS_KEYWORDS = [
    "South Africa",
    "JSE",
    "Johannesburg Stock Exchange",
    "ZAR",
    "rand",
    "mining",
    "commodity",
    "platinum",
    "gold",
    "emerging markets",
    "Africa",
    "BRICS",
    "SARB",
    "interest rate",
    "oil price",
    "Brent crude"
]


# =========================
# Price Data Fetchers
# =========================

class PriceFetcher(ABC):
    """Abstract base for price data fetchers"""
    
    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for ticker"""
        pass
    
    @abstractmethod
    def get_historical_prices(self, ticker: str, days: int = 30) -> List[float]:
        """Get historical prices for backfilling"""
        pass


class YahooFinanceFetcher(PriceFetcher):
    """Fetch prices from Yahoo Finance (free, reliable)"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 60  # seconds

    def get_chart(self, ticker: str, period: str = "3mo") -> Dict:
        """Timestamped public bars for display; never substitutes mock prices.

        Keep legacy scalar methods unchanged. Yahoo equities may be quoted in
        South African cents; normalize only when currency metadata confirms it.
        Daily timestamps identify sessions, not the time of the latest trade.
        """
        import math
        if period not in {"1d", "1mo", "3mo", "1y", "5y"}:
            raise ValueError("Unsupported chart period")
        symbol = JSE_TICKERS.get(ticker, {}).get("yahoo_symbol", ticker)
        stock = yf.Ticker(symbol)
        # The one-day operational chart is the swing-review view. Keep its
        # public bars at the declared 30-minute decision window; the canonical
        # ranking/paper path remains daily until a verified JSE 30-minute source
        # is admitted separately.
        interval = "30m" if period == "1d" else "1d"
        frame = stock.history(period=period, interval=interval, auto_adjust=False,
                              actions=False, timeout=10)
        if frame.empty:
            raise ValueError("Yahoo returned no bars")
        metadata = stock.get_history_metadata() or {}
        raw_currency = metadata.get("currency") or "UNKNOWN"
        is_index = symbol.startswith("^")
        scale = 0.01 if raw_currency == "ZAc" and not is_index else 1.0
        unit = "points" if is_index else ("ZAR" if raw_currency == "ZAc" else raw_currency)
        bars = []
        for stamp, row in frame.iterrows():
            close = float(row["Close"]) * scale
            if not math.isfinite(close) or close <= 0:
                continue
            bar = {"timestamp": stamp.isoformat(), "close": close,
                   "volume": float(row["Volume"]) if math.isfinite(float(row["Volume"])) else None}
            for source, target in (("Open", "open"), ("High", "high"), ("Low", "low")):
                value = float(row[source]) if source in row else None
                if value is not None and math.isfinite(value) and value > 0:
                    bar[target] = value * scale
            bars.append(bar)
        if not bars:
            raise ValueError("Yahoo returned no valid closing prices")
        return {"symbol": symbol, "currency": unit, "provider_currency": raw_currency,
                "provider_symbol": metadata.get('symbol'), "instrument_type": metadata.get('instrumentType'),
                "exchange": metadata.get('exchangeName'),
                "interval": interval, "period": period, "bars": bars,
                "price": bars[-1]["close"], "source_timestamp": bars[-1]["timestamp"],
                "timestamp_kind": "bar_start" if interval == "5m" else "session_date",
                "change_pct": (bars[-1]["close"] / bars[0]["close"] - 1) * 100,
                "change_basis": "selected chart period"}
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price from Yahoo Finance"""
        try:
            # Map JSE ticker to Yahoo symbol
            if ticker in JSE_TICKERS:
                yahoo_symbol = JSE_TICKERS[ticker]["yahoo_symbol"]
            else:
                yahoo_symbol = ticker
            
            # Check cache
            if ticker in self.cache:
                elapsed = (datetime.now() - self.cache_time[ticker]).total_seconds()
                if elapsed < self.cache_ttl:
                    return self.cache[ticker]
            
            # Fetch from Yahoo
            data = yf.download(yahoo_symbol, period="1d", progress=False)
            if data.empty:
                return None
            
            # yfinance>=1.0 returns multi-level columns; squeeze to scalar
            close = data['Close']
            if hasattr(close, 'columns'):
                close = close.iloc[:, 0]
            price = float(close.iloc[-1])

            # Cache it
            self.cache[ticker] = price
            self.cache_time[ticker] = datetime.now()

            return price

        except Exception as e:
            print(f"Error fetching price for {ticker}: {e}")
            return None
    
    def get_historical_prices(self, ticker: str, days: int = 30) -> List[float]:
        """Get historical prices for backtesting"""
        try:
            if ticker in JSE_TICKERS:
                yahoo_symbol = JSE_TICKERS[ticker]["yahoo_symbol"]
            else:
                yahoo_symbol = ticker
            
            period = f"{days}d"
            data = yf.download(yahoo_symbol, period=period, progress=False)
            
            if data.empty:
                return []
            
            close = data['Close']
            if hasattr(close, 'columns'):
                close = close.iloc[:, 0]
            return [float(p) for p in close.tolist()]

        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")
            return []


class FinnhubFetcher(PriceFetcher):
    """Fetch prices from Finnhub API (requires free API key)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 60
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price from Finnhub"""
        try:
            # Check cache
            if ticker in self.cache:
                elapsed = (datetime.now() - self.cache_time[ticker]).total_seconds()
                if elapsed < self.cache_ttl:
                    return self.cache[ticker]
            
            # Map JSE to Finnhub format if needed
            symbol = ticker if "." in ticker else f"{ticker}.XJSE"
            
            url = f"{self.base_url}/quote"
            params = {
                "symbol": symbol,
                "token": self.api_key
            }
            
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if 'c' in data:
                price = float(data['c'])
                self.cache[ticker] = price
                self.cache_time[ticker] = datetime.now()
                return price
            
            return None
        
        except Exception as e:
            print(f"Error fetching price from Finnhub for {ticker}: {e}")
            return None
    
    def get_historical_prices(self, ticker: str, days: int = 30) -> List[float]:
        """Get historical prices from Finnhub"""
        # This would require more complex Finnhub API calls
        # For now, fall back to empty list
        return []


class MockPriceFetcher(PriceFetcher):
    """Generate mock prices for testing (deterministic)"""
    
    def __init__(self, base_prices: Dict[str, float] = None):
        self.base_prices = base_prices or {}
        self.history = {}
        
        # Initialize with JSE tickers
        for ticker in JSE_TICKERS.keys():
            if ticker not in self.base_prices:
                self.base_prices[ticker] = 100.0
            self.history[ticker] = [self.base_prices[ticker]]
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Return current mock price"""
        if ticker not in self.history:
            self.history[ticker] = [100.0]
        
        # Simple random walk
        import random
        current = self.history[ticker][-1]
        change = random.gauss(0, 0.02)
        new_price = current * (1 + change)
        self.history[ticker].append(new_price)
        
        return new_price
    
    def get_historical_prices(self, ticker: str, days: int = 30) -> List[float]:
        """Return mock historical prices"""
        if ticker not in self.history:
            self.history[ticker] = [self.base_prices.get(ticker, 100.0)]
        
        return self.history[ticker][-days:]


# =========================
# News Fetchers
# =========================

class NewsFetcher(ABC):
    """Abstract base for news data fetchers"""
    
    @abstractmethod
    def fetch_news(self, ticker: str, limit: int = 5) -> List[NewsItem]:
        """Fetch recent news for ticker"""
        pass


class NewsAPIFetcher(NewsFetcher):
    """Fetch news from NewsAPI.org (free tier available)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 300  # 5 minutes
    
    def fetch_news(self, ticker: str, limit: int = 5) -> List[NewsItem]:
        """Fetch news from NewsAPI"""
        try:
            company_name = JSE_TICKERS.get(ticker, {}).get("name", ticker)
            
            # Check cache
            cache_key = f"{ticker}:{limit}"
            if cache_key in self.cache:
                elapsed = (datetime.now() - self.cache_time[cache_key]).total_seconds()
                if elapsed < self.cache_ttl:
                    return self.cache[cache_key]
            
            # Search for company news + SA news
            query = f'({company_name} OR "{ticker}") AND (South Africa OR JSE OR "Johannesburg Stock")'
            
            url = f"{self.base_url}/everything"
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit * 2,  # Fetch more to filter
                "apiKey": self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            articles = response.json().get("articles", [])
            
            news_items = []
            for article in articles[:limit]:
                # Simple sentiment (could use ML model)
                sentiment = self._classify_sentiment(article.get("description", ""))
                
                news_items.append(NewsItem(
                    ticker=ticker,
                    headline=article.get("title", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    timestamp=datetime.fromisoformat(
                        article.get("publishedAt", "").replace("Z", "+00:00")
                    ),
                    sentiment_label=sentiment[0],
                    sentiment_score=sentiment[1],
                    text=article.get("description", "")
                ))
            
            # Cache
            self.cache[cache_key] = news_items
            self.cache_time[cache_key] = datetime.now()
            
            return news_items
        
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return []
    
    @staticmethod
    def _classify_sentiment(text: str) -> Tuple[SentimentLabel, float]:
        """Simple sentiment classification (keyword-based)"""
        if not text:
            return SentimentLabel.NEUTRAL, 0.0
        
        text_lower = text.lower()
        
        bullish_words = [
            "rise", "surge", "jump", "gain", "profit", "beat", "strong",
            "boost", "invest", "growth", "up", "positive", "upgrade",
            "growth", "opportunity", "bullish", "outperform"
        ]
        
        bearish_words = [
            "fall", "drop", "decline", "loss", "miss", "weak", "down",
            "downgrade", "risk", "concern", "bearish", "underperform",
            "struggle", "challenge", "downside"
        ]
        
        bullish_count = sum(1 for word in bullish_words if word in text_lower)
        bearish_count = sum(1 for word in bearish_words if word in text_lower)
        
        if bullish_count > bearish_count:
            return SentimentLabel.BULLISH, min(0.95, 0.1 + bullish_count * 0.15)
        elif bearish_count > bullish_count:
            return SentimentLabel.BEARISH, min(-0.95, -0.1 - bearish_count * 0.15)
        else:
            return SentimentLabel.NEUTRAL, 0.0


class MockNewsFetcher(NewsFetcher):
    """Generate mock news for testing"""
    
    def __init__(self):
        self.headlines = {
            "NPN": [
                "Naspers reports strong earnings",
                "Naspers invests in AI startups",
                "Naspers faces regulatory challenges"
            ],
            "SASOL": [
                "Sasol plans capital reduction",
                "Sasol crude prices surge",
                "Sasol reports losses"
            ]
        }
    
    def fetch_news(self, ticker: str, limit: int = 5) -> List[NewsItem]:
        """Return mock news items"""
        import random
        
        headlines = self.headlines.get(ticker, ["Market update"])
        news_items = []
        
        for i, headline in enumerate(headlines[:limit]):
            # Mock sentiment based on keywords
            if any(w in headline.lower() for w in ["strong", "surge", "invest", "growth"]):
                sentiment = SentimentLabel.BULLISH
                score = 0.7
            elif any(w in headline.lower() for w in ["loss", "fall", "decline", "challenge"]):
                sentiment = SentimentLabel.BEARISH
                score = -0.7
            else:
                sentiment = SentimentLabel.NEUTRAL
                score = 0.0
            
            news_items.append(NewsItem(
                ticker=ticker,
                headline=headline,
                source="Mock News",
                timestamp=datetime.now() - timedelta(hours=i),
                sentiment_label=sentiment,
                sentiment_score=score,
                text=headline
            ))
        
        return news_items


# =========================
# Main JSE Adapter
# =========================

class SENSFeedFetcher:
    """
    Pull public SENS announcements.

    The official JSE SENS site (sens.jse.co.za) blocks non-browser clients with
    403s, so we read the public Moneyweb SENS listing instead — it republishes
    every JSE SENS announcement at moneyweb.co.za/tools-and-data/moneyweb-sens/
    in a stable <strong>COMPANY</strong> – Title format.
    """

    MAX_RESPONSE_BYTES = 2 * 1024 * 1024
    MAX_ITEMS = 100

    MONEYWEB_SENS_URL = "https://www.moneyweb.co.za/tools-and-data/moneyweb-sens/"

    _BROWSER_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    }

    # Entry pattern: <strong>COMPANY NAME</strong> – Announcement title
    _ENTRY_RE = re.compile(
        r"<strong>([^<]{3,120})</strong>&nbsp;&#8211;&nbsp;([^<]{5,250})",
        re.I,
    )

    def __init__(self, base_url: str = "https://www.moneyweb.co.za/tools-and-data/moneyweb-sens/"):
        self.base_url = base_url
        self.last_status = "NOT_REQUESTED"
        self.session = requests.Session()
        self.session.headers.update(self._BROWSER_HEADERS)

    def fetch_recent(self, limit: int = 10, session: Optional[requests.Session] = None) -> List[NewsItem]:
        """Fetch recent SENS announcements from the public Moneyweb listing."""
        target_session = session or self.session
        if target_session is self.session:
            target_session.headers.update(self._BROWSER_HEADERS)
        else:
            merged = dict(self._BROWSER_HEADERS)
            merged.update(target_session.headers)
            target_session.headers.update(merged)

        try:
            # Bound decompressed bytes before parsing, even without Content-Length.
            with target_session.get(self.base_url, timeout=15, stream=True) as response:
                if response.status_code >= 400:
                    self.last_status = f"HTTP_{response.status_code}"
                    return []
                body = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if len(body) + len(chunk) > self.MAX_RESPONSE_BYTES:
                        self.last_status = "RESPONSE_TOO_LARGE"
                        return []
                    body.extend(chunk)
                text = body.decode(response.encoding or "utf-8", errors="replace")
            items = self._parse_moneyweb_sens(text, limit)
            self.last_status = "AVAILABLE" if items else "EMPTY_OR_UNAVAILABLE"
            return items
        except Exception:
            self.last_status = "UNAVAILABLE"
            return []

    @classmethod
    def _parse_moneyweb_sens(cls, text: str, limit: int) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            limit = max(0, min(cls.MAX_ITEMS, limit))
            if not limit:
                return []
            for match in cls._ENTRY_RE.finditer(text):
                company, title = match.groups()
                company = company.strip()
                title = title.strip()
                if not company or not title:
                    continue
                items.append(NewsItem(
                    ticker="JSE",
                    headline=f"{company}: {title}",
                    source="JSE SENS (via Moneyweb)",
                    timestamp=datetime.now(timezone.utc),
                    sentiment_label=SentimentLabel.NEUTRAL,
                    sentiment_score=0.0,
                    text=f"SENS announcement from {company}: {title}",
                    url=cls.MONEYWEB_SENS_URL,
                    timestamp_kind="observed; publication time unavailable",
                ))
                if len(items) >= limit:
                    break
            return items
        except Exception:
            return []

    @staticmethod
    def _parse_rss_text(text: str, limit: int) -> List[NewsItem]:
        try:
            root = ET.fromstring(text)
            items = []
            for node in root.findall(".//item")[:limit]:
                title = node.findtext("title", default="")
                link = node.findtext("link", default="")
                desc = node.findtext("description", default="")
                date_text = node.findtext("pubDate", default="")
                try:
                    timestamp = datetime.strptime(date_text, "%a, %d %b %Y %H:%M:%S %Z")
                except Exception:
                    timestamp = datetime.now()
                items.append(NewsItem(
                    ticker="JSE",
                    headline=title,
                    source="JSE SENS",
                    timestamp=timestamp,
                    sentiment_label=SentimentLabel.NEUTRAL,
                    sentiment_score=0.0,
                    text=f"{desc} | {link}"
                ))
            return items
        except Exception:
            return []

    @staticmethod
    def _parse_html_announcements(text: str, limit: int) -> List[NewsItem]:
        try:
            rows = re.findall(r"<a[^>]*href=[\"'][^\"']+[\"'][^>]*>(.*?)</a>", text, flags=re.I | re.S)
            titles = []
            for row in rows:
                clean = re.sub(r"<[^>]+>", " ", row)
                clean = re.sub(r"\s+", " ", clean).strip()
                if len(clean) > 6 and clean not in titles:
                    titles.append(clean)
            item_list = []
            for title in titles[:limit]:
                item_list.append(NewsItem(
                    ticker="JSE",
                    headline=title,
                    source="JSE SENS",
                    timestamp=datetime.now(),
                    sentiment_label=SentimentLabel.NEUTRAL,
                    sentiment_score=0.0,
                    text=title
                ))
            return item_list
        except Exception:
            return []


class RedditFetcher:
    """
    Fetch South African market chatter from Reddit.

    Uses the approved OAuth API through praw when REDDIT_CLIENT_ID /
      REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT env vars are set.

    Unauthenticated public-JSON polling is deliberately disabled: current
    Reddit Data API terms require approved access information.

    Subreddits watched: r/southafrica, r/JSE, r/PersonalFinanceZA,
    r/za_finance, r/investing (SA-filtered).
    """

    DEFAULT_SUBREDDITS = ["southafrica", "JSE", "PersonalFinanceZA", "za_finance"]

    _KEYWORDS = [
        "jse", "rand", "zar", "south africa", "sarb", "eskom", "load shedding",
        "naspers", "sasol", "standard bank", "capitec", "mining", "platinum",
        "gold", "interest rate", "inflation", "emerging market",
    ]

    _HEADERS = {"User-Agent": "jse-trading-intel/1.0 (personal research tool)"}

    def __init__(
        self,
        subreddits: Optional[List[str]] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        import os
        self.subreddits = subreddits or self.DEFAULT_SUBREDDITS
        self._praw = None

        cid = client_id or os.environ.get("REDDIT_CLIENT_ID")
        secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET")
        ua = user_agent or os.environ.get("REDDIT_USER_AGENT", "jse-trading-intel/1.0")
        if cid and secret:
            try:
                import praw
                self._praw = praw.Reddit(
                    client_id=cid, client_secret=secret, user_agent=ua,
                )
            except Exception as exc:
                print(f"[REDDIT] praw init failed, falling back to public JSON: {exc}")

    def _classify(self, text: str) -> Tuple[SentimentLabel, float]:
        low = text.lower()
        bull = sum(1 for w in ("rise", "surge", "gain", "growth", "profit", "strong", "record", "rally") if w in low)
        bear = sum(1 for w in ("fall", "drop", "loss", "weak", "risk", "crisis", "crash", "downgrade") if w in low)
        if bull > bear:
            return SentimentLabel.BULLISH, min(0.95, 0.15 + bull * 0.12)
        if bear > bull:
            return SentimentLabel.BEARISH, max(-0.95, -0.15 - bear * 0.12)
        return SentimentLabel.NEUTRAL, 0.0

    def _relevant(self, title: str) -> bool:
        low = title.lower()
        return any(k in low for k in self._KEYWORDS)

    def fetch_recent(self, limit: int = 10) -> List[NewsItem]:
        items: List[NewsItem] = []
        if self._praw is None:
            return items
        for sub in self.subreddits:
            if len(items) >= limit:
                break
            try:
                if self._praw is not None:
                    for post in self._praw.subreddit(sub).hot(limit=15):
                        if not self._relevant(post.title):
                            continue
                        label, score = self._classify(post.title)
                        items.append(NewsItem(
                            ticker="JSE",
                            headline=post.title,
                            source=f"Reddit r/{sub}",
                            timestamp=datetime.fromtimestamp(post.created_utc),
                            sentiment_label=label,
                            sentiment_score=score,
                            text=(post.selftext or "")[:300],
                        ))
            except Exception as exc:
                print(f"[REDDIT] r/{sub} fetch failed: {exc}")
                continue
        return items[:limit]


class MoneywebRSSFetcher:
    """Fetch public Moneyweb news items and classify them as a sentiment input."""

    def __init__(self, rss_url: str = "https://www.moneyweb.co.za/feed/"):
        self.rss_url = rss_url

    def fetch_recent(self, limit: int = 10) -> List[NewsItem]:
        try:
            response = requests.get(self.rss_url, timeout=15)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            items = []
            for node in root.findall(".//item")[:limit]:
                title = node.findtext("title", default="")
                link = node.findtext("link", default="")
                desc = node.findtext("description", default="")
                date_text = node.findtext("pubDate", default="")
                try:
                    timestamp = datetime.strptime(date_text, "%a, %d %b %Y %H:%M:%S %z")
                    timestamp_kind = "published"
                except Exception:
                    timestamp = datetime.now(timezone.utc)
                    timestamp_kind = "observed; publication time unavailable"
                sentiment_score = 0.0
                label = SentimentLabel.NEUTRAL
                content = f"{title} {desc}".lower()
                bullish_words = ["growth", "earnings", "upgrade", "strong", "bullish", "profit", "increase"]
                bearish_words = ["drop", "loss", "risky", "decline", "downgrade", "weak", "down", "concern"]
                bullish_hits = sum(1 for w in bullish_words if w in content)
                bearish_hits = sum(1 for w in bearish_words if w in content)
                if bullish_hits > bearish_hits:
                    label = SentimentLabel.BULLISH
                    sentiment_score = min(0.95, 0.2 + bullish_hits * 0.12)
                elif bearish_hits > bullish_hits:
                    label = SentimentLabel.BEARISH
                    sentiment_score = max(-0.95, -0.2 - bearish_hits * 0.12)
                items.append(NewsItem(
                    ticker="JSE",
                    headline=title,
                    source="Moneyweb",
                    timestamp=timestamp,
                    sentiment_label=label,
                    sentiment_score=sentiment_score,
                    text=f"{desc} | {link}",
                    url=link, timestamp_kind=timestamp_kind
                ))
            return items
        except Exception:
            return []


class BaseBankAdapter(ABC):
    """Shared contract for South African bank adapters.

    This keeps the platform public-safe and modular: end users can provide their own
    credentials and provider configuration, while the platform remains agnostic to
    the underlying bank implementation.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def login(self, **kwargs) -> bool:
        pass

    @abstractmethod
    def get_portfolio_summary(self) -> Dict:
        pass

    @abstractmethod
    def get_live_prices(self, ticker: str) -> Optional[float]:
        pass


class StandardBankOSTAdapter(BaseBankAdapter):
    """
    Best-effort adapter for Standard Bank OST web login.

    Standard Bank OST is a browser-based portal and not a publicly documented SDK or
    trading API. This wrapper is therefore designed as a secure session manager that
    can accept a username and password, login to the portal, and store a session for
    authenticated calls. The exact endpoint names and required form fields must be
    confirmed against the bank's official developer portal or internal documentation.
    """

    provider_name = "standardbank_ost"

    def __init__(self, username: str = "", password: str = "", base_url: str = "https://securities.standardbank.co.za/ost"):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.logged_in = False

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

        if not self.username or not self.password:
            raise ValueError("Standard Bank OST username and password are required.")

        # Real contract discovered from the live portal (2026-09-02):
        #   GET  /ost/NSWebController?event=VIEW_LOGIN_EVENT  -> login page
        #   POST /ost/j_security_check  (j_username, j_password, realm=@ostusers.com)
        login_page = self.base_url + "/NSWebController?event=VIEW_LOGIN_EVENT"
        security_check = self.base_url + "/j_security_check"

        try:
            # 1) Establish session cookies from the login page
            self.session.get(login_page, timeout=20)

            # 2) Submit credentials. The portal JS appends the @ostusers.com realm
            #    to the username before posting, so we mirror that here.
            realm_user = self.username
            if "@" not in realm_user:
                realm_user = f"{realm_user}@ostusers.com"

            payload = {
                "j_username": realm_user,
                "j_password": self.password,
                "realm": "@ostusers.com",
            }
            response = self.session.post(
                security_check,
                data=payload,
                timeout=20,
                allow_redirects=True,
            )

            # Heuristics: a failed login typically redirects back to a page
            # containing the login form (j_security_check in URL or loginForm in body).
            body = response.text.lower()
            url = response.url.lower()
            failed_markers = ["j_security_check", "loginform", "login_failed", "invalid"]
            if response.status_code < 400 and not any(m in url or m in body for m in failed_markers):
                self.logged_in = True
                return True

            self.logged_in = False
            return False
        except Exception:
            self.logged_in = False
            return False

    def get_portfolio_summary(self) -> Dict:
        """Placeholder method for authenticated account data retrieval."""
        if not self.logged_in:
            raise RuntimeError("You must login() before fetching OST portfolio/account data.")
        return {"status": "authenticated", "source": "Standard Bank OST", "data": []}

    def get_live_prices(self, ticker: str) -> Optional[float]:
        """Placeholder method for authenticated, live market prices where available."""
        if not self.logged_in:
            raise RuntimeError("You must login() before fetching live OST market data.")
        return None


class BankProviderFactory:
    """Factory for bank adapters. Keeps the platform modular for future South African banks."""

    _registry: Dict[str, Type[BaseBankAdapter]] = {
        "standardbank_ost": StandardBankOSTAdapter,
    }

    @classmethod
    def register(cls, provider_name: str, adapter_class: Type[BaseBankAdapter]) -> None:
        cls._registry[provider_name.lower()] = adapter_class

    @classmethod
    def create(cls, provider_name: str, **kwargs) -> BaseBankAdapter:
        key = provider_name.lower()
        if key not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(f"Unsupported bank provider '{provider_name}'. Available: {available}")
        return cls._registry[key](**kwargs)


class JSEDataAdapter:
    """
    Main adapter that integrates price and news fetching
    
    Usage:
        adapter = JSEDataAdapter(
            price_source=DataSourceType.YAHOO_FINANCE,
            news_source="newsapi",  # "newsapi" or "mock"
            newsapi_key="your-api-key"
        )
        
        price = adapter.get_price("NPN")
        news = adapter.get_news("NPN")
        
        # Or feed directly to pipeline
        adapter.feed_to_pipeline(pipeline, "NPN")
    """
    
    def __init__(
        self,
        price_source: DataSourceType = DataSourceType.YAHOO_FINANCE,
        news_source: str = "mock",  # "newsapi" or "mock"
        newsapi_key: Optional[str] = None,
        finnhub_key: Optional[str] = None,
        sens_base_url: str = "https://www.moneyweb.co.za/tools-and-data/moneyweb-sens/",
        moneyweb_rss_url: str = "https://www.moneyweb.co.za/feed/"
    ):
        # Initialize price fetcher
        if price_source == DataSourceType.YAHOO_FINANCE:
            self.price_fetcher = YahooFinanceFetcher()
        elif price_source == DataSourceType.FINNHUB:
            self.price_fetcher = FinnhubFetcher(finnhub_key or "")
        else:
            self.price_fetcher = MockPriceFetcher()
        
        # Initialize news fetcher
        if news_source == "newsapi" and newsapi_key:
            self.news_fetcher = NewsAPIFetcher(newsapi_key)
        else:
            self.news_fetcher = MockNewsFetcher()

        self.sens_fetcher = SENSFeedFetcher(sens_base_url)
        self.moneyweb_fetcher = MoneywebRSSFetcher(moneyweb_rss_url)
        self.ost_adapter = None
        
        self.last_price = {}
        self.last_update = {}
    
    def get_price(self, ticker: str) -> Optional[float]:
        """Get current price for JSE ticker"""
        price = self.price_fetcher.get_current_price(ticker)
        if price:
            self.last_price[ticker] = price
            self.last_update[ticker] = datetime.now()
        return price
    
    def get_historical_prices(self, ticker: str, days: int = 30) -> List[float]:
        """Get historical prices for backtesting"""
        return self.price_fetcher.get_historical_prices(ticker, days)
    
    def get_news(self, ticker: str, limit: int = 5) -> List[NewsItem]:
        """Get recent news for ticker"""
        return self.news_fetcher.fetch_news(ticker, limit)

    def get_sens_news(self, limit: int = 10) -> List[NewsItem]:
        """Get JSE SENS announcements (best effort, depends on public access or authenticated session)."""
        return self.sens_fetcher.fetch_recent(limit=limit)

    def get_moneyweb_news(self, limit: int = 10) -> List[NewsItem]:
        """Get public Moneyweb news items for AI/social sentiment flags."""
        return self.moneyweb_fetcher.fetch_recent(limit)

    def login_standard_bank_ost(self, username: str, password: str) -> StandardBankOSTAdapter:
        """Create and authenticate a Standard Bank OST session if the bank exposes the portal login."""
        self.ost_adapter = StandardBankOSTAdapter(username=username, password=password)
        self.ost_adapter.login()
        return self.ost_adapter
    
    def get_market_data(self, ticker: str) -> Optional[MarketData]:
        """Get complete market data point (price + volume etc.)"""
        price = self.get_price(ticker)
        if not price:
            return None
        
        return MarketData(
            ticker=ticker,
            price=price,
            timestamp=datetime.now(),
            volume=0,  # Would need to fetch from source
            vwap=price  # Would need to calculate from intraday data
        )
    
    def feed_to_pipeline(
        self,
        pipeline: UnifiedDataPipeline,
        ticker: str,
        include_news: bool = True
    ) -> bool:
        """
        Fetch data and feed directly to pipeline
        Returns True if successful
        """
        # Get price
        market_data = self.get_market_data(ticker)
        if not market_data:
            return False
        
        pipeline.add_market_data(market_data)
        
        # Get news
        if include_news:
            news_items = self.get_news(ticker, limit=3)
            for news in news_items:
                pipeline.add_news(ticker, news)
        
        return True
    
    def backfill_historical_data(
        self,
        pipeline: UnifiedDataPipeline,
        ticker: str,
        days: int = 30
    ) -> int:
        """
        Fill pipeline with historical price data
        Useful for warming up technical indicators before live trading
        Returns number of data points added
        """
        prices = self.get_historical_prices(ticker, days)
        
        if not prices:
            return 0
        
        now = datetime.now()
        for i, price in enumerate(prices):
            # Backdate the timestamps
            timestamp = now - timedelta(days=len(prices) - i)
            pipeline.add_market_data(MarketData(
                ticker=ticker,
                price=price,
                timestamp=timestamp,
                vwap=price
            ))
        
        return len(prices)
    
    def get_jse_metadata(self, ticker: str) -> Dict:
        """Get metadata about a JSE ticker"""
        return JSE_TICKERS.get(ticker, {})
    
    def list_available_tickers(self) -> List[str]:
        """Get list of all available JSE tickers"""
        return list(JSE_TICKERS.keys())


# =========================
# Integration Example
# =========================

if __name__ == "__main__":
    """
    Example usage of JSE adapter
    """
    print("JSE Data Adapter Example")
    print("=" * 80)
    
    # Initialize adapter (using mock for demo)
    adapter = JSEDataAdapter(
        price_source=DataSourceType.MOCK,
        news_source="mock"
    )
    
    # Get metadata
    print("\nAvailable JSE Tickers:")
    for ticker in adapter.list_available_tickers()[:3]:
        meta = adapter.get_jse_metadata(ticker)
        print(f"  {ticker}: {meta['name']} ({meta['sector']})")
    
    # Get current price
    print("\n\nGetting current prices...")
    for ticker in ["NPN", "SASOL", "BHP"]:
        price = adapter.get_price(ticker)
        print(f"  {ticker}: €{price:.2f}" if price else f"  {ticker}: N/A")
    
    # Get news
    print("\n\nGetting recent news...")
    news = adapter.get_news("NPN", limit=2)
    for item in news:
        print(f"  [{item.sentiment_label.value}] {item.headline}")
        print(f"    Source: {item.source}")
    
    # Backfill pipeline with historical data
    print("\n\nBackfilling pipeline with 30 days of historical data...")
    from data_pipeline import UnifiedDataPipeline
    from merged_simulation import MergedSimulation
    
    pipeline = UnifiedDataPipeline(jse_tickers=["NPN"])
    count = adapter.backfill_historical_data(pipeline, "NPN", days=30)
    print(f"  Loaded {count} historical data points")
    
    # Feed live data to pipeline
    print("\n\nFeeding live data to pipeline...")
    success = adapter.feed_to_pipeline(pipeline, "NPN", include_news=True)
    print(f"  Success: {success}")
    
    # Check pipeline state
    obs = pipeline.get_observation("NPN")
    print(f"\n  Price: €{obs.price:.2f}")
    print(f"  Sentiment: {obs.news_sentiment.value}")
    print(f"  Technical indicators available: {obs.indicators is not None}")
