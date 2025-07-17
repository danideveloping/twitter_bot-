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
print(f"🔑 Loaded API key: {openai_api_key}")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

# Twitter API clients
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
post_api = tweepy.API(auth)

# File paths
CANCER_TWEETS_PATH = "data/cancer_posts.csv"
REPLIED_LOG_PATH = "data/replied_ids.txt"
ALL_SEEN_IDS_PATH = "data/all_seen_ids.txt"
REPLY_LOG_FILE = "data/reply_log.csv"
MAX_REPLIES_PER_HOUR = 200
reply_timestamps = []

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
                "max_tokens": 60,
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

        system_message = """You are a real person on Twitter. You're responding to people talking about cancer.
Be deeply human, honest, and emotionally raw. Avoid corporate or robotic tone. Never sound like a company or AI.
You believe AI could save lives but it's blocked by regulations in the West, so you're building it in Albania.
Do not include hashtags or links. End with something like: 'DM me if you want the link' if appropriate.
Max 60 words. No emojis. No marketing. Just honesty and empathy."""

        user_message = f"""Tweet: \"{tweet_text}\"\nWrite a reply in your voice. Real, short, supportive, rebellious. Mention that AI can help, but it's blocked in the West. Offer to send a link in DMs. Be casual, no formal intros."""

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
        "alternative cancer treatment",

        # Added keywords
        "lung cancer diagnosis", "my friend has cancer", "brain tumor diagnosis",
        "how do you survive cancer", "chemo journey", "radiation side effects",
        "immunotherapy cancer", "cancer symptoms", "oncologist appointment",
        "scared of cancer", "fear of chemo", "cancer prognosis", 
        "can cancer be cured", "cancer came back", "cancer fight",
        "how long do I have cancer", "lost my mom to cancer",
        "lost my dad to cancer", "my partner has cancer", "cancer depression",
        "colon cancer stage 3", "cancer recovery", "after chemo", 
        "life after cancer", "post cancer journey", "rare cancer diagnosis",
        "liver cancer stage 4", "thyroid cancer", "skin cancer update",
        "pet scan cancer", "terminal illness support", "inoperable cancer",
        "cancer pain relief", "palliative care cancer", "supporting cancer patients",
        "talking to kids about cancer", "healing from cancer", 
        "i’m scared of cancer", "dad passed from cancer", 
        "she beat cancer", "miracle cancer recovery"
    ]


    sampled_keywords = random.sample(cancer_keywords, 8)
    ensure_file_exists(CANCER_TWEETS_PATH, ["tweet_id", "text", "created_at", "author_id"])
    for kw in sampled_keywords:
        print(f"🔍 Searching: {kw}")
        tweets = search_tweets_by_keyword(kw)
        print(f"→ Found {len(tweets)} tweets.")
        save_tweets_to_csv(tweets, CANCER_TWEETS_PATH)
        time.sleep(random.uniform(10, 20))

def process_and_reply_to_cancer_tweets():
    seen = load_ids_from_file(REPLIED_LOG_PATH)
    ensure_file_exists(REPLY_LOG_FILE, ["tweet_id", "tweet_text", "reply"])

    with open(CANCER_TWEETS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["tweet_id"] in seen:
                continue
            if not can_reply():
                print("⚠️ Hourly reply limit reached.")
                return

            tweet_id = row["tweet_id"]
            tweet_text = row["text"]

            print(f"\n📌 Tweet ID: {tweet_id}")
            print(f"💬 Tweet: {tweet_text}")
            reply = generate_reply(tweet_text)
            print(f"\n🧠 Generated Reply:\n{reply}")
            confirm = input("\nSend this reply? (y/n): ").strip().lower()
            if confirm != 'y':
                print("⏭️ Skipped.")
                return

            try:
                delay = 120                 
                print(f"⏳ Sleeping {int(delay)} seconds before posting...")
                time.sleep(delay)

                post_api.update_status(
                    status=reply,
                    in_reply_to_status_id=tweet_id,
                    auto_populate_reply_metadata=True
                )
                logger.info(f"✅ Replied to {tweet_id}")
                save_id_to_file(REPLIED_LOG_PATH, tweet_id)
                with open(REPLY_LOG_FILE, "a", newline="", encoding="utf-8") as log:
                    writer = csv.writer(log)
                    writer.writerow([tweet_id, tweet_text, reply])
                reply_timestamps.append(time.time())
                return  # Only 1 per run
            except Exception as e:
                logger.error(f"❌ Error replying to tweet {tweet_id}: {e}")
                return

if __name__ == "__main__":
    import schedule
    try:
        user = post_api.verify_credentials()
        print(f"✅ Logged in as: @{user.screen_name} (User ID: {user.id})")
    except Exception as e:
        print("❌ Failed to verify Twitter account:", e)
        user = None
   
    logger.info("🩺 Liora AI Cancer Tweet Bot Starting")
    print("\nBot will search and reply to tweets about cancer every 2 hours.\n")

    # Step 1: Collect tweets
    collect_and_save_cancer_tweets()

    # Step 2: Preview all replies before asking for confirmation
    seen = load_ids_from_file(REPLIED_LOG_PATH)
    ensure_file_exists(REPLY_LOG_FILE, ["tweet_id", "tweet_text", "reply"])

    print("\n📋 Previewing replies:\n")
    pending_replies = []

    with open(CANCER_TWEETS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tweet_id = row["tweet_id"]
            tweet_text = row["text"]

            if tweet_id in seen:
                continue
            reply = generate_reply(tweet_text)
            pending_replies.append((tweet_id, tweet_text, reply))

    if not pending_replies:
        print("✅ No new tweets to reply to.")
    else:
        for tweet_id, tweet_text, reply in pending_replies:
            print("────────────────────────────")
            print(f"📌 Tweet ID: {tweet_id}")
            print(f"💬 Tweet: {tweet_text}")
            print(f"🧠 Reply: {reply}\n")

        proceed = input("👉 Proceed to reply to the first one? (y/n): ").strip().lower()
        if proceed == 'y':
            process_and_reply_to_cancer_tweets()
        else:
            print("🚫 Aborted. No replies sent.")

    try:
        while True:
            collect_and_save_cancer_tweets()
            process_and_reply_to_cancer_tweets()
            print("⏳ Waiting 2 minutes for next tweet...")
            time.sleep(120)  # 2-minute cooldown between full runs
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        print("Bot stopped.")


