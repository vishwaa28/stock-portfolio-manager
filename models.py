from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    portfolio = db.relationship('PortfolioStock', backref='owner', lazy=True)
    watchlist = db.relationship('WatchlistStock', backref='user', lazy=True)

class PortfolioStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, default=1)  # Number of shares owned
    purchase_price = db.Column(db.Float, default=0)  # Average purchase price per share
    target_up = db.Column(db.Float)
    target_dn = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class WatchlistStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (UniqueConstraint('symbol', 'user_id', name='unique_watchlist'), )

class SentimentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sentiment_score = db.Column(db.Float, nullable=False)
    sentiment_class = db.Column(db.String(20), nullable=False)  # positive, negative, neutral
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = db.relationship('User', backref='sentiment_history')
    
    __table_args__ = (UniqueConstraint('symbol', 'user_id', 'timestamp', name='unique_sentiment_record'), )

