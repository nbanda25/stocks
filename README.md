# Nasdaq Historical Stock Price Dataset Builder

A robust, configurable Python utility to fetch historical stock price data (OHLCV) directly from the Nasdaq quotes API and export it to a cleaned, standardized CSV dataset.

## 📋 Features

- **Robust Date Handling**: Mitigates undocumented quirks in Nasdaq's API (e.g., internal errors when starting queries on weekends or requesting the active trading day) by using an automatic fallback and parameter retry mechanism.
- **Data Normalization**: Cleans currency symbols (`$`), parses volume commas, and converts columns to standard numeric/datetime formats.
- **Chronological Sorting**: Sorts historical records from oldest to newest.
- **Configurable Ticker & Date Range**: Allows fetching any ticker and custom date ranges using CLI parameters.

---

## 🛠️ Setup & Installation

1. **Install Dependencies**:
   Make sure you have Python 3 and the required libraries installed:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🚀 Usage

The main scraper script is located in `cod/fetch_nasdaq.py`.

### 1. Download Apple (AAPL) Data
By default, running the script without arguments fetches the last 10 years of historical data for **AAPL** and saves it to the `downloads/` directory:
```bash
python3 cod/fetch_nasdaq.py
```

### 2. Download Data for Another Ticker & Custom Date Range
To download a specific ticker and date range (e.g., Microsoft `MSFT` from `2020-01-01` to `2025-12-31`):
```bash
python3 cod/fetch_nasdaq.py --ticker MSFT --start 2020-01-01 --end 2025-12-31
```

### Options
- `--ticker`: The stock ticker symbol (default: `AAPL`).
- `--start`: The start date in `YYYY-MM-DD` format (default: 10 years ago).
- `--end`: The end date in `YYYY-MM-DD` format (default: today's date).
- `--outdir`: The directory to save the output CSV (default: `downloads`).

---

## 📂 Project Structure

```
.
├── cod/
│   └── fetch_nasdaq.py   # Core scraping and data cleaning logic
├── downloads/
│   └── AAPL.csv          # Generated historical stock price dataset
├── requirements.txt      # Project requirements
└── README.md             # Project documentation
```

---

## ⚙️ How It Works: Handling Nasdaq API Quirks

Nasdaq's internal API (`api.nasdaq.com`) is known for throwing `1000: Something went wrong` errors under several conditions:
1. When the `fromdate` falls exactly on a weekend or holiday.
2. When the `todate` refers to the active trading day or a very recent date that has not yet been processed in the historical index database.

To address these quirks:
- **Fallback Strategies**: If an API request fails, the script automatically attempts alternative date parameters, such as shifting the start date to the preceding weekday, or using a far-future `todate` (e.g. `2030-12-31`) to bypass current-day processing conflicts.
- **Client-Side Filtering**: Since these shifts might fetch dates outside the requested window, the script automatically filters the final pandas DataFrame back to the exact `start_date` and `end_date` requested by the user before writing the CSV.
