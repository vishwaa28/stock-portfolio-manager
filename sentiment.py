from transformers import pipeline
sentiment_pipeline = pipeline("sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    revision="714eb0f")

def analyze_sentiment(text):
    result = sentiment_pipeline(text[:512])[0]
    return result["label"].lower()