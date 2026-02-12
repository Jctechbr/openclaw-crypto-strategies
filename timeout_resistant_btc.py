#!/usr/bin/env python3

import requests
import json
import datetime
import time
from typing import List, Dict, Any, Optional

class TimeoutResistantAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.max_retries = 2
        self.timeout = 8  # Reduced timeout to avoid 524 errors
        self.circuit_breaker_timeout = 30  # 30 seconds circuit breaker
        
    def fetch_with_timeout(self, url: str, params: Dict = None, retry_count: int = 0) -> Optional[Dict]:
        """Fetch data with timeout and retry logic"""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout fetching {url}")
            if retry_count < self.max_retries:
                print(f"🔄 Retrying ({retry_count + 1}/{self.max_retries})...")
                time.sleep(2)  # Short delay before retry
                return self.fetch_with_timeout(url, params, retry_count + 1)
            return None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed: {e}")
            return None
    
    def get_crypto_news_fast(self, count: int = 3) -> tuple[List[Dict], str]:
        """Get crypto news with fast timeout handling"""
        print(f"🔍 Fetching crypto news with {self.timeout}s timeout...")
        
        # Try CoinGecko first (fastest)
        articles, source = self._get_coingecko_news_fast(count)
        if articles:
            return articles, 'coingecko'
        
        # Try alternative sources if CoinGecko fails
        articles, source = self._get_alternative_news_fast(count)
        if articles:
            return articles, 'alternative'
        
        return [], 'offline'
    
    def _get_coingecko_news_fast(self, count: int) -> tuple[List[Dict], str]:
        """Fast CoinGecko news fetch"""
        try:
            url = "https://api.coingecko.com/api/v3/news"
            params = {
                'categories': 'cryptocurrency',
                'per_page': min(count, 5),
                'page': 1
            }
            
            data = self.fetch_with_timeout(url, params)
            if data and data.get('data'):
                articles = []
                for item in data['data'][:count]:
                    content = item.get('description', '')[:500]
                    articles.append({
                        'title': item.get('title', 'No title'),
                        'url': item.get('url', ''),
                        'content': content,
                        'published': item.get('published_at', ''),
                        'source': 'CoinGecko'
                    })
                return articles, 'coingecko'
        except Exception as e:
            print(f"⚠️ CoinGecko fast fetch failed: {e}")
        
        return [], None
    
    def _get_alternative_news_fast(self, count: int) -> tuple[List[Dict], str]:
        """Fast alternative news sources"""
        alternatives = [
            ("https://api.binance.com/api/v3/ticker/price", None),
        ]
        
        for url, params in alternatives:
            try:
                data = self.fetch_with_timeout(url, params)
                if data:
                    # Convert price data to news-like format
                    articles = [{
                        'title': f'Binance BTC Price Update',
                        'url': 'https://binance.com',
                        'content': f'BTC/USDT: {data.get("price", "N/A")}',
                        'published': datetime.datetime.now().isoformat(),
                        'source': 'Binance'
                    }]
                    return articles[:count], 'alternative'
            except:
                continue
        
        return [], None
    
    def analyze_sentiment_quick(self, text: str) -> Dict[str, Any]:
        """Quick sentiment analysis with minimal processing"""
        # Simplified crypto sentiment keywords
        bullish = ['bull', 'positive', 'rise', 'gain', 'green', 'moon', 'rally']
        bearish = ['bear', 'negative', 'fall', 'loss', 'red', 'crash', 'dump']
        
        text_lower = text.lower()
        bullish_count = sum(1 for word in bullish if word in text_lower)
        bearish_count = sum(1 for word in bearish if word in text_lower)
        
        if bullish_count > bearish_count:
            sentiment = 'BULLISH'
            strength = 'HIGH' if bullish_count > 2 else 'MODERATE'
        elif bearish_count > bullish_count:
            sentiment = 'BEARISH'
            strength = 'HIGH' if bearish_count > 2 else 'MODERATE'
        else:
            sentiment = 'NEUTRAL'
            strength = 'MODERATE'
        
        return {
            'sentiment': sentiment,
            'strength': strength,
            'impact': 'HIGH' if strength == 'HIGH' else 'MEDIUM',
            'factors': [text[:50] + '...' if len(text) > 50 else text],
            'real_time': True,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    def get_sentiment_or_offline(self) -> Dict[str, Any]:
        """Get sentiment or return offline mode"""
        try:
            articles, source = self.get_crypto_news_fast(3)
            
            if articles and source != 'offline':
                print(f"✅ Got {len(articles)} articles from {source}")
                
                # Quick sentiment analysis
                all_sentiments = []
                for article in articles:
                    sentiment = self.analyze_sentiment_quick(article['content'])
                    all_sentiments.append(sentiment)
                
                # Simple majority vote
                bullish = sum(1 for s in all_sentiments if s['sentiment'] == 'BULLISH')
                bearish = sum(1 for s in all_sentiments if s['sentiment'] == 'BEARISH')
                
                if bullish > bearish:
                    overall_sentiment = 'BULLISH'
                    overall_strength = 'HIGH' if bullish >= 2 else 'MODERATE'
                elif bearish > bullish:
                    overall_sentiment = 'BEARISH'
                    overall_strength = 'HIGH' if bearish >= 2 else 'MODERATE'
                else:
                    overall_sentiment = 'NEUTRAL'
                    overall_strength = 'MODERATE'
                
                return {
                    'sentiment': overall_sentiment,
                    'strength': overall_strength,
                    'impact': 'HIGH' if overall_strength == 'HIGH' else 'MEDIUM',
                    'factors': [a['title'][:50] for a in articles[:2]],
                    'events': [a['title'][:50] for a in articles[:2]],
                    'source': source,
                    'articles_count': len(articles),
                    'real_time': True,
                    'timestamp': datetime.datetime.now().isoformat()
                }
            else:
                print("🔇 No real-time data available - offline mode")
                return {
                    'sentiment': None,
                    'strength': None,
                    'impact': None,
                    'factors': [],
                    'events': [],
                    'source': 'offline',
                    'articles_count': 0,
                    'real_time': False,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'note': 'Technical analysis only - no sentiment data'
                }
                
        except Exception as e:
            print(f"⚠️ Sentiment analysis failed: {e}")
            return {
                'sentiment': None,
                'real_time': False,
                'note': 'Error - using technical analysis only'
            }

# Test the timeout-resistant analyzer
if __name__ == "__main__":
    analyzer = TimeoutResistantAnalyzer()
    result = analyzer.get_sentiment_or_offline()
    print("Timeout-resistant sentiment result:")
    print(json.dumps(result, indent=2))
