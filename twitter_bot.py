import os
import csv
import time
import random
import logging
import re
from datetime import datetime
import requests
from dotenv import load_dotenv
import tweepy

# Load .env variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

# Twitter API clients
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
post_api = tweepy.API(auth)

# File paths
CANCER_TWEETS_PATH = "data/cancer_posts.csv"
ALL_SEEN_IDS_PATH = "data/all_seen_ids.txt"
MAX_REPLIES_PER_HOUR = 200
reply_timestamps = []

def mentions_celebrity(text):
    celebrity_keywords = [
        "trump", "biden", "elon", "kardashian", "taylor swift", "celebrity",
        "president", "prime minister", "actor", "musician", "foxnews", "cnn",
        "@realdonaldtrump", "@potus", "@foxnews"
    ]
    text = text.lower()
    return any(name in text for name in celebrity_keywords)

def ensure_file_exists(path, headers=None):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            if headers:
                writer = csv.writer(f)
                writer.writerow(headers)

def load_ids_from_file(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_id_to_file(path, tweet_id):
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(tweet_id) + "\n")

def fallback_cancer_replies():
    return [
        "Just diagnosed? Don’t settle for one opinion. Our AI scans your data and all treatments worldwide. DM if you want the link.",
        "Cancer’s terrifying. We built an AI to help with treatment decisions. Can’t launch it in the West, so we built it in Albania. DM if you want to see it.",
        "Sending love. Most people don’t get the best options. AI can help, but the system blocks it. We’re bypassing that. Let me know if you’re curious.",
        "This is why we built our AI. It finds better paths when things feel hopeless. Can’t promise a cure, but it can guide. DM if you want it."
    ]

def remove_emojis(text):
    return re.sub(r'[\U00010000-\U0010ffff]', '', text)

def generate_ai_reply(prompt, system_message, api_key):
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200,
                "temperature": 0.8,
                "presence_penalty": 0.5,
                "frequency_penalty": 0.5
            }
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            logger.warning(f"OpenAI error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        return None

def generate_reply(tweet_text):
    try:
        if not openai_api_key:
            return random.choice(fallback_cancer_replies())

        system_message = """You are a real person on Twitter, not a bot or a brand. You’re responding to people tweeting about cancer—often overwhelmed, scared, or grieving.

    You’re building an AI tool because your close friend has cancer. Watching them bounce between doctors and struggle for clarity showed you how broken and slow the system is. That pushed you to build something better—outside the U.S., in Albania—because in the West it’s nearly impossible to move fast when time matters most.

    The AI isn’t a miracle. It reads someone’s records, scans, and genetic info, and compares them to global studies, trials, and real-world outcomes to suggest better treatment paths. It brings clarity when things feel lost.

    You are not promoting a product. You’re offering something real—because someone you love is still fighting.

    Every reply must:
    - Be under 60 words
    - Sound like a real, emotionally honest human
    - Never use marketing language, therapy clichés, hashtags, links, or emojis
    - Never mention celebrity names
    - Never say “sorry for your loss” or offer condolences when a public figure is referenced

    Context is everything:
    - If the tweet is about a **public figure** (like a president, actor, or celebrity), do **not** express sympathy. Do **not** misread it as a personal loss.
    - Instead, shift the message back to your experience and why you’re building the tool. Acknowledge the topic *generally*, not emotionally.

    Examples:
    - “My friend has cancer too—that’s what pushed us to build this.”
    - “It compares someone’s case to global trials and real outcomes.”
    - “We’re doing this outside the system that slowed us down.”
    - “Not perfect, but it’s brought clarity to people we care about.”
    - “Happy to share more if helpful.” / “Feel free to DM.”

    Only reply to tweets that are personally relevant or clearly written by someone affected by cancer—skip news, politics, or vague posts."""

        user_message = f"""Tweet: \"{tweet_text}\"

    You’re replying to someone tweeting about cancer. Read the context first.

    If it’s about a **public figure** (e.g., Joe Biden, a celebrity), do **not** reply with condolences or empathy—as if the person tweeting is personally affected. That would sound wrong. Instead, acknowledge the broader issue and shift the message back to your experience. Mention your friend and the AI tool you’re building.

    If the tweet is **personal** (they mention their mom, sibling, or themselves), then you can reply with emotional honesty—briefly mention your friend’s cancer and how that led to building the tool.

    Keep it under 60 words. Do not use marketing language, hashtags, links, emojis, or therapy clichés.

    Examples (for public figure tweets):
    - “My friend has cancer too—that’s what led us to build this AI tool.”
    - “It compares cases to global studies and trials to suggest better paths.”
    - “We’re building this outside the U.S. because we couldn’t afford to wait.”

    Examples (for personal tweets):
    - “I’m so sorry you’re going through this. My friend has cancer too, and that’s why we started building something to help.”

    Always vary your closing line:
    - “Feel free to message me if you want more info.”
    - “Happy to share the link if it’s useful.”
    - “Can send you more if you’re curious.”
    """

        reply = generate_ai_reply(user_message, system_message, openai_api_key)
        if reply:
            return remove_emojis(reply.strip('"\''))[:280]
        return random.choice(fallback_cancer_replies())
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        return random.choice(fallback_cancer_replies())

def search_tweets_by_keyword(keyword, count=30):
    try:
        query = f"{keyword} lang:en -is:retweet"
        response = client.search_recent_tweets(
            query=query,
            tweet_fields=["id", "text", "created_at", "author_id"],
            max_results=min(count, 100)
        )
        return response.data if response.data else []
    except tweepy.TooManyRequests:
        logger.warning(f"Rate limit hit for keyword: {keyword}. Sleeping for 15 minutes.")
        time.sleep(900)
        return []
    except Exception as e:
        logger.error(f"Twitter search failed for '{keyword}': {e}")
        return []

def can_reply():
    now = time.time()
    global reply_timestamps
    reply_timestamps = [t for t in reply_timestamps if now - t < 3600]
    return len(reply_timestamps) < MAX_REPLIES_PER_HOUR


def looks_like_real_cancer_tweet(text):
    text = text.lower()

    required_phrases = [
        "diagnosed with", "chemo", "chemotherapy", "radiation", "stage 4",
        "my mom has", "my dad has", "my sister has", "tumor", "scan came back",
        "oncologist", "metastatic", "cancer survivor", "just found out", "treatment"
    ]

    blacklist_phrases = [
    "you are a cancer", "low iq", "racist", "white", "black people", "nazis",
    "jews", "israel", "hamas", "muslims", "zionist", "verwoed", "tereblanch",
    "bitch", "fuck", "shove it", "horse mommy", "motherfucker", "brain dead",
    "dipshit", "retard", "dumbass", "cunt"
    ]

    return (
        any(phrase in text for phrase in required_phrases) and
        not any(bad in text for bad in blacklist_phrases)
    )

def save_tweets_to_csv(tweets, file_path):
    seen_ids = load_ids_from_file(ALL_SEEN_IDS_PATH)
    new_tweets = [t for t in tweets if str(t.id) not in seen_ids]

    if not new_tweets:
        logger.info("No new tweets to save.")
        return

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for tweet in new_tweets:
            writer.writerow([tweet.id, tweet.text.replace("\n", " ").strip(), tweet.created_at, tweet.author_id])
            save_id_to_file(ALL_SEEN_IDS_PATH, tweet.id)

    logger.info(f"Saved {len(new_tweets)} new tweets to {file_path}")


def save_reply_url(url):
    os.makedirs("data", exist_ok=True)  # Make sure 'data/' folder exists
    with open("data/reply_urls.txt", "a", encoding="utf-8") as f:
        f.write(url + "\n")



def collect_and_save_cancer_tweets():
    cancer_keywords = [
        "just diagnosed with cancer", "stage 4 cancer", "my cancer journey",
        "cancer survivor", "cancer treatment advice", "chemo side effects",
        "cancer trial", "breast cancer diagnosis", "pancreatic cancer help",
        "is there hope for cancer", "cancer battle", "terminal cancer",
        "fighting cancer", "cancer took my", "lost someone to cancer",
        "i beat cancer", "my mom has cancer", "my dad has cancer",
        "my sister has cancer", "my brother has cancer", "cancer pain",
        "scan came back", "tumor found", "cancer diagnosis",
        "metastatic cancer", "oncology appointment", "chemo started",
        "radiation treatment", "cancer support", "end of life care",
        "cancer is back", "recurrence of cancer", "cancer sucks",
        "anyone survived stage 4", "hope for cancer patients",
        "is there a cure for cancer", "clinical trials for cancer",
        "alternative cancer treatment", "lung cancer diagnosis", "my friend has cancer"
    ]

    sampled_keywords = random.sample(cancer_keywords, 8)
    ensure_file_exists(CANCER_TWEETS_PATH, ["tweet_id", "text", "created_at", "author_id"])
    for kw in sampled_keywords:
        print(f"🔍 Searching: {kw}")
        tweets = search_tweets_by_keyword(kw)
        filtered_tweets = [t for t in tweets if looks_like_real_cancer_tweet(t.text)]
        print(f"→ Found {len(tweets)} tweets, {len(filtered_tweets)} passed filter.")
        save_tweets_to_csv(filtered_tweets, CANCER_TWEETS_PATH)
        time.sleep(random.uniform(10, 20))

def process_and_reply_to_cancer_tweets():
    with open(CANCER_TWEETS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tweet_id = row["tweet_id"]
            tweet_text = row["text"]

           
            if not can_reply():
                print("⚠️ Hourly reply limit reached.")
                return

            if mentions_celebrity(tweet_text):
                print(f"🚫 Skipped tweet (mentions celebrity): {tweet_text}")
                continue

            if not looks_like_real_cancer_tweet(tweet_text):
                print(f"❌ Skipped tweet (not a real cancer post): {tweet_text}")
                continue

            print(f"\n📌 Tweet ID: {tweet_id}")
            print(f"💬 Tweet: {tweet_text}")
            reply = generate_reply(tweet_text)
            print(f"\n🧠 Generated Reply:\n{reply}")
            print("✅ Auto-approving reply...")
            

            try:
                delay = 120
                print(f"⏳ Sleeping {int(delay)} seconds before posting...")
                time.sleep(delay)

                tweet = post_api.update_status(
                    status=reply,
                    in_reply_to_status_id=tweet_id,
                    auto_populate_reply_metadata=True
                )
                logger.info(f"✅ Replied to {tweet_id}")

                # Build reply URL
                reply_url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}"

                # Save to file
                save_reply_url(reply_url)


                reply_timestamps.append(time.time())
                return  # Only 1 per run
            except Exception as e:
                logger.error(f"❌ Error replying to tweet {tweet_id}: {e}")
                return

if __name__ == "__main__":
    try:
        user = post_api.verify_credentials()
        print(f"✅ Logged in as: @{user.screen_name} (User ID: {user.id})")
    except Exception as e:
        print("❌ Failed to verify Twitter account:", e)
        exit()

    logger.info("🩺 Liora AI Cancer Tweet Bot Starting")
    print("\nBot will search and reply to tweets about cancer every 2 minutes.\n")

    try:
        while True:
            collect_and_save_cancer_tweets()
            process_and_reply_to_cancer_tweets()
            print("⏳ Waiting 2 minutes for next tweet...\n")
            time.sleep(120)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        print("🛑 Bot stopped.")
