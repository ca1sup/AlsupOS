import logging
from textblob import TextBlob
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def analyze_sentiment_simple(text: str) -> tuple[float, float]:
    """
    Returns (polarity, subjectivity).
    Polarity: -1.0 (negative) to 1.0 (positive)
    Subjectivity: 0.0 (objective) to 1.0 (subjective)
    """
    try:
        blob = TextBlob(text)
        return blob.sentiment.polarity, blob.sentiment.subjectivity
    except Exception as e:
        logger.error(f"Sentiment Analysis Failed: {e}")
        return 0.0, 0.0

async def get_mood_health_correlation(days: int = 30) -> List[Dict[str, Any]]:
    """
    Correlates sentiment scores with health metrics (e.g. steps, sleep).
    Returns a list of data points for visualization.
    """
    from backend.database import get_sentiment_history, get_recent_health_metrics_structured
    
    sentiment_data = await get_sentiment_history(days)
    health_data = await get_recent_health_metrics_structured(days)
    
    # Merge by date
    merged = {}
    
    for s in sentiment_data:
        date = s['date'].split('T')[0] # strict ISO format assumption
        if date not in merged: merged[date] = {}
        # Average sentiment if multiple entries per day
        if 'sentiment_sum' not in merged[date]:
            merged[date]['sentiment_sum'] = 0
            merged[date]['sentiment_count'] = 0
        merged[date]['sentiment_sum'] += s['score']
        merged[date]['sentiment_count'] += 1
        
    for h in health_data:
        date = h['date']
        if date not in merged: merged[date] = {}
        merged[date]['steps'] = h.get('steps_count', 0)
        merged[date]['sleep'] = h.get('sleep_total_duration', "0 hr")

    # Format for frontend
    result = []
    for date, data in merged.items():
        sentiment_avg = 0
        if data.get('sentiment_count', 0) > 0:
            sentiment_avg = data['sentiment_sum'] / data['sentiment_count']
            
        result.append({
            "date": date,
            "sentiment": sentiment_avg,
            "steps": data.get('steps', 0),
            "sleep": data.get('sleep', "0 hr")
        })
        
    return sorted(result, key=lambda x: x['date'])