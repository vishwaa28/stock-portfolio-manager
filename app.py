from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from models import db, User, PortfolioStock, WatchlistStock
from api_clients import fetch_price, fetch_news, fetch_all_stocks, fetch_general_news, fetch_detailed_stocks, fetch_sector_news
from sentiment import analyze_sentiment
import random
from datetime import datetime, timedelta
from flask_mail import Mail, Message
# from flask_wtf import CSRFProtect



# csrf = CSRFProtect()

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
    def home():
        stocks = fetch_all_stocks()
        ticker_data = fetch_detailed_stocks(limit=10)
        # Gather unique sectors from top 10 stocks
        unique_sectors = set([s['sector'] for s in ticker_data if s.get('sector') and s['sector'] != 'Unknown'])
        news_list = []
        recent_days = 3
        now = datetime.now()
        for sector in unique_sectors:
            sector_news = fetch_sector_news(sector, limit=10)
            # Only include news from the last 3 days
            recent_news = []
            for news in sector_news:
                try:
                    published_date = datetime.strptime(news['published'], '%Y-%m-%d')
                    if (now - published_date).days <= recent_days:
                        news['sector'] = sector
                        recent_news.append(news)
                except Exception:
                    continue
            # Sort by published date descending
            recent_news.sort(key=lambda n: n['published'], reverse=True)
            news_list.extend(recent_news[:3])
        # Fallback to general news if no sector news found
        if not news_list:
            news_list = fetch_general_news()
            for news in news_list:
                news['sector'] = 'general'
        # Sort all news by published date descending
        news_list.sort(key=lambda n: n['published'], reverse=True)
        return render_template("home.html", stocks=stocks, news_list=news_list, ticker_data=ticker_data)

    @app.route("/dashboard")
    @login_required
    def dashboard():
        table = []
        total_value = 0
        overall_sentiment = {"positive": 0, "negative": 0, "neutral": 0}

        for stock in current_user.portfolio:
            price = fetch_price(stock.symbol)
            news = fetch_news(stock.symbol, limit=3)

            # Calculate alerts based on sentiment analysis
            alerts = []
            positive_count = 0
            negative_count = 0

            for n in news:
                sentiment = analyze_sentiment(n["title"] + " " + n.get("description", ""))
                if sentiment == "negative":
                    alerts.append(f"⚠️ Negative sentiment: \"{n['title'][:50]}...\"")
                    negative_count += 1

                elif sentiment == "positive":
                    positive_count += 1

            # Add price alerts if targets are set
            if stock.target_up and price >= stock.target_up:
                alerts.append(f"🎯 Price target reached: ${price} >= ${stock.target_up}")
            if stock.target_dn and price <= stock.target_dn:
                alerts.append(f"⚠️ Price dropped below target: ${price} <= ${stock.target_dn}")

            # Determine overall sentiment
            if positive_count > negative_count:
                sentiment_class = "positive"
                sentiment_text = "📈 Positive"
            elif negative_count > positive_count:
                sentiment_class = "negative"
                sentiment_text = "📉 Negative"
            else:
                sentiment_class = "neutral"
                sentiment_text = "➖ Neutral"

            total_value += price

            table.append({
                "symbol": stock.symbol,
                "price": price,
                "news": news,
                "alerts": alerts,
                "sentiment_class": sentiment_class,
                "sentiment_text": sentiment_text,
                "target_up": stock.target_up,
                "target_dn": stock.target_dn
            })
        user_email = "vishwaayuvaraj@gmail.com"
        final_msg = ""

        if overall_sentiment["positive"] > overall_sentiment["negative"]:
            final_msg = "📈 Your stocks are showing overall **positive sentiment**. It might be a good time to hold or sell at profit."
        elif overall_sentiment["negative"] > overall_sentiment["positive"]:
            final_msg = "📉 Your stocks are showing overall **negative sentiment**. Consider reviewing your portfolio to prevent potential loss."
        else:
            final_msg = "📉 Your stocks are showing overall **negative sentiment**. Consider reviewing your portfolio to prevent potential loss."

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
        # Try to fetch from Finnhub, fallback to mock data
        import requests
        from datetime import datetime, timedelta
        FINNHUB_API_KEY = app.config.get('FINNHUB_API_KEY', 'd1d3ap9r01qic6lgtil0d1d3ap9r01qic6lgtilg')
        try:
            end = datetime.now()
            start = end - timedelta(days=30)
            url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={int(start.timestamp())}&to={int(end.timestamp())}&token={FINNHUB_API_KEY}"
            resp = requests.get(url)
            data = resp.json()
            if data.get('s') == 'ok':
                result = []
                for i in range(len(data['t'])):
                    date = datetime.fromtimestamp(data['t'][i]).strftime('%Y-%m-%d')
                    price = data['c'][i]
                    result.append({"date": date, "price": price})
                return jsonify(result)
        except Exception as e:
            print(f"Finnhub history error: {e}")
        # Fallback: generate mock data
        today = datetime.now()
        result = []
        price = 100
        for i in range(30, 0, -1):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            price += random.uniform(-2, 2)
            result.append({"date": date, "price": round(price, 2)})
        return jsonify(result)

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)