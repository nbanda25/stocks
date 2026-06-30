#!/usr/bin/env python3
"""
Nasdaq-100 Historical Stock Price Dataset Builder
Fetches historical stock price data for all Nasdaq-100 constituents,
merges them into a single unified CSV file, and cleans up individual files.
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Fallback Nasdaq-100 constituent list in case the Wikipedia scrap fails
FALLBACK_TICKERS = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'AVGO', 'PEP',
    'COST', 'CSCO', 'ADBE', 'AMD', 'NFLX', 'CMCSA', 'TMUS', 'AMGN', 'QCOM', 'INTC',
    'INTU', 'PANW', 'ISRG', 'AMAT', 'BKNG', 'HON', 'MU', 'LRCX', 'VRTX', 'REGN',
    'ADP', 'MDLZ', 'ADI', 'KLAC', 'GILD', 'PDD', 'SNPS', 'MELI', 'CDNS', 'WDAY',
    'NXPI', 'MAR', 'ORLY', 'CTAS', 'ROP', 'CEG', 'MNST', 'FTNT', 'CRWD', 'MCHP',
    'ADSK', 'DXCM', 'CPRT', 'KDP', 'KHC', 'FAST', 'CSX', 'PCAR', 'LITE', 'PAYX',
    'IDXX', 'MARA', 'GEHC', 'EXC', 'ODFL', 'FANG', 'XEL', 'TEAM', 'BKR', 'DDOG',
    'ANSS', 'EA', 'DLTR', 'WBD', 'ILMN', 'ALGN', 'WMT', 'PLTR', 'ARM', 'ASML',
    'ABNB', 'APP', 'AXON', 'CCEP', 'DASH', 'FER', 'MSTR', 'RKLB', 'SHOP', 'SBUX',
    'TTWO', 'TER', 'TXN', 'TRI', 'WDC', 'ALNY', 'ALAB', 'CRWV', 'MPWR', 'NBIS'
]

def get_nasdaq100_tickers():
    """Fetch the list of Nasdaq-100 constituents from Wikipedia, falling back to a hardcoded list if needed."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("Fetching Nasdaq-100 constituent list from Wikipedia...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            wikitables = soup.find_all('table', class_='wikitable')
            
            # Find the constituents table (usually index 4, let's verify headers)
            constituents_table = None
            for table in wikitables:
                headers_list = [th.text.strip().lower() for th in table.find_all('th')]
                if 'ticker' in headers_list or 'symbol' in headers_list:
                    constituents_table = table
                    break
            
            if constituents_table:
                tickers = []
                for row in constituents_table.find_all('tr')[1:]:
                    cols = row.find_all(['td', 'th'])
                    if cols:
                        ticker = cols[0].text.strip()
                        # Clean up ticker formatting
                        ticker = ticker.split('[')[0].strip().replace('.', '-')
                        tickers.append(ticker)
                
                # Filter out empty or header rows and ensure uniqueness
                tickers = list(dict.fromkeys([t for t in tickers if t]))
                if len(tickers) >= 90:
                    print(f"Successfully scraped {len(tickers)} tickers from Wikipedia.")
                    return tickers
            
            print("Could not locate the constituents table on Wikipedia.")
        else:
            print(f"Failed to fetch Wikipedia page. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching Nasdaq-100 constituents: {e}")
        
    print("Using hardcoded fallback list of Nasdaq-100 tickers.")
    return FALLBACK_TICKERS

def clean_price(val):
    if pd.isna(val) or not isinstance(val, str):
        return val
    val_clean = val.replace('$', '').replace(',', '').strip()
    try:
        return float(val_clean)
    except ValueError:
        return None

def clean_volume(val):
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    val_clean = val.replace(',', '').strip()
    try:
        return int(val_clean)
    except ValueError:
        return 0

def fetch_ticker_data(ticker, start_date, end_date):
    """Fetch historical data for a ticker with robust parameter fallbacks to avoid API bugs."""
    url = f"https://api.nasdaq.com/api/quote/{ticker.upper()}/historical"
    headers = {
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "origin": "https://www.nasdaq.com",
        "referer": "https://www.nasdaq.com/",
        "accept-language": "en-US,en;q=0.9",
    }
    
    attempts = [
        {"from": start_date, "to": end_date},
        {"from": start_date, "to": "2030-12-31"},  # far-future bypass
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
        
    for offset in [-1, -2, -3, 1, 2, 3]:
        try:
            from_dt = datetime.strptime(start_date, "%Y-%m-%d")
            shifted_from = (from_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            attempts.append({"from": shifted_from, "to": "2030-12-31"})
            attempts.append({"from": shifted_from, "to": end_date})
        except ValueError:
            pass
            
    seen = set()
    unique_attempts = []
    for att in attempts:
        key = (att["from"], att["to"])
        if key not in seen:
            seen.add(key)
            unique_attempts.append(att)
            
    for idx, att in enumerate(unique_attempts):
        from_d = att["from"]
        to_d = att["to"]
        params = {
            "assetclass": "stocks",
            "fromdate": from_d,
            "todate": to_d,
            "limit": "9999"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("data") is not None:
                    trades_table = res_json["data"].get("tradesTable", {})
                    rows = trades_table.get("rows", [])
                    if rows:
                        df = pd.DataFrame(rows)
                        df['Date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                        df['Open'] = df['open'].apply(clean_price)
                        df['High'] = df['high'].apply(clean_price)
                        df['Low'] = df['low'].apply(clean_price)
                        df['Close'] = df['close'].apply(clean_price)
                        df['Volume'] = df['volume'].apply(clean_volume)
                        
                        df_clean = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
                        df_clean = df_clean.sort_values(by='Date').reset_index(drop=True)
                        
                        # Filter to user requested range
                        df_clean = df_clean[(df_clean['Date'] >= start_date) & (df_clean['Date'] <= end_date)].reset_index(drop=True)
                        if not df_clean.empty:
                            df_clean.insert(0, 'Ticker', ticker.upper())
                            return df_clean
        except Exception:
            pass
            
    return None

def main():
    # Configure directories
    outdir = "downloads"
    os.makedirs(outdir, exist_ok=True)
    
    # Target file paths
    final_csv = os.path.join(outdir, "nasdaq100_historical.csv")
    aapl_csv = os.path.join(outdir, "AAPL.csv")
    
    # Get constituents
    tickers = get_nasdaq100_tickers()
    
    # Standardize dates: 10 years ago to today
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365 * 10)).strftime('%Y-%m-%d')
    
    print(f"\nPreparing to fetch 10 years of historical data for {len(tickers)} tickers...")
    print(f"Date Range: {start_date} to {end_date}")
    print("This will execute sequentially with a polite delay to prevent rate limits.")
    
    all_dfs = []
    failed_tickers = []
    
    start_time = time.time()
    
    for idx, ticker in enumerate(tickers):
        print(f"[{idx+1}/{len(tickers)}] Fetching {ticker}...", end="", flush=True)
        
        # 3 retries per ticker just in case of temporary network glitches
        df = None
        for r in range(3):
            df = fetch_ticker_data(ticker, start_date, end_date)
            if df is not None:
                break
            time.sleep(1)
            
        if df is not None:
            all_dfs.append(df)
            print(f" Success! ({len(df)} rows)")
        else:
            failed_tickers.append(ticker)
            print(" Failed!")
            
        # Polite delay to prevent rate limit (1.0 seconds)
        time.sleep(1.0)
        
    duration = time.time() - start_time
    print(f"\nFetch complete in {duration/60:.2f} minutes.")
    
    if all_dfs:
        print("Merging datasets...")
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # Save to final CSV
        combined_df.to_csv(final_csv, index=False)
        print(f"Saved unified dataset to: {final_csv}")
        print(f"Total Rows: {len(combined_df)}")
        print(f"Tickers Saved: {len(all_dfs)}")
    else:
        print("Error: No data was successfully fetched.", file=sys.stderr)
        sys.exit(1)
        
    if failed_tickers:
        print(f"The following tickers failed to fetch: {failed_tickers}")
        
    # Delete individual AAPL CSV if it exists (but its data is now in the unified CSV)
    if os.path.exists(aapl_csv):
        try:
            os.remove(aapl_csv)
            print(f"Deleted individual file: {aapl_csv}")
        except Exception as e:
            print(f"Warning: Could not delete {aapl_csv}: {e}", file=sys.stderr)
            
    print("\nDataset generation completed successfully!")

if __name__ == "__main__":
    main()
