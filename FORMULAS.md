# Stock Portfolio Manager - Key Formulas

## 1. Day's Gain Percentage
Calculates the percentage change in price from the previous close to the current price.

```python
days_gain_pct = ((price - previous_close) / previous_close) * 100
```

---

## 2. Overall Gain Percentage
Calculates the percentage gain/loss since purchase. Uses the actual purchase price if available, otherwise falls back to previous close or a simulated price.

```python
overall_gain_pct = ((price - purchase_price) / purchase_price) * 100
# If purchase_price is not available:
overall_gain_pct = ((price - previous_close) / previous_close) * 100
# If neither is available, simulate:
variation = random.uniform(-0.10, 0.10)
simulated_purchase_price = price * (1 + variation)
overall_gain_pct = ((price - simulated_purchase_price) / simulated_purchase_price) * 100
```

---

## 3. Total Value of a Stock Holding
The total value of a stock in the portfolio.

```python
stock_total_value = price * quantity
```

---

## 4. Sentiment Score (per news item)
Assigns a score based on sentiment analysis:

- Positive: `0.8`
- Neutral: `0.5`
- Negative: `0.2`

---

## 5. Average Sentiment Score (per stock)
Average of all sentiment scores for news items related to a stock.

```python
avg_sentiment_score = total_sentiment_score / news_count if news_count > 0 else 0.5
```

---

## 6. Portfolio Impact Calculation
Determines the impact of a stock on the portfolio based on quantity, gain percentage, and relative value.

```python
quantity_impact = min(quantity / 50, 1.0)  # Cap at 50 shares for max impact

if gain_percentage is None:
    performance_impact = 0.5  # Neutral if no gain data
else:
    # Normalize performance: -20% to +20% range, with 0% being neutral
    performance_impact = max(0, min(1, (gain_percentage + 20) / 40))

impact_score = (quantity_impact * 0.7) + (performance_impact * 0.3)
# Impact level:
#   if impact_score >= 0.6: 'large'
#   elif impact_score >= 0.3: 'mid'
#   else: 'small'
```

---

## 7. Impact Score Percentage (News Impact Card)
Average sentiment score across all stocks, shown as a percentage out of 100.

```jinja2
{% set avg_sentiment_score = (sentiment_scores|sum(attribute="sentiment_score") / sentiment_scores|length) %}
{% set impact_percentage = (avg_sentiment_score * 100)|round(1) %}
```

---

## 8. Initial Gain/Loss on Stock Addition
When a stock is added, the initial gain/loss is calculated as:

```python
initial_gain_pct = ((current_price - purchase_price) / purchase_price) * 100
```

---

## 9. Market Summary (Up/Down Count)
Randomly simulates the number of stocks up or down for a market summary.

```python
up_count = random.randint(int(total_stocks * 0.4), int(total_stocks * 0.7))
down_count = total_stocks - up_count
```

---

## 10. Sentiment Analysis (Text + Price Change)
Determines sentiment class based on text and price change:

- If price_change > 0 and text is neutral: positive
- If price_change < 0 and text is neutral: negative
- If price_change > 0 and text is negative: neutral
- If price_change < 0 and text is positive: neutral
- If price_change_percent > 5: positive
- If price_change_percent < -5: negative
```

---

**Note:** All calculations are performed in Python (backend) or Jinja2 (template) as shown above. 