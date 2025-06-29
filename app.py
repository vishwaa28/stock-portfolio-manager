from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from models import db, User, PortfolioStock, WatchlistStock, SentimentHistory
from api_clients import fetch_price, fetch_news, fetch_all_stocks, fetch_general_news, fetch_detailed_stocks, fetch_sector_news, fetch_company_profile, fetch_previous_close, fetch_stock_logo
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
            print("✅ Admin user created successfully")
        else:
            print("✅ Admin user already exists")
        
        # Check if database tables are created
        try:
            portfolio_count = PortfolioStock.query.count()
            print(f"✅ Database initialized. Current portfolio stocks: {portfolio_count}")
        except Exception as e:
            print(f"❌ Database error: {e}")
            db.create_all()
            print("✅ Database tables recreated")

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
        
        # Add logo data to ticker_data
        for stock in ticker_data:
            stock['logo'] = fetch_stock_logo(stock['symbol'])
        
        # Fetch news from different sectors for better filtering
        news_list = []
        
        # Get general market news
        general_news = fetch_general_news(limit=5)  # Increased from 2 to 5
        for news in general_news:
            news['sector'] = 'General Market'
            news['sentiment'] = analyze_sentiment(news.get('title', '') + ' ' + news.get('description', ''))
        news_list.extend(general_news)
        
        # Get news from popular sectors
        popular_sectors = ['Technology', 'Healthcare', 'Finance', 'Energy', 'Oil', 'Automobiles', 'Retail']
        for sector in popular_sectors:
            try:
                sector_news = fetch_sector_news(sector, limit=3)  # Increased from 1 to 3
                for news in sector_news:
                    news['sector'] = sector
                    news['sentiment'] = analyze_sentiment(news.get('title', '') + ' ' + news.get('description', ''))
                news_list.extend(sector_news)
            except Exception as e:
                print(f"Error fetching news for sector {sector}: {e}")
                continue
        
        # Limit total news to 20 articles
        news_list = news_list[:20]
        
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
            days_gain_pct = None
            overall_gain_pct = None
            
            if previous_close and price:
                change = price - previous_close
                days_gain_pct = ((price - previous_close) / previous_close) * 100 if previous_close else None
            
            # Calculate overall gain percentage if purchase price is available
            if stock.purchase_price and price and stock.purchase_price > 0:
                overall_gain_pct = ((price - stock.purchase_price) / stock.purchase_price) * 100
            else:
                # If no purchase price is set, show N/A or calculate based on a default
                overall_gain_pct = None
            
            # Calculate total value for this stock (price * quantity)
            stock_total_value = price * stock.quantity if price else 0
            total_value += stock_total_value
            
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
                # Use enhanced sentiment analysis that considers price changes
                sentiment = analyze_sentiment(
                    n["title"] + " " + n.get("description", ""), 
                    price_change=change, 
                    price_change_percent=days_gain_pct
                )
                # Calculate sentiment score based on actual sentiment
                if sentiment == "negative":
                    sentiment_score = 0.2  # Low score for negative
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

            # Determine overall sentiment - also consider price changes if no news
            if news_count == 0 and change is not None:
                # If no news, base sentiment on price change
                if change > 0:
                    sentiment_class = "positive"
                    sentiment_text = "📈 Positive"
                    overall_sentiment["positive"] += 1
                elif change < 0:
                    sentiment_class = "negative"
                    sentiment_text = "📉 Negative"
                    overall_sentiment["negative"] += 1
                else:
                    sentiment_class = "neutral"
                    sentiment_text = "➖ Neutral"
                    overall_sentiment["neutral"] += 1
            else:
                # Use news-based sentiment
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

            # Check for sentiment change alerts using smart alert system
            previous_sentiment = get_previous_sentiment(stock.symbol, current_user.id)
            should_alert, alert_message = should_alert_sentiment_change(
                previous_sentiment, avg_sentiment_score, sentiment_class
            )
            
            if should_alert:
                alerts.append(f"🚨 {alert_message}")
            
            # Save current sentiment to history
            save_sentiment_history(stock.symbol, current_user.id, avg_sentiment_score, sentiment_class)

            # Add price alerts if targets are set
            if stock.target_up and price >= stock.target_up:
                alerts.append(f"🎯 Price target reached: ${price} >= ${stock.target_up}")
            if stock.target_dn and price <= stock.target_dn:
                alerts.append(f"⚠️ Price dropped below target: ${price} <= ${stock.target_dn}")

            # Combine stock news and sector news
            all_news = news + sector_news

            # Calculate portfolio impact
            portfolio_impact = calculate_portfolio_impact(
                stock.quantity, 
                overall_gain_pct, 
                total_value,
                stock_total_value
            )

            table.append({
                "symbol": stock.symbol,
                "name": profile.get("name", stock.symbol) if profile else stock.symbol,
                "price": price,
                "quantity": stock.quantity,
                "total_value": stock_total_value,
                "change": change,
                "days_gain_pct": days_gain_pct,
                "overall_gain_pct": overall_gain_pct,
                "portfolio_impact": portfolio_impact,
                "news": all_news,
                "alerts": alerts,
                "sentiment_class": sentiment_class,
                "sentiment_text": sentiment_text,
                "sentiment_score": avg_sentiment_score,
                "target_up": stock.target_up,
                "target_dn": stock.target_dn,
                "sector": sector,
                "logo": fetch_stock_logo(stock.symbol)
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
                "market_cap": s["market_cap"],
                "logo": fetch_stock_logo(s["symbol"])
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
            symbol = request.form.get("symbol", "").upper().strip()
            quantity = request.form.get("quantity", "1")
            purchase_price = request.form.get("purchase_price")
            target_up = request.form.get("target_up")
            target_dn = request.form.get("target_dn")
            
            print(f"🔍 Adding stock: {symbol}, quantity: {quantity}, purchase_price: {purchase_price}, target_up: {target_up}, target_dn: {target_dn}")
            print(f"🔍 Current user: {current_user.username} (ID: {current_user.id})")
            
            if not symbol:
                print("❌ No symbol provided")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"error": "Please enter a valid stock symbol"}), 400
                flash("Please enter a valid stock symbol", "danger")
                return render_template("add_stock.html")
            
            # Check if stock already exists in portfolio
            existing = PortfolioStock.query.filter_by(user_id=current_user.id, symbol=symbol).first()
            if existing:
                print(f"❌ Stock {symbol} already exists in portfolio")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"error": f"Stock {symbol} is already in your portfolio"}), 400
                flash(f"Stock {symbol} is already in your portfolio", "warning")
                return render_template("add_stock.html")
            
            try:
                # Convert quantity to integer, default to 1 if invalid
                try:
                    quantity = int(quantity)
                    if quantity <= 0:
                        quantity = 1
                except (ValueError, TypeError):
                    quantity = 1
                
                # Convert purchase_price to float, default to current price if not provided
                try:
                    purchase_price = float(purchase_price)
                except (ValueError, TypeError):
                    purchase_price = fetch_price(symbol)
                
                # Create new portfolio stock
                stock = PortfolioStock(
                    user_id=current_user.id,
                    symbol=symbol,
                    quantity=quantity,
                    purchase_price=purchase_price,
                    target_up=float(target_up) if target_up else None,
                    target_dn=float(target_dn) if target_dn else None
                )
                print(f"✅ Creating stock object: {stock.symbol} with quantity {stock.quantity} at purchase price {stock.purchase_price}")
                
                db.session.add(stock)
                db.session.commit()
                print(f"✅ Stock {symbol} added to database successfully")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"success": f"Stock {symbol} added to portfolio successfully"}), 200
                
                flash(f"Stock {symbol} added to portfolio successfully", "success")
                return redirect(url_for("dashboard"))
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error adding stock: {e}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"error": "Failed to add stock. Please try again."}), 500
                flash("Failed to add stock. Please try again.", "danger")
                return render_template("add_stock.html")
        
        return render_template("add_stock.html")

    def monitor_portfolio():
        with app.app_context():
            for stock in PortfolioStock.query.all():
                for article in fetch_news(stock.symbol, limit=3):
                    # Get current price and change for enhanced sentiment analysis
                    price = fetch_price(stock.symbol)
                    previous_close = fetch_previous_close(stock.symbol)
                    change = price - previous_close if price and previous_close else 0
                    days_gain_pct = ((price - previous_close) / previous_close) * 100 if price and previous_close else None
                    
                    sentiment = analyze_sentiment(
                        article["title"] + " " + article.get("description", ""),
                        price_change=change,
                        price_change_percent=days_gain_pct
                    )
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

    @app.route("/test_db")
    @login_required
    def test_db():
        try:
            # Test database connection
            user_count = User.query.count()
            portfolio_count = PortfolioStock.query.count()
            user_portfolio_count = PortfolioStock.query.filter_by(user_id=current_user.id).count()
            
            return jsonify({
                "status": "success",
                "message": "Database connection working",
                "data": {
                    "total_users": user_count,
                    "total_portfolio_stocks": portfolio_count,
                    "current_user_portfolio": user_portfolio_count,
                    "current_user": current_user.username,
                    "current_user_id": current_user.id
                }
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Database error: {str(e)}"
            }), 500

    def get_previous_sentiment(symbol, user_id, hours_back=24):
        """Get the most recent sentiment data for a stock within the specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        previous_sentiment = SentimentHistory.query.filter_by(
            symbol=symbol, 
            user_id=user_id
        ).filter(
            SentimentHistory.timestamp >= cutoff_time
        ).order_by(SentimentHistory.timestamp.desc()).first()
        
        return previous_sentiment

    def should_alert_sentiment_change(previous_sentiment, current_sentiment_score, current_sentiment_class):
        """
        Determine if we should alert based on sentiment change
        Alerts only when:
        1. Moving from positive to negative (score drops below 0.4)
        2. Moving from neutral to very negative (score drops below 0.3)
        3. Significant drop in score (more than 0.3 points)
        """
        if not previous_sentiment:
            # No previous data, don't alert
            return False, None
        
        previous_score = previous_sentiment.sentiment_score
        previous_class = previous_sentiment.sentiment_class
        score_change = previous_score - current_sentiment_score
        
        # Case 1: Moving from positive to negative
        if previous_class == "positive" and current_sentiment_score < 0.4:
            return True, f"Sentiment dropped from positive ({previous_score:.2f}) to negative ({current_sentiment_score:.2f})"
        
        # Case 2: Moving from neutral to very negative
        if previous_class == "neutral" and current_sentiment_score < 0.3:
            return True, f"Sentiment dropped from neutral ({previous_score:.2f}) to very negative ({current_sentiment_score:.2f})"
        
        # Case 3: Significant drop in score (more than 0.3 points)
        if score_change > 0.3:
            return True, f"Significant sentiment drop: {previous_score:.2f} → {current_sentiment_score:.2f} (change: -{score_change:.2f})"
        
        return False, None

    def save_sentiment_history(symbol, user_id, sentiment_score, sentiment_class):
        """Save current sentiment data to history"""
        try:
            sentiment_record = SentimentHistory(
                symbol=symbol,
                user_id=user_id,
                sentiment_score=sentiment_score,
                sentiment_class=sentiment_class
            )
            db.session.add(sentiment_record)
            db.session.commit()
        except Exception as e:
            print(f"Error saving sentiment history for {symbol}: {e}")
            db.session.rollback()

    @app.route("/api/alerts/<symbol>")
    @login_required
    def api_alerts(symbol):
        """Get alerts for a specific stock"""
        try:
            # Get the stock from user's portfolio
            stock = PortfolioStock.query.filter_by(
                user_id=current_user.id, 
                symbol=symbol
            ).first()
            
            if not stock:
                return jsonify({"alerts": []})
            
            # Get current sentiment data
            price = fetch_price(symbol)
            news = fetch_news(symbol, limit=2)
            
            # Calculate price change for enhanced sentiment analysis
            previous_close = fetch_previous_close(symbol)
            change = 0
            days_gain_pct = None
            
            if previous_close and price:
                change = price - previous_close
                days_gain_pct = ((price - previous_close) / previous_close) * 100 if previous_close else None
            
            # Calculate current sentiment
            positive_count = 0
            negative_count = 0
            total_sentiment_score = 0
            news_count = 0
            
            for n in news:
                # Use enhanced sentiment analysis that considers price changes
                sentiment = analyze_sentiment(
                    n["title"] + " " + n.get("description", ""),
                    price_change=change,
                    price_change_percent=days_gain_pct
                )
                if sentiment == "negative":
                    sentiment_score = 0.2
                    negative_count += 1
                elif sentiment == "positive":
                    sentiment_score = 0.8
                    positive_count += 1
                else:
                    sentiment_score = 0.5
                
                total_sentiment_score += sentiment_score
                news_count += 1
            
            avg_sentiment_score = total_sentiment_score / news_count if news_count > 0 else 0.5
            
            # Determine sentiment class - also consider price changes if no news
            if news_count == 0 and change is not None:
                # If no news, base sentiment on price change
                if change > 0:
                    sentiment_class = "positive"
                elif change < 0:
                    sentiment_class = "negative"
                else:
                    sentiment_class = "neutral"
            else:
                # Use news-based sentiment
                if positive_count > negative_count:
                    sentiment_class = "positive"
                elif negative_count > positive_count:
                    sentiment_class = "negative"
                else:
                    sentiment_class = "neutral"
            
            # Check for sentiment change alerts
            previous_sentiment = get_previous_sentiment(symbol, current_user.id)
            should_alert, alert_message = should_alert_sentiment_change(
                previous_sentiment, avg_sentiment_score, sentiment_class
            )
            
            alerts = []
            if should_alert:
                alerts.append({
                    "type": "sentiment_change",
                    "message": alert_message,
                    "severity": "high" if avg_sentiment_score < 0.3 else "medium"
                })
            
            # Add price alerts if targets are set
            if stock.target_up and price >= stock.target_up:
                alerts.append({
                    "type": "price_target",
                    "message": f"Price target reached: ${price} >= ${stock.target_up}",
                    "severity": "medium"
                })
            if stock.target_dn and price <= stock.target_dn:
                alerts.append({
                    "type": "price_target",
                    "message": f"Price dropped below target: ${price} <= ${stock.target_dn}",
                    "severity": "high"
                })
            
            return jsonify({"alerts": alerts})
            
        except Exception as e:
            print(f"Error getting alerts for {symbol}: {e}")
            return jsonify({"alerts": []})

    def calculate_portfolio_impact(quantity, gain_percentage, total_portfolio_value, stock_total_value):
        """
        Calculate the impact of a stock on the portfolio
        Impact is based on:
        1. Quantity (more shares = higher impact)
        2. Gain percentage (better performance = higher impact)
        3. Relative to total portfolio value
        
        Returns: 'small', 'mid', or 'large'
        """
        if total_portfolio_value == 0:
            return 'small'
        
        # Calculate impact score
        # Base impact from quantity (normalized)
        quantity_impact = min(quantity / 50, 1.0)  # Cap at 50 shares for max impact
        
        # Performance impact (handle None and 0 values)
        if gain_percentage is None:
            performance_impact = 0.5  # Neutral if no gain data
        else:
            # Normalize performance: -20% to +20% range, with 0% being neutral
            performance_impact = max(0, min(1, (gain_percentage + 20) / 40))
        
        # Combined impact score
        impact_score = (quantity_impact * 0.7) + (performance_impact * 0.3)
        
        # Determine impact level
        if impact_score >= 0.6:
            return 'large'
        elif impact_score >= 0.3:
            return 'mid'
        else:
            return 'small'

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)