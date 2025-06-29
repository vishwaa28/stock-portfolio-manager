import requests
import random
import os
from datetime import datetime, timedelta
import time
from functools import lru_cache

# Finnhub API key (get from https://finnhub.io)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "d1d3ap9r01qic6lgtil0d1d3ap9r01qic6lgtilg")

# Simple in-memory cache
_cache = {}
_cache_timeout = int(os.getenv("CACHE_TIMEOUT", "300"))  # 5 minutes default
_enable_caching = os.getenv("ENABLE_CACHING", "True").lower() == "true"

def _get_cached_data(key):
    if not _enable_caching:
        return None
    if key in _cache:
        data, timestamp = _cache[key]
        if time.time() - timestamp < _cache_timeout:
            return data
    return None

def _set_cached_data(key, data):
    if not _enable_caching:
        return
    _cache[key] = (data, time.time())

STOCK_DATA = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer Discretionary"},
    "TSLA": {"name": "Tesla Inc.", "sector": "Automotive"},
}

# Pre-defined sector mappings to avoid API calls
SECTOR_SYMBOLS = {
    "Technology": ["AAPL", "GOOGL", "MSFT", "NVDA", "META"],
    "Consumer Discretionary": ["AMZN", "TSLA", "NFLX", "HD", "MCD"],
    "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA"],
    "Industrial": ["BA", "CAT", "GE", "MMM", "HON"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "SLB"],
    "Consumer Staples": ["PG", "KO", "WMT", "COST", "PEP"],
    "Real Estate": ["SPG", "PLD", "EQIX", "AMT", "CCI"],
    "Materials": ["LIN", "APD", "FCX", "NEM", "DOW"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"]
}

@lru_cache(maxsize=100)
def fetch_price(symbol):
    cache_key = f"price_{symbol}"
    cached = _get_cached_data(cache_key)
    if cached:
        return cached
        
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        price = data.get("c")
        if price:
            result = round(price, 2)
            _set_cached_data(cache_key, result)
            return result
        else:
            print(f"No Finnhub price data for {symbol}")
            result = round(STOCK_DATA.get(symbol, {}).get("base_price", random.uniform(10, 500)), 2)
            _set_cached_data(cache_key, result)
            return result
    except Exception as e:
        print(f"Finnhub price error: {e}")
        result = round(STOCK_DATA.get(symbol, {}).get("base_price", random.uniform(10, 500)), 2)
        _set_cached_data(cache_key, result)
        return result

def analyze_sentiment(text, price_change=None, price_change_percent=None):
    """
    Enhanced sentiment analysis that considers both text content and price changes
    """
    text = text.lower()
    negative_words = ["drop", "falls", "disappoint", "decline", "regulatory", "controversy", "loss", "plunge", "cut", "down", "lower", "weak", "bearish", "crash", "sell", "negative"]
    positive_words = ["surge", "beats", "growth", "rise", "positive", "profit", "record", "strong", "up", "higher", "bullish", "rally", "gain", "buy", "positive"]
    
    # Check text sentiment
    text_sentiment = "neutral"
    for word in negative_words:
        if word in text:
            text_sentiment = "negative"
            break
    for word in positive_words:
        if word in text:
            text_sentiment = "positive"
            break
    
    # If we have price change data, incorporate it into sentiment
    if price_change is not None:
        if price_change > 0:
            if text_sentiment == "neutral":
                text_sentiment = "positive"
            elif text_sentiment == "negative":
                text_sentiment = "neutral"  # Price gain might offset negative news
        elif price_change < 0:
            if text_sentiment == "neutral":
                text_sentiment = "negative"
            elif text_sentiment == "positive":
                text_sentiment = "neutral"  # Price loss might offset positive news
    
    # Consider percentage change for stronger sentiment
    if price_change_percent is not None:
        if abs(price_change_percent) > 5:  # Significant move
            if price_change_percent > 5:
                text_sentiment = "positive"
            elif price_change_percent < -5:
                text_sentiment = "negative"
    
    return text_sentiment

@lru_cache(maxsize=50)
def fetch_news(symbol, limit=5):
    cache_key = f"news_{symbol}_{limit}"
    cached = _get_cached_data(cache_key)
    if cached:
        return cached
        
    if symbol not in STOCK_DATA:
        return []
    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={(datetime.now() - timedelta(days=7)).date()}&to={datetime.now().date()}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        news_items = []
        for item in data[:limit]:
            # Get current price and change for enhanced sentiment analysis
            current_price = fetch_price(symbol)
            previous_close = fetch_previous_close(symbol)
            change = current_price - previous_close if current_price and previous_close else 0
            days_gain_pct = ((current_price - previous_close) / previous_close) * 100 if current_price and previous_close else None
            
            sentiment = analyze_sentiment(
                item.get("headline", "") + " " + item.get("summary", ""),
                price_change=change,
                price_change_percent=days_gain_pct
            )
            news_items.append({
                "title": item.get("headline"),
                "description": item.get("summary"),
                "url": item.get("url"),
                "source": item.get("source"),
                "published": datetime.fromtimestamp(item.get("datetime")).strftime('%Y-%m-%d'),
                "sentiment": sentiment
            })
        _set_cached_data(cache_key, news_items)
        return news_items
    except Exception as e:
        print(f"Finnhub news error: {e}")
        return []

@lru_cache(maxsize=10)
def fetch_general_news(limit=10):
    cache_key = f"general_news_{limit}"
    cached = _get_cached_data(cache_key)
    if cached:
        return cached
        
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        news_items = []
        for item in data[:limit]:
            try:
                published_date = datetime.fromtimestamp(item.get("datetime"))
                news_items.append({
                    "title": item.get("headline"),
                    "description": item.get("summary"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                    "published": published_date.strftime('%Y-%m-%d'),
                    "sector": "general"
                })
            except Exception as e:
                print(f"Error processing news item: {e}")
                continue

        _set_cached_data(cache_key, news_items)
        return news_items

    except Exception as e:
        print(f"Finnhub general news error: {e}")
        # Return mock news if API fails
        mock_news = [
            {
                "title": "Market Update: Stocks Show Mixed Performance",
                "description": "Major indices show mixed performance as investors weigh economic data.",
                "source": "Financial Times",
                "url": "#",
                "published": datetime.now().strftime('%Y-%m-%d'),
                "sector": "general"
            },
            {
                "title": "Tech Sector Leads Market Gains",
                "description": "Technology stocks continue to outperform other sectors.",
                "source": "Reuters",
                "url": "#",
                "published": datetime.now().strftime('%Y-%m-%d'),
                "sector": "general"
            },
            {
                "title": "Federal Reserve Policy Update",
                "description": "Federal Reserve maintains current interest rate policy.",
                "source": "Bloomberg",
                "url": "#",
                "published": datetime.now().strftime('%Y-%m-%d'),
                "sector": "general"
            },
            {
                "title": "Earnings Season Kicks Off",
                "description": "Major companies begin reporting quarterly earnings.",
                "source": "CNBC",
                "url": "#",
                "published": datetime.now().strftime('%Y-%m-%d'),
                "sector": "general"
            },
            {
                "title": "Global Markets React to Economic Data",
                "description": "International markets respond to latest economic indicators.",
                "source": "MarketWatch",
                "url": "#",
                "published": datetime.now().strftime('%Y-%m-%d'),
                "sector": "general"
            }
        ]
        _set_cached_data(cache_key, mock_news)
        return mock_news

def fetch_all_stocks():
    stocks = []
    for symbol, data in STOCK_DATA.items():
        stocks.append({
            "symbol": symbol,
            "name": data["name"],
            "price": fetch_price(symbol),
            "sector": data["sector"]
        })
    return stocks

def search_stocks(query):
    query = query.upper()
    results = []
    for symbol, data in STOCK_DATA.items():
        if query in symbol or query in data["name"].upper():
            results.append({
                "symbol": symbol,
                "name": data["name"],
                "price": fetch_price(symbol),
                "sector": data["sector"]
            })
    return results

def get_market_summary():
    total_stocks = len(STOCK_DATA)
    up_count = random.randint(int(total_stocks * 0.4), int(total_stocks * 0.7))
    down_count = total_stocks - up_count
    return {
        "total_stocks": total_stocks,
        "stocks_up": up_count,
        "stocks_down": down_count,
        "market_sentiment": "positive" if up_count > down_count else "negative"
    }

@lru_cache(maxsize=5)
def fetch_all_symbols(exchange="US"):
    cache_key = f"symbols_{exchange}"
    cached = _get_cached_data(cache_key)
    if cached:
        return cached
        
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange={exchange}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        _set_cached_data(cache_key, data)
        return data  # list of dicts with 'symbol', 'description', etc.
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

@lru_cache(maxsize=100)
def fetch_company_profile(symbol):
    cache_key = f"profile_{symbol}"
    cached = _get_cached_data(cache_key)
    if cached:
        return cached
        
    url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        _set_cached_data(cache_key, data)
        return data
    except Exception as e:
        print(f"Error fetching company profile for {symbol}: {e}")
        return {}

@lru_cache(maxsize=100)
def fetch_stock_logo(symbol):
    """Fetch stock logo URL from Finnhub API"""
    cache_key = f"logo_{symbol}"
    cached = _get_cached_data(cache_key)
    if cached:
        return cached
        
    url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        logo_url = data.get("logo", "")
        _set_cached_data(cache_key, logo_url)
        return logo_url
    except Exception as e:
        print(f"Error fetching logo for {symbol}: {e}")
        return ""

def fetch_previous_close(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        return data.get("pc")  # previous close
    except:
        return None

def fetch_detailed_stocks(limit=10):
    # Use a smaller, predefined list for better performance
    popular_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "NFLX", "JPM", "JNJ"]
    stocks = []
    
    for symbol in popular_symbols[:limit]:
        profile = fetch_company_profile(symbol)
        # Fetch quote data for price, previous close, and volume
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            price = data.get("c")
            previous_close = data.get("pc")
            volume = data.get("v")
            percent = 0
            change = 0
            if price is not None and previous_close:
                change = price - previous_close
                percent = ((price - previous_close) / previous_close) * 100 if previous_close else 0
            sector = profile.get("finnhubIndustry", "Unknown") if profile else "Unknown"
            market_cap = profile.get("marketCapitalization", "N/A") if profile else "N/A"
            logo = fetch_stock_logo(symbol)
            stocks.append({
                "symbol": symbol,
                "name": profile.get("name", "Unknown") if profile else "Unknown",
                "change": change,
                "percent": percent,
                "volume": volume,
                "sector": sector,
                "market_cap": market_cap,
                "price": price,
                "logo": logo
            })
        except Exception as e:
            print(f"Error fetching detailed stock data for {symbol}: {e}")
    # Sort by profit (change) descending
    stocks.sort(key=lambda x: x["change"], reverse=True)
    return stocks

def fetch_sector_news(sector_name, limit=5):
    # Use predefined sector symbols instead of fetching all symbols
    sector_symbols = SECTOR_SYMBOLS.get(sector_name, [])
    
    if not sector_symbols:
        # Fallback: return empty list instead of making expensive API calls
        return []

    # Get news from up to 3 companies in the sector (reduced from 5)
    sector_news = []
    for symbol in sector_symbols[:3]:
        news = fetch_news(symbol, limit=limit)
        sector_news.extend(news)
    return sector_news



