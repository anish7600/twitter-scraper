### Setup

- python -m venv myvenv
- source myvenv/bin/activate
- pip install -r requirements.txt

### Fetch Tweets

- python scrape_and_save_tweets.py -h
- python scrape_and_save_tweets.py (Loads twitter_handles from twitter_handles.txt)
- python scrape_and_save_tweets.py [--handle [twitter_handle_without_'@']]

> **Note:** This script uses your existing Chrome login session, so make sure you're already logged into Twitter/X in Chrome before running the script.

### Tweets Dashboard

- python twitter-flask/app.py 
