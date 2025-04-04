from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

def load_tweets(file_path="tweets.csv"):
    df = pd.read_csv(file_path)
    tweets = []
    for _, row in df.iterrows():
        tweets.append({
            'main_text': row['main_text'],
            'quoted_texts': row['quoted_texts'].split(" || ") if pd.notna(row['quoted_texts']) else [],
            'images': row['images'].split(" || ") if pd.notna(row['images']) else []
        })
    return tweets

@app.route("/")
def index():
    tweets = load_tweets()
    return render_template("index.html", tweets=tweets)

if __name__ == "__main__":
    app.run(debug=True)

