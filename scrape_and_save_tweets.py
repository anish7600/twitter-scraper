from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import browser_cookie3
import os
import csv
import re
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Constants
TARGET_TWEET_COUNT = 100
CHROME_EXECUTABLE_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

def get_chrome_cookies(domain=".x.com"):
    """Retrieve cookies from Chrome for the specified domain."""
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

def extract_tweets_with_videos(html, intercepted_videos):
    """Parse the HTML to extract tweets and associate them with their videos."""
    soup = BeautifulSoup(html, "html.parser")
    tweets_data = []

    for article in soup.find_all("article"):
        tweet_text_blocks = [div.get_text(separator=" ", strip=True)
                             for div in article.find_all("div", {"data-testid": "tweetText"})]
        if not tweet_text_blocks:
            continue

        main_text = tweet_text_blocks[0]
        quoted_texts = tweet_text_blocks[1:] if len(tweet_text_blocks) > 1 else []

        poster = ''
        repost_title = ''

        social_context = soup.find('span', {'data-testid': 'socialContext'})
        if social_context:
            inner_span = social_context.find('span')
            poster = inner_span.find('span').text if inner_span and inner_span.find('span') else None
            user_names = article.find_all('div', {'data-testid': 'User-Name'})
            repost_title = user_names[0].text if user_names else ""
        else:
            user_names = article.find_all('div', {'data-testid': 'User-Name'})
            poster = user_names[0].text if user_names else ""

        image_links = []
        video_links = []

        for img in article.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue
            if "profile_images" in src or "emoji" in src:
                continue

            match = re.search(r"ext_tw_video_thumb/(\d+)/", src)
            if match:
                video_id = match.group(1)
                for video_url in intercepted_videos:
                    if video_id in video_url:
                        video_links.append(video_url)
                        break
                continue

            image_links.append(src)

        tweets_data.append({
            "main_text": main_text,
            "quoted_texts": quoted_texts,
            "images": image_links,
            "videos": video_links,
            "poster": poster,
            "repost_title": repost_title
        })

    return tweets_data

def scrape_authenticated_tweets(username, target_count):
    """Scrape tweets from a user's profile, intercepting video streams."""
    intercepted_videos = []

    def intercept_videos(route, request):
        if "video.twimg.com" in request.url and ".m3u8" in request.url:
            intercepted_videos.append(request.url)
        route.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=CHROME_EXECUTABLE_PATH)
        context = browser.new_context()
        context.add_cookies(get_chrome_cookies())

        page = context.new_page()
        page.route("**/*", intercept_videos)

        url = f"https://x.com/{username}"
        print(f"➡️ Opening {url}")
        page.goto(url)
        page.wait_for_timeout(3000)

        all_tweets = []
        seen_texts = set()
        scroll_attempts = 0

        while len(all_tweets) < target_count:
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)

            html = page.content()
            new_tweets = extract_tweets_with_videos(html, intercepted_videos)

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

def save_tweets_to_csv(path, tweets):
    """Save the extracted tweets to a CSV file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode="w", newline='', encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["main_text", "quoted_texts", "poster", "repost_title", "images", "videos"])
        writer.writeheader()
        for tweet in tweets:
            writer.writerow({
                "main_text": tweet["main_text"],
                "quoted_texts": " || ".join(tweet.get("quoted_texts", [])),
                "poster": tweet["poster"],
                "repost_title": tweet["repost_title"],
                "images": " || ".join(tweet.get("images", [])),
                "videos": " || ".join(tweet.get("videos", []))
            })

def read_usernames(filename="twitter_handles.txt"):
    """Read Twitter usernames from a file."""
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

def scrape_user(username):
    """Wrapper function to scrape and save tweets for a single user."""
    try:
        print(f"🔍 Scraping tweets for: {username}")
        tweets = scrape_authenticated_tweets(username, target_count=TARGET_TWEET_COUNT)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_path = os.path.join("users", username, timestamp, "tweets.csv")
        save_tweets_to_csv(save_path, tweets)
        print(f"✅ Saved to {save_path}")
        return username
    except Exception as e:
        print(f"❌ Error scraping {username}: {e}")
        return None

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")  # Safe on macOS

    usernames = read_usernames()
    max_workers = min(4, len(usernames))  # Adjust based on CPU and rate limits

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scrape_user, username) for username in usernames]
        for future in as_completed(futures):
            result = future.result()
            if result:
                print(f"✅ Finished scraping for: {result}")
