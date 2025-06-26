from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from models import db, User, PortfolioStock, WatchlistStock
from api_clients import fetch_price, fetch_news, fetch_all_stocks, fetch_general_news
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
        news_list = fetch_general_news()
        return render_template("home.html", stocks=stocks, news_list=news_list)

    @app.route("/add_to_watchlist", methods=["POST"])
    # @login_required
    def add_to_watchlist():
        symbol = request.form["symbol"].upper()
        if not WatchlistStock.query.filter_by(symbol=symbol, user_id=current_user.id).first():
            db.session.add(WatchlistStock(symbol=symbol, user_id=current_user.id))
            db.session.commit()
            flash(f"{symbol} added to your watchlist!", "success")
        else:
            flash(f"{symbol} is already in your watchlist.", "warning")
        return redirect(url_for("watchlist"))

    @app.route("/add_stock", methods=["GET", "POST"])
    @login_required
    def add_stock():
        if request.method == "POST":
            symbol = request.form["symbol"].upper()
            if not PortfolioStock.query.filter_by(symbol=symbol, user_id=current_user.id).first():
                db.session.add(PortfolioStock(symbol=symbol, user_id=current_user.id))
                db.session.commit()
                flash(f"{symbol} added to your portfolio!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash(f"{symbol} is already in your portfolio.", "warning")
        return render_template("add_stock.html")

    @app.route("/portfolio")
    @login_required
    def watchlist():
        stocks = WatchlistStock.query.filter_by(user_id=current_user.id).all()
        data = []
        related_news = []

        for stock in stocks:
            price = fetch_price(stock.symbol)
            news = fetch_news(stock.symbol, limit=3)
            data.append({
                "symbol": stock.symbol,
                "price": price,
                "news": news
            })
            related_news.extend(news[:2])
        return render_template("portfolio.html", watchlist=data, related_news=related_news)

    @app.route("/buy_stock/<symbol>", methods=["POST"])
    @login_required
    def buy_stock(symbol):
        symbol = symbol.upper()
        # Remove from watchlist
        WatchlistStock.query.filter_by(symbol=symbol, user_id=current_user.id).delete()

        # Add to portfolio if not already there
        if not PortfolioStock.query.filter_by(symbol=symbol, user_id=current_user.id).first():
            db.session.add(PortfolioStock(symbol=symbol, user_id=current_user.id))
            flash(f"{symbol} bought and added to your portfolio!", "success")
        else:
            flash(f"{symbol} is already in your portfolio.", "warning")

        db.session.commit()
        return redirect(url_for("watchlist"))

    @app.route("/remove_from_watchlist/<symbol>", methods=["POST"])
    @login_required
    def remove_from_watchlist(symbol):
        WatchlistStock.query.filter_by(symbol=symbol, user_id=current_user.id).delete()
        db.session.commit()
        flash(f"{symbol} removed from watchlist.", "info")
        return redirect(url_for("watchlist"))

    @app.route("/remove_from_portfolio/<symbol>", methods=["POST"])
    @login_required
    def remove_from_portfolio(symbol):
        deleted = PortfolioStock.query.filter_by(symbol=symbol, user_id=current_user.id).delete()
        if deleted == 0:
            flash("No such stock found in your portfolio.", "warning")
        else:
            flash(f"{symbol} removed from portfolio.", "info")
        db.session.commit()
        return redirect(url_for("dashboard"))

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

        # Send the email
        try:
            msg = Message("📊 Stock Sentiment Analysis", recipients=[user_email])
            msg.body = final_msg
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send email: {e}")

        return render_template("dashboard.html", table=table, total_value=total_value)

    @app.route("/set_targets/<symbol>", methods=["POST"])
    @login_required
    def set_targets(symbol):
        stock = PortfolioStock.query.filter_by(symbol=symbol, user_id=current_user.id).first()
        if stock:
            target_up = request.form.get("target_up")
            target_dn = request.form.get("target_dn")

            stock.target_up = float(target_up) if target_up else None
            stock.target_dn = float(target_dn) if target_dn else None
            db.session.commit()
            flash(f"Price targets updated for {symbol}!", "success")
        return redirect(url_for("dashboard"))

    @app.route("/api/price/<symbol>")
    def api_price(symbol):
        return jsonify({"price": fetch_price(symbol)})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = User.query.filter_by(username=request.form["username"]).first()
            if user and user.password == request.form["password"]:
                login_user(user)
                return redirect(url_for("home"))
            flash("Invalid credentials", "danger")
        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        return render_template("register.html")


    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    def monitor_portfolio():
        with app.app_context():
            for stock in PortfolioStock.query.all():
                price = fetch_price(stock.symbol)
                if stock.target_up and price >= stock.target_up:
                    print(f"[ALERT] {stock.symbol} reached target: ${price}")
                if stock.target_dn and price <= stock.target_dn:
                    print(f"[ALERT] {stock.symbol} dropped to: ${price}")

                for article in fetch_news(stock.symbol, limit=3):
                    sentiment = analyze_sentiment(article["title"] + " " + article.get("description", ""))
                    if sentiment == "negative":
                        print(f"[SENTIMENT ALERT] {stock.symbol}: {article['title']}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(monitor_portfolio, "interval", minutes=5)
    scheduler.start()

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)