#!/bin/bash

set -e  # Exit on any error
trap 'echo "🛑 Cleaning up..."; kill $FLASK_PID 2>/dev/null || true' EXIT

echo "🔧 Setting up virtual environment..."
python3 -m venv myvenv
source myvenv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

echo "🐦 Fetching tweets..."

#!/bin/bash

HANDLE=""
COUNT=100

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --handle)
      HANDLE="$2"
      shift 2
      ;;
    --count)
      COUNT="$2"
      shift 2
      ;;
    *)
      echo "❌ Unknown argument: $1"
      exit 1
      ;;
  esac
done

# Run tweet scraper
if [[ -n "$HANDLE" ]]; then
  echo "👉 Scraping tweets for @$HANDLE (count=$COUNT)"
  python scrape_and_save_tweets.py --handle "$HANDLE" --count "$COUNT"
else
  echo "📄 No handle provided, using twitter_handles.txt (count=$COUNT)..."
  python scrape_and_save_tweets.py --count "$COUNT"
fi

echo "🌐 Starting Tweets Dashboard..."
python twitter-flask/app.py
