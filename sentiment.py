from transformers import pipeline
sentiment_pipeline = pipeline("sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    revision="714eb0f")

def analyze_sentiment(text, price_change=None, price_change_percent=None):
    """
    Enhanced sentiment analysis that considers both text content and price changes
    """
    # Get base sentiment from ML model
    result = sentiment_pipeline(text[:512])[0]
    base_sentiment = result["label"].lower()
    
    # Convert ML model output to our format
    if base_sentiment == "positive":
        text_sentiment = "positive"
    elif base_sentiment == "negative":
        text_sentiment = "negative"
    else:
        text_sentiment = "neutral"
    
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