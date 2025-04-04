from flask import Flask, render_template, request
import pandas as pd
import os

app = Flask(__name__)

BASE_DIR = os.getcwd()
USERS_PATH = os.path.join(BASE_DIR, "users")

def get_all_users():
    return [user for user in os.listdir(USERS_PATH) if os.path.isdir(os.path.join(USERS_PATH, user))]

def get_timestamps_for_user(user):
    return [ts for ts in os.listdir(os.path.join(USERS_PATH, user)) if os.path.isdir(os.path.join(USERS_PATH, user, ts))]

def load_tweets_from_csv(path):
    df = pd.read_csv(path)
    tweets = []
    for _, row in df.iterrows():
        tweets.append({
            'main_text': row['main_text'],
            'quoted_texts': row['quoted_texts'].split(" || ") if pd.notna(row['quoted_texts']) else [],
            'images': row['images'].split(" || ") if pd.notna(row['images']) else []
        })
    return tweets

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/users")
def users():
    user_list = get_all_users()
    print(user_list)
    return render_template("users.html", users=user_list)

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
