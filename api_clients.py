import requests
import random
import os
from datetime import datetime, timedelta

# Finnhub API key (get from https://finnhub.io)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "d1d3ap9r01qic6lgtil0d1d3ap9r01qic6lgtilg")

STOCK_DATA = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer Discretionary"},
    "TSLA": {"name": "Tesla Inc.", "sector": "Automotive"},

}

def fetch_price(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        price = data.get("c")  # current price
        if price:
            return round(price, 2)
        else:
            print(f"No Finnhub price data for {symbol}")
            return round(STOCK_DATA.get(symbol, {}).get("base_price", random.uniform(10, 500)), 2)
    except Exception as e:
        print(f"Finnhub price error: {e}")
        return round(STOCK_DATA.get(symbol, {}).get("base_price", random.uniform(10, 500)), 2)

def analyze_sentiment(text):
    text = text.lower()
    negative_words = ["drop", "falls", "disappoint", "decline", "regulatory", "controversy", "loss", "plunge", "cut"]
    positive_words = ["surge", "beats", "growth", "rise", "positive", "profit", "record", "strong"]
    for word in negative_words:
        if word in text:
            return "negative"
    for word in positive_words:
        if word in text:
            return "positive"
    return "neutral"

def fetch_news(symbol, limit=5):
    if symbol not in STOCK_DATA:
        return []
    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={(datetime.now() - timedelta(days=7)).date()}&to={datetime.now().date()}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        news_items = []
        for item in data[:limit]:
            sentiment = analyze_sentiment(item.get("headline", "") + " " + item.get("summary", ""))
            news_items.append({
                "title": item.get("headline"),
                "description": item.get("summary"),
                "url": item.get("url"),
                "source": item.get("source"),
                "published": datetime.fromtimestamp(item.get("datetime")).strftime('%Y-%m-%d'),
                "sentiment": sentiment
            })
        return news_items
    except Exception as e:
        print(f"Finnhub news error: {e}")
        return []

def fetch_general_news(limit=10):
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        news_items = []
        for item in data[:limit]:
            news_items.append({
                "title": item.get("headline"),
                "description": item.get("summary"),
                "source": item.get("source"),
                "url": item.get("url"),
                "published": datetime.fromtimestamp(item.get("datetime")).strftime('%Y-%m-%d')
            })
        return news_items
    except Exception as e:
        print(f"Finnhub general news error: {e}")
        return []

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

def fetch_all_symbols(exchange="US"):
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange={exchange}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        return data  # list of dicts with 'symbol', 'description', etc.
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

def fetch_company_profile(symbol):
    url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        return response.json()
    except Exception as e:
        print(f"Error fetching company profile for {symbol}: {e}")
        return {}
def fetch_previous_close(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        return data.get("pc")  # previous close
    except:
        return None


def fetch_detailed_stocks(limit=10):
    stocks = []
    symbols = fetch_all_symbols()
    for item in symbols[:limit]:  # Limit for demo/testing
        symbol = item["symbol"]
        profile = fetch_company_profile(symbol)
        # Fetch quote data for price, previous close, and volume
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        try:
            response = requests.get(url)
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
            stocks.append({
                "symbol": symbol,
                "name": profile.get("name", "Unknown") if profile else "Unknown",
                "change": change,
                "percent": percent,
                "volume": volume,
                "sector": sector,
                "market_cap": market_cap,
                "price": price
            })
        except Exception as e:
            print(f"Error fetching detailed stock data for {symbol}: {e}")
    # Sort by profit (change) descending
    stocks.sort(key=lambda x: x["change"], reverse=True)
    return stocks

def fetch_sector_news(sector_name, limit=5):
    all_symbols = fetch_all_symbols()
    sector_symbols = []

    for item in all_symbols:
        symbol = item["symbol"]
        profile = fetch_company_profile(symbol)
        if profile.get("finnhubIndustry", "").lower() == sector_name.lower():
            sector_symbols.append(symbol)

    # Get news from up to 5 companies in the sector
    sector_news = []
    for symbol in sector_symbols[:5]:
        news = fetch_news(symbol, limit=limit)
        sector_news.extend(news)
    return sector_news



