from flask import Flask, render_template, request
import pandas as pd
import os

app = Flask(__name__)

BASE_DIR = os.getcwd()
USERS_PATH = os.path.join(BASE_DIR, "users")

def get_all_users():
    if not os.path.exists(USERS_PATH):
        return []
    return [user for user in os.listdir(USERS_PATH) if os.path.isdir(os.path.join(USERS_PATH, user))]

def get_timestamps_for_user(user):
    return [ts for ts in os.listdir(os.path.join(USERS_PATH, user)) if os.path.isdir(os.path.join(USERS_PATH, user, ts))]

def clean_field(val):
    val = str(val).strip()
    if val.lower() == "nan" or not val:
        return None
    return val

def load_tweets_from_csv(path):
    df = pd.read_csv(path)
    tweets = []
    for _, row in df.iterrows():
        tweets.append({
            'main_text': clean_field(row['main_text']),
            'quoted_texts': [clean_field(q) for q in str(row['quoted_texts']).split(" || ") if clean_field(q)] if pd.notna(row['quoted_texts']) else [],
            'images': [clean_field(img) for img in str(row['images']).split(" || ") if clean_field(img)] if pd.notna(row['images']) else [],
            'videos': [clean_field(vid) for vid in str(row['videos']).split(" || ") if clean_field(vid)] if pd.notna(row['videos']) else [],
            'poster': clean_field(row['poster']),
            'repost_title': clean_field(row['repost_title']),
        })
    return tweets

@app.route("/")
def home():
    user_list = get_all_users()
    return render_template("home.html", users=user_list)

@app.route("/users/<username>")
def user_timestamps(username):
    timestamps = get_timestamps_for_user(username)
    return render_template("timestamps.html", username=username, timestamps=timestamps)

@app.route("/users/<username>/<timestamp>")
def view_tweets(username, timestamp):
    csv_path = os.path.join(BASE_DIR, "users", username, timestamp, "tweets.csv")
    if not os.path.exists(csv_path):
        return f"File not found: {csv_path}", 404
    tweets = load_tweets_from_csv(csv_path)
    return render_template("tweets.html", username=username, timestamp=timestamp, tweets=tweets)

if __name__ == "__main__":
    app.run(debug=True)
