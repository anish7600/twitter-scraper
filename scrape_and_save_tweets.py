from playwright.sync_api import sync_playwright
from datetime import datetime
from bs4 import BeautifulSoup
import browser_cookie3
import os
import csv

TARGET_TWEET_COUNT = 5

def get_chrome_cookies(domain=".x.com"):
    cj = browser_cookie3.chrome(domain_name=domain)
    cookies = []
    for cookie in cj:
        cookies.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": cookie.expires or -1,
            "httpOnly": cookie._rest.get("HttpOnly", False),
            "secure": bool(cookie.secure),
            "sameSite": "Lax"
        })
    return cookies


def extract_tweets_with_images(html):
    soup = BeautifulSoup(html, "html.parser")
    tweets_data = []

    for article in soup.find_all("article"):
        tweet_text_blocks = []

        for div in article.find_all("div", {"data-testid": "tweetText"}):
            text = div.get_text(separator=" ", strip=True)
            if not text:
                text = " "  # Assume emoji-only
            tweet_text_blocks.append(text)

        if not tweet_text_blocks:
            continue

        main_text = tweet_text_blocks[0]
        quoted_texts = tweet_text_blocks[1:] if len(tweet_text_blocks) > 1 else []

        image_links = []
        for img in article.find_all("img"):
            src = img.get("src", "")
            if "profile_images" not in src and "emoji" not in src:
                image_links.append(src)

        tweet_data = {
            "main_text": main_text,
            "quoted_texts": quoted_texts,
            "images": image_links
        }

        tweets_data.append(tweet_data)

    return tweets_data


def scrape_authenticated_tweets(username, target_count):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        cookies = get_chrome_cookies()
        context.add_cookies(cookies)

        page = context.new_page()
        url = f"https://x.com/{username}"
        print(f"➡️ Opening {url}")
        page.goto(url)
        page.wait_for_timeout(3000)

        all_tweets = []
        seen_texts = set()
        scroll_attempts = 0

        while len(all_tweets) < target_count:
            # Scroll a bit before grabbing new content
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)

            html = page.content()
            new_tweets = extract_tweets_with_images(html)

            for tweet in new_tweets:
                if tweet["main_text"] in seen_texts:
                    continue
                all_tweets.append(tweet)
                seen_texts.add(tweet["main_text"])
                print(f"✅ Collected tweet #{len(all_tweets)}: {tweet['main_text'][:60]}...")
                if len(all_tweets) >= target_count:
                    break

            scroll_attempts += 1
            if scroll_attempts > 30:
                print("⛔ Max scroll attempts reached.")
                break

        browser.close()
        return all_tweets


def save_tweets_to_csv(path, tweets, filename="tweets.csv"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(filename, mode="a", newline='', encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["main_text", "quoted_texts", "images"])
        writer.writeheader()
        for tweet in tweets:
            writer.writerow({
                "main_text": tweet["main_text"],
                "quoted_texts": " || ".join(tweet.get("quoted_texts", [])),
                "images": " || ".join(tweet.get("images", []))
            })


def display_tweets_from_csv(filename="tweets.csv"):
    with open(filename, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for i, row in enumerate(reader, 1):
            print(f"\n{i}. 📝 Tweet #{i}")
            print(f"Main: {row['main_text']}")

            quoted = row["quoted_text"].strip()
            if quoted:
                for j, q in enumerate(quoted.split(" || "), 1):
                    print(f"\n🔁 Quoted/Repost #{j}: {q}")

            images = row["images"].strip()
            if images:
                for img in images.split(" || "):
                    print(f"\n📸 {img}")


def read_usernames(filename="twitter_handles.txt"):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    usernames = read_usernames()
    for username in usernames:
        print(f"🔍 Scraping tweets for: {username}")
        tweets = scrape_authenticated_tweets(username, target_count=TARGET_TWEET_COUNT)

        # for i, tweet in enumerate(tweets, 1):
        #     print(f"\n{i}. 📝 Tweet #{i}")
        #     print(f"Main: {tweet['main_text']}")

        #     for j, quoted in enumerate(tweet.get("quoted_texts", []), 1):
        #         print(f"\n🔁 Quoted/Repost #{j}: {quoted}")

        #     for img in tweet["images"]:
        #         print(f"\n📸 {img}")        

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_path = os.path.join("users", username, timestamp, "tweets.csv")
        save_tweets_to_csv(save_path, tweets, save_path)
        print(f"✅ Saved to {save_path}")
