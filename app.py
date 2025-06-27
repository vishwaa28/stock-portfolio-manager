from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from models import db, User, PortfolioStock, WatchlistStock
from api_clients import fetch_price, fetch_news, fetch_all_stocks, fetch_general_news, fetch_detailed_stocks, fetch_sector_news, fetch_company_profile, fetch_previous_close
from sentiment import analyze_sentiment
import random
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import time
import functools
# from flask_wtf import CSRFProtect



# csrf = CSRFProtect()

def timing_decorator(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        print(f"⏱️ {f.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return decorated_function

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    # csrf.init_app(app)
    db.init_app(app)
    mail = Mail(app)

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            user = User(username="admin", password="1234")
            db.session.add(user)
            db.session.commit()

    # Login manager setup
    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route("/")
    @timing_decorator
    def home():
        # Use cached data for better performance
        stocks = fetch_all_stocks()
        ticker_data = fetch_detailed_stocks(limit=5)  # Reduced from 10 to 5
        news_list = fetch_general_news(limit=3)  # Reduced from 5 to 3
        for news in news_list:
            news['sector'] = 'general'
        return render_template("home.html", stocks=stocks, news_list=news_list, ticker_data=ticker_data)

    @app.route("/dashboard")
    @login_required
    @timing_decorator
    def dashboard():
        table = []
        total_value = 0
        overall_sentiment = {"positive": 0, "negative": 0, "neutral": 0}

        # Batch fetch all profiles at once to reduce API calls
        portfolio_symbols = [stock.symbol for stock in current_user.portfolio]
        profiles = {}
        for symbol in portfolio_symbols:
            profiles[symbol] = fetch_company_profile(symbol)

        for stock in current_user.portfolio:
            # Get cached price and news
            price = fetch_price(stock.symbol)
            news = fetch_news(stock.symbol, limit=2)  # Reduced from 3 to 2
            
            # Get sector information from cached profile
            profile = profiles.get(stock.symbol, {})
            sector = profile.get("finnhubIndustry", "Unknown") if profile else "Unknown"
            
            # Calculate price change
            previous_close = fetch_previous_close(stock.symbol)
            change = 0
            if previous_close and price:
                change = price - previous_close
            
            # Only fetch sector news if we have a valid sector and it's not "Unknown"
            sector_news = []
            if sector != "Unknown":
                sector_news = fetch_sector_news(sector, limit=1)  # Reduced from 2 to 1
                # Add sector info to sector news
                for news_item in sector_news:
                    news_item['sector'] = sector
                    news_item['symbol'] = stock.symbol

            # Calculate alerts based on sentiment analysis
            alerts = []
            positive_count = 0
            negative_count = 0
            total_sentiment_score = 0
            news_count = 0

            for n in news:
                sentiment = analyze_sentiment(n["title"] + " " + n.get("description", ""))
                # Calculate sentiment score based on actual sentiment
                if sentiment == "negative":
                    sentiment_score = 0.2  # Low score for negative
                    alerts.append(f"⚠️ Negative sentiment: \"{n['title'][:50]}...\"")
                    negative_count += 1
                elif sentiment == "positive":
                    sentiment_score = 0.8  # High score for positive
                    positive_count += 1
                else:
                    sentiment_score = 0.5  # Neutral score
                
                total_sentiment_score += sentiment_score
                news_count += 1
                
                # Add sentiment score to news item
                n["sentiment_score"] = sentiment_score
                n["sector"] = sector
                n["symbol"] = stock.symbol

            # Calculate average sentiment score
            avg_sentiment_score = total_sentiment_score / news_count if news_count > 0 else 0.5

            # Add price alerts if targets are set
            if stock.target_up and price >= stock.target_up:
                alerts.append(f"🎯 Price target reached: ${price} >= ${stock.target_up}")
            if stock.target_dn and price <= stock.target_dn:
                alerts.append(f"⚠️ Price dropped below target: ${price} <= ${stock.target_dn}")

            # Determine overall sentiment
            if positive_count > negative_count:
                sentiment_class = "positive"
                sentiment_text = "📈 Positive"
                overall_sentiment["positive"] += 1
            elif negative_count > positive_count:
                sentiment_class = "negative"
                sentiment_text = "📉 Negative"
                overall_sentiment["negative"] += 1
            else:
                sentiment_class = "neutral"
                sentiment_text = "➖ Neutral"
                overall_sentiment["neutral"] += 1

            total_value += price

            # Combine stock news and sector news
            all_news = news + sector_news

            table.append({
                "symbol": stock.symbol,
                "name": profile.get("name", stock.symbol) if profile else stock.symbol,
                "price": price,
                "change": change,
                "news": all_news,
                "alerts": alerts,
                "sentiment_class": sentiment_class,
                "sentiment_text": sentiment_text,
                "sentiment_score": avg_sentiment_score,
                "target_up": stock.target_up,
                "target_dn": stock.target_dn,
                "sector": sector
            })
        
        # Only send email if there are stocks in portfolio
        if current_user.portfolio:
            user_email = "vishwaayuvaraj@gmail.com"
            final_msg = ""

            if overall_sentiment["positive"] > overall_sentiment["negative"]:
                final_msg = "📈 Your stocks are showing overall **positive sentiment**. It might be a good time to hold or sell at profit."
            elif overall_sentiment["negative"] > overall_sentiment["positive"]:
                final_msg = "📉 Your stocks are showing overall **negative sentiment**. Consider reviewing your portfolio to prevent potential loss."
            else:
                final_msg = "➖ Your stocks are showing overall **neutral sentiment**. Monitor for changes."

            try:
                msg = Message("📊 Stock Sentiment Analysis", recipients=[user_email])
                msg.body = final_msg
                mail.send(msg)
            except Exception as e:
                print(f"Failed to send email: {e}")

        return render_template("dashboard.html", table=table, total_value=total_value)


    @app.route("/api/price/<symbol>")
    def api_price(symbol):
        return jsonify({"price": fetch_price(symbol)})

    @app.route("/api/top_stocks")
    def api_top_stocks():
        stocks = fetch_detailed_stocks(limit=10)
        return jsonify([
            {
                "symbol": s["symbol"],
                "name": s["name"],
                "price": s["price"],
                "change": s["change"],
                "percent": s["percent"],
                "volume": s["volume"],
                "sector": s["sector"],
                "market_cap": s["market_cap"]
            } for s in stocks
        ])

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = User.query.filter_by(username=request.form["username"]).first()
            if user and user.password == request.form["password"]:
                login_user(user)
                return redirect(url_for("home"))
            flash("Invalid credentials", "danger")
        return render_template("login.html")


    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/add_stock", methods=["GET", "POST"])
    @login_required
    def add_stock():
        if request.method == "POST":
            symbol = request.form.get("symbol", "").upper()
            target_up = request.form.get("target_up")
            target_dn = request.form.get("target_dn")
            
            if symbol:
                # Check if stock already exists in portfolio
                existing = PortfolioStock.query.filter_by(user_id=current_user.id, symbol=symbol).first()
                if existing:
                    flash(f"Stock {symbol} is already in your portfolio", "warning")
                else:
                    # Create new portfolio stock
                    stock = PortfolioStock(
                        user_id=current_user.id,
                        symbol=symbol,
                        target_up=float(target_up) if target_up else None,
                        target_dn=float(target_dn) if target_dn else None
                    )
                    db.session.add(stock)
                    db.session.commit()
                    flash(f"Stock {symbol} added to portfolio successfully", "success")
                    return redirect(url_for("dashboard"))
            else:
                flash("Please enter a valid stock symbol", "danger")
        
        return render_template("add_stock.html")

    def monitor_portfolio():
        with app.app_context():
            for stock in PortfolioStock.query.all():
                for article in fetch_news(stock.symbol, limit=3):
                    sentiment = analyze_sentiment(article["title"] + " " + article.get("description", ""))
                    if sentiment == "negative":
                        print(f"[SENTIMENT ALERT] {stock.symbol}: {article['title']}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(monitor_portfolio, "interval", minutes=5)
    scheduler.start()

    @app.route("/api/stock_history/<symbol>")
    def api_stock_history(symbol):
        # Get days parameter from query string, default to 30 days
        days = request.args.get('days', 30, type=int)
        
        # Try to fetch from Finnhub, fallback to mock data
        import requests
        from datetime import datetime, timedelta
        FINNHUB_API_KEY = app.config.get('FINNHUB_API_KEY', 'd1d3ap9r01qic6lgtil0d1d3ap9r01qic6lgtilg')
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={int(start.timestamp())}&to={int(end.timestamp())}&token={FINNHUB_API_KEY}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get('s') == 'ok' and data.get('t'):
                result = []
                for i in range(len(data['t'])):
                    date = datetime.fromtimestamp(data['t'][i]).strftime('%Y-%m-%d')
                    price = data['c'][i]
                    result.append({"date": date, "price": price})
                return jsonify(result)
        except Exception as e:
            print(f"Finnhub history error: {e}")
        
        # Fallback: generate mock data for the requested period
        today = datetime.now()
        result = []
        price = 100 + random.uniform(-20, 20)  # Start with a random price
        
        for i in range(days, 0, -1):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            # Add some realistic price movement
            price += random.uniform(-3, 3)
            price = max(price, 1)  # Ensure price doesn't go below $1
            result.append({"date": date, "price": round(price, 2)})
        
        return jsonify(result)

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)