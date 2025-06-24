import requests
import random
import os
from datetime import datetime, timedelta

# Real API Keys (Use env vars in production)
MARKETSTACK_API_KEY = os.getenv("MARKETSTACK_API_KEY", "7362b480d77a0b5a3cd4b3601f7c70db")
MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY", "158e34144f7dad49dc1dc702ed3ae7a5")

#afzal api
# MARKETSTACK_API_KEY = os.getenv("MARKETSTACK_API_KEY", "65a4255f73c3ec226176aa977375d33f")
# MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY", "dd5c5a74cfd485b399c55fd831035be8")


STOCK_DATA = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology"},
    "AMZN": {"name": "Amazon.com Inc.", "base_price": 145.80, "sector": "Consumer Discretionary"},
    "TSLA": {"name": "Tesla Inc.", "base_price": 248.50, "sector": "Automotive"},
    "MSFT": {"name": "Microsoft Corp.", "base_price": 378.85, "sector": "Technology"},
    "NVDA": {"name": "NVIDIA Corp.", "base_price": 465.20, "sector": "Technology"},
    "META": {"name": "Meta Platforms Inc.", "base_price": 296.70, "sector": "Technology"},
    "NFLX": {"name": "Netflix Inc.", "base_price": 421.15, "sector": "Communication Services"},
    "AMD": {"name": "Advanced Micro Devices", "base_price": 112.30, "sector": "Technology"},
    "INTC": {"name": "Intel Corp.", "base_price": 43.85, "sector": "Technology"},
    "CRM": {"name": "Salesforce Inc.", "base_price": 214.60, "sector": "Technology"},
    "ORCL": {"name": "Oracle Corp.", "base_price": 118.45, "sector": "Technology"},
    "IBM": {"name": "IBM Corp.", "base_price": 165.80, "sector": "Technology"},
    "V": {"name": "Visa Inc.", "base_price": 245.30, "sector": "Financial Services"},
    "MA": {"name": "Mastercard Inc.", "base_price": 398.90, "sector": "Financial Services"},
}

def fetch_price(symbol):
    url = f"http://api.marketstack.com/v1/eod/latest?access_key={MARKETSTACK_API_KEY}&symbols={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        if "data" in data and data["data"]:
            return round(data["data"][0]["close"], 2)
        else:
            print(f"No data for {symbol}")
            return round(STOCK_DATA.get(symbol, {}).get("base_price", random.uniform(10, 500)), 2)
    except Exception as e:
        print(f"Marketstack error: {e}")
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
    company_name = STOCK_DATA[symbol]["name"]
    url = f"http://api.mediastack.com/v1/news?access_key={MEDIASTACK_API_KEY}&keywords={company_name}&limit={limit}&languages=en"
    try:
        response = requests.get(url)
        data = response.json()
        news_items = []
        if "data" in data:
            for item in data["data"]:
                sentiment = analyze_sentiment(item.get("title", "") + " " + item.get("description", ""))
                news_items.append({
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "url": item.get("url"),
                    "source": item.get("source"),
                    "published": item.get("published_at"),
                    "sentiment": sentiment
                })
        return news_items
    except Exception as e:
        print(f"Mediastack error: {e}")
        return []

def fetch_general_news(limit=10):
    url = f"http://api.mediastack.com/v1/news?access_key={MEDIASTACK_API_KEY}&categories=business,technology&limit={limit}&languages=en"
    try:
        response = requests.get(url)
        data = response.json()
        news_items = []
        if "data" in data:
            for item in data["data"]:
                news_items.append({
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                    "published": item.get("published_at")
                })
        return news_items
    except Exception as e:
        print(f"Mediastack general news error: {e}")
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
