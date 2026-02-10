import ccxt
import pandas as pd
# Manual indicators since pandas_ta failed to install
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = calculate_ema(series, fast)
    exp2 = calculate_ema(series, slow)
    macd = exp1 - exp2
    signal_line = calculate_ema(macd, signal)
    return macd, signal_line

def analyze_strategy(df):
    # Calculate Indicators
    df['RSI'] = calculate_rsi(df['close'])
    df['EMA_50'] = calculate_ema(df['close'], 50)
    df['EMA_200'] = calculate_ema(df['close'], 200)
    df['MACD'], df['MACD_Signal'] = calculate_macd(df['close'])
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    signal = "NEUTRAL"
    confidence = "LOW"
    reasons = []

    # 1. Trend Filter
    trend = "BULLISH" if last_row['EMA_50'] > last_row['EMA_200'] else "BEARISH"
    reasons.append(f"Trend is {trend} (EMA50 vs EMA200)")

    # 2. RSI
    if last_row['RSI'] < 30:
        reasons.append(f"RSI Oversold ({last_row['RSI']:.2f})")
        rsi_state = "OVERSOLD"
    elif last_row['RSI'] > 70:
        reasons.append(f"RSI Overbought ({last_row['RSI']:.2f})")
        rsi_state = "OVERBOUGHT"
    else:
        rsi_state = "NEUTRAL"

    # 3. MACD Crossover
    macd_bullish = (prev_row['MACD'] <= prev_row['MACD_Signal']) and (last_row['MACD'] > last_row['MACD_Signal'])
    macd_bearish = (prev_row['MACD'] >= prev_row['MACD_Signal']) and (last_row['MACD'] < last_row['MACD_Signal'])
    
    if macd_bullish: reasons.append("MACD Bullish Crossover")
    if macd_bearish: reasons.append("MACD Bearish Crossover")

    # Strategy Decision Matrix
    if trend == "BULLISH":
        if macd_bullish or (rsi_state == "OVERSOLD"):
            signal = "LONG"
            confidence = "HIGH" if (macd_bullish and rsi_state == "OVERSOLD") else "MEDIUM"
        elif rsi_state == "OVERBOUGHT":
            signal = "EXIT_LONG" # Take profit on long
            
    elif trend == "BEARISH":
        if macd_bearish or (rsi_state == "OVERBOUGHT"):
            signal = "SHORT"
            confidence = "HIGH" if (macd_bearish and rsi_state == "OVERBOUGHT") else "MEDIUM"
        elif rsi_state == "OVERSOLD":
            signal = "EXIT_SHORT" # Take profit on short

    return {
        "price": last_row['close'],
        "signal": signal,
        "confidence": confidence,
        "trend": trend,
        "reasons": reasons,
        "indicators": {
            "RSI": last_row['RSI'],
            "MACD": last_row['MACD'],
            "EMA_50": last_row['EMA_50'],
            "EMA_200": last_row['EMA_200']
        }
    }

def main():
    print("Fetching BTC/USDT data from Binance...")
    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=500)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    result = analyze_strategy(df)
    
    print(f"\n--- BITCOIN STRATEGY REPORT (1H Timeframe) ---")
    print(f"Current Price: ${result['price']:.2f}")
    print(f"Trend: {result['trend']}")
    print(f"Signal: {result['signal']}")
    print(f"Confidence: {result['confidence']}")
    print("\nAnalysis:")
    for r in result['reasons']:
        print(f"- {r}")
    print("\nIndicators:")
    print(f"RSI: {result['indicators']['RSI']:.2f}")
    print(f"MACD: {result['indicators']['MACD']:.2f}")

if __name__ == "__main__":
    main()
