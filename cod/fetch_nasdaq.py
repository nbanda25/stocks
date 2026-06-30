#!/usr/bin/env python3
"""
Nasdaq Historical Stock Price Downloader
Fetches historical stock price data (OHLCV) from Nasdaq's API and saves it as a cleaned CSV.
"""

import os
import sys
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta

def clean_price(val):
    """Clean dollar signs and commas from price strings and convert to float."""
    if pd.isna(val) or not isinstance(val, str):
        return val
    val_clean = val.replace('$', '').replace(',', '').strip()
    try:
        return float(val_clean)
    except ValueError:
        return None

def clean_volume(val):
    """Clean commas from volume strings and convert to integer."""
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    val_clean = val.replace(',', '').strip()
    try:
        return int(val_clean)
    except ValueError:
        return 0

def fetch_historical_data(ticker, start_date, end_date):
    """
    Fetch historical data for a given ticker from api.nasdaq.com.
    
    Args:
        ticker (str): Stock ticker symbol (e.g., 'AAPL').
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.
        
    Returns:
        pd.DataFrame: Cleaned historical stock data, filtered to the requested date range.
    """
    url = f"https://api.nasdaq.com/api/quote/{ticker.upper()}/historical"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "origin": "https://www.nasdaq.com",
        "referer": "https://www.nasdaq.com/",
        "accept-language": "en-US,en;q=0.9",
    }
    
    # Nasdaq's API has quirks where certain weekend dates as fromdate, or recent dates
    # as todate can cause internal query errors (e.g. Code 1000: 'Something went wrong').
    # We generate a series of fallback parameter strategies to bypass these quirks.
    attempts = [
        {"from": start_date, "to": end_date},
        {"from": start_date, "to": "2030-12-31"},  # Use a far-future todate to avoid temporary current-day edge cases
    ]
    
    # Try shifting the start date back to preceding weekdays if it falls on a weekend
    try:
        from_dt = datetime.strptime(start_date, "%Y-%m-%d")
        if from_dt.weekday() == 5:    # Saturday
            shifted_from = (from_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            attempts.append({"from": shifted_from, "to": end_date})
            attempts.append({"from": shifted_from, "to": "2030-12-31"})
        elif from_dt.weekday() == 6:  # Sunday
            shifted_from = (from_dt - timedelta(days=2)).strftime("%Y-%m-%d")
            attempts.append({"from": shifted_from, "to": end_date})
            attempts.append({"from": shifted_from, "to": "2030-12-31"})
    except ValueError:
        pass
        
    # Additional robust offsets in case of other calendar/holiday conflicts
    for offset in [-1, -2, -3, 1, 2, 3]:
        try:
            from_dt = datetime.strptime(start_date, "%Y-%m-%d")
            shifted_from = (from_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            attempts.append({"from": shifted_from, "to": "2030-12-31"})
            attempts.append({"from": shifted_from, "to": end_date})
        except ValueError:
            pass
            
    # Deduplicate attempts while preserving order
    seen = set()
    unique_attempts = []
    for att in attempts:
        key = (att["from"], att["to"])
        if key not in seen:
            seen.add(key)
            unique_attempts.append(att)
            
    json_data = None
    success = False
    
    for idx, att in enumerate(unique_attempts):
        from_d = att["from"]
        to_d = att["to"]
        
        params = {
            "assetclass": "stocks",
            "fromdate": from_d,
            "todate": to_d,
            "limit": "9999"
        }
        
        print(f"Attempt {idx+1}/{len(unique_attempts)}: Querying {ticker.upper()} ({from_d} to {to_d})...")
        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
        except Exception as e:
            print(f"  HTTP error: {e}", file=sys.stderr)
            continue
            
        if response.status_code != 200:
            print(f"  HTTP Status {response.status_code}", file=sys.stderr)
            continue
            
        try:
            res_json = response.json()
        except ValueError:
            print("  Failed to parse JSON response.", file=sys.stderr)
            continue
            
        status = res_json.get("status", {})
        bcode_msg = status.get("bCodeMessage")
        
        if res_json.get("data") is not None:
            trades_table = res_json["data"].get("tradesTable", {})
            rows = trades_table.get("rows", [])
            if rows:
                json_data = res_json
                success = True
                print(f"  Success! Retrieved {len(rows)} records.")
                break
            else:
                print("  Warning: Success status but 0 rows returned.")
        else:
            err_msg = bcode_msg[0].get("errorMessage") if bcode_msg else "Unknown API Error"
            print(f"  API Error: {err_msg}")
            
    if not success or json_data is None:
        print(f"Error: All attempts to fetch data for {ticker.upper()} failed.", file=sys.stderr)
        return None
        
    trades_table = json_data["data"].get("tradesTable", {})
    rows = trades_table.get("rows", [])
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Clean data types
    df['Date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    df['Open'] = df['open'].apply(clean_price)
    df['High'] = df['high'].apply(clean_price)
    df['Low'] = df['low'].apply(clean_price)
    df['Close'] = df['close'].apply(clean_price)
    df['Volume'] = df['volume'].apply(clean_volume)
    
    # Select and order final columns
    df_clean = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
    
    # Sort chronologically (oldest to newest)
    df_clean = df_clean.sort_values(by='Date').reset_index(drop=True)
    
    # Filter the cleaned DataFrame to the user's requested date range
    df_clean = df_clean[(df_clean['Date'] >= start_date) & (df_clean['Date'] <= end_date)].reset_index(drop=True)
    
    return df_clean

def main():
    # Calculate default date range (last 10 years)
    default_end = datetime.now().strftime('%Y-%m-%d')
    default_start = (datetime.now() - timedelta(days=365 * 10)).strftime('%Y-%m-%d')
    
    parser = argparse.ArgumentParser(description="Fetch historical stock price data from Nasdaq.")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker symbol (default: AAPL)")
    parser.add_argument("--start", type=str, default=default_start, help=f"Start date YYYY-MM-DD (default: {default_start})")
    parser.add_argument("--end", type=str, default=default_end, help=f"End date YYYY-MM-DD (default: {default_end})")
    parser.add_argument("--outdir", type=str, default="downloads", help="Output directory (default: downloads)")
    
    args = parser.parse_args()
    
    # Ensure directories exist
    os.makedirs(args.outdir, exist_ok=True)
    
    df = fetch_historical_data(args.ticker, args.start, args.end)
    
    if df is not None and not df.empty:
        output_file = os.path.join(args.outdir, f"{args.ticker.upper()}.csv")
        df.to_csv(output_file, index=False)
        print(f"\nSaved historical data for {args.ticker.upper()} to: {output_file}")
        print("\nDataset Summary:")
        print(f"  Total records: {len(df)}")
        print(f"  Date range:    {df['Date'].min()} to {df['Date'].max()}")
        print(f"  Starting Close: ${df['Close'].iloc[0]:.2f}")
        print(f"  Ending Close:   ${df['Close'].iloc[-1]:.2f}")
        print("\nFirst 5 rows:")
        print(df.head())
        print("\nLast 5 rows:")
        print(df.tail())
    else:
        print("Failed to build dataset.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
