from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import browser_cookie3
import os
import csv
import re
import argparse
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Constants
TWEET_COUNT = 100
CHROME_EXECUTABLE_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

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


def parse_tweets(html, handle):
    soup = BeautifulSoup(html, "html.parser")
    tweets_data = []

    for article in soup.find_all("article"):
        tweet = {}
        tweet_items = {}
        tweet['main_text'] = ''
        tweet['quoted_texts'] = []

        # Extract tweet texts
        tweet_text_divs = article.find_all("div", {"data-testid": "tweetText"})
        tweet_text_blocks = [
            "\n".join([span.get_text(" ", strip=True) for span in div.find_all("span")])
            for div in tweet_text_divs
        ]

        if not tweet_text_blocks:
            continue

        username_blocks = [
            div.get_text(separator=" ", strip=True)
            for div in article.find_all("div", {"data-testid": "User-Name"})
        ]

        tweet["poster"] = username_blocks[0]

        for idx, tweet_text in enumerate(tweet_text_blocks):
            tweet_items[username_blocks[idx]] = tweet_text

        for username, tweet_text in tweet_items.items():
            if handle in username:
                tweet["main_text"] = tweet_text
            else:
                tweet["quoted_texts"].append(tweet_text)

        # Extract repost title
        tweet["repost_title"] = extract_user_info(article)

        # Extract images and videos (video extraction needs intercepted_videos input)
        tweet["images"], tweet["alt_texts"], tweet["video_ids"] = parse_images(article)

        tweets_data.append((article, tweet))  # Keep article for video resolution

    return tweets_data


def extract_user_info(article):
    user_name_divs = article.find_all('div', {'data-testid': 'User-Name'})
    social_context = article.find('span', {'data-testid': 'socialContext'})

    repost_title = ''

    if not social_context:
        if len(user_name_divs) > 1:
            repost_title = user_name_divs[1].get_text(strip=True)
            repost_title = repost_title[:repost_title.find('@')] if '@' in repost_title else repost_title

    return repost_title


def parse_images(article):
    image_links = []
    alt_texts = []
    video_ids = []

    for img in article.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue
        if "profile_images" in src or "emoji" in src:
            continue

        # Check if it's a video thumbnail
        match = re.search(r"ext_tw_video_thumb/(\d+)/", src)
        if match:
            video_ids.append(match.group(1))
            continue

        image_links.append(src)

        alt = img.get("alt", "")
        if alt and alt != "Image":
            alt_texts.append(alt)

    return image_links, alt_texts, video_ids


def resolve_videos(tweets_data, intercepted_videos):
    final_tweets = []
    for article, tweet in tweets_data:
        video_links = []
        for video_id in tweet.get("video_ids", []):
            for video_url in intercepted_videos:
                if video_id in video_url:
                    video_links.append(video_url)
                    break
        tweet["videos"] = video_links
        tweet.pop("video_ids", None)
        final_tweets.append(tweet)
    return final_tweets


def extract_tweets_with_videos(html, handle, intercepted_videos):
    tweets_with_articles = parse_tweets(html, handle)
    tweets_resolved = resolve_videos(tweets_with_articles, intercepted_videos)
    return tweets_resolved


def scrape_authenticated_tweets(handle, tweet_count):
    intercepted_videos = []

    def intercept_videos(route, request):
        if "video.twimg.com" in request.url and ".m3u8" in request.url:
            intercepted_videos.append(request.url)
        route.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=CHROME_EXECUTABLE_PATH)
        context = browser.new_context()
        context.add_cookies(get_chrome_cookies(".x.com"))

        page = context.new_page()
        page.route("**/*", intercept_videos)

        url = f"https://x.com/{handle}"
        print(f"➡️ Opening {url}")
        page.goto(url)
        page.wait_for_timeout(3000)

        all_tweets = []
        seen_texts = set()
        scroll_attempts = 0

        while len(all_tweets) < tweet_count:
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)

            html = page.content()
            new_tweets = extract_tweets_with_videos(html, handle, intercepted_videos)

            for tweet in new_tweets:
                if tweet["main_text"] in seen_texts:
                    continue
                all_tweets.append(tweet)
                seen_texts.add(tweet["main_text"])
                print(f"✅ Collected tweet #{len(all_tweets)}: {tweet['main_text'][:60]}...")
                if len(all_tweets) >= tweet_count:
                    break

            scroll_attempts += 1
            if scroll_attempts > 30:
                print("⛔ Max scroll attempts reached.")
                break

        browser.close()
        return all_tweets

def save_tweets_to_csv(path, tweets):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode="w", newline='', encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["main_text", "quoted_texts", "poster", "repost_title", "images", "videos", "alt_texts"]
        )
        writer.writeheader()
        for tweet in tweets:
            writer.writerow({
                "main_text": tweet["main_text"],
                "quoted_texts": " || ".join(tweet.get("quoted_texts", [])),
                "poster": tweet["poster"],
                "repost_title": tweet["repost_title"],
                "images": " || ".join(tweet.get("images", [])),
                "videos": " || ".join(tweet.get("videos", [])),
                "alt_texts": " || ".join(tweet.get("alt_texts", [])),
            })

def read_handles(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

def scrape_handle(handle):
    try:
        print(f"🔍 Scraping tweets for: {handle}")
        tweets = scrape_authenticated_tweets(handle, TWEET_COUNT)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_handle = re.sub(r'[^a-zA-Z0-9_]', '_', handle)
        save_path = os.path.join("users", safe_handle, timestamp, "tweets.csv")
        save_tweets_to_csv(save_path, tweets)
        print(f"✅ Saved to {save_path}")
        return handle
    except Exception as e:
        print(f"❌ Error scraping {handle}: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Twitter handles.")
    parser.add_argument("filename", nargs="?", default="twitter_handles.txt", help="File containing Twitter handles")
    parser.add_argument("--handle", help="Scrape a single Twitter handle instead of a file")
    parser.add_argument("--chrome-path", help="Path to Chrome executable", default=CHROME_EXECUTABLE_PATH)
    args = parser.parse_args()

    if args.handle:
        twitter_handles = [args.handle]
    else:
        twitter_handles = read_handles(args.filename)

    multiprocessing.set_start_method("spawn")

    max_workers = min(4, len(twitter_handles))

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scrape_handle, handle) for handle in twitter_handles]
        for future in as_completed(futures):
            result = future.result()
            if result:
                print(f"✅ Finished scraping for: {result}")
