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

# Load environment variables from .env file
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

# Initialize Twitter API clients
# client: for searching tweets (read-only operations)
# auth & post_api: for posting replies (write operations)
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
post_api = tweepy.API(auth)

# File paths and configuration
CANCER_TWEETS_PATH = "data/cancer_posts.csv"  # Stores found cancer-related tweets
ALL_SEEN_IDS_PATH = "data/all_seen_ids.txt"   # Tracks which tweets we've already seen
REPLY_PREVIEWS_PATH = "data/reply_previews.txt"  # Stores reply previews before posting
MAX_REPLIES_PER_HOUR = 20                    # Rate limiting to avoid Twitter restrictions
reply_timestamps = []                         # Tracks when replies were sent for rate limiting

def mentions_celebrity(text):
    """
    Check if a tweet mentions a celebrity or public figure.
    We avoid replying to tweets about celebrities to prevent inappropriate responses.
    
    Args:
        text (str): The tweet text to check
        
    Returns:
        bool: True if celebrity is mentioned, False otherwise
    """
    celebrity_keywords = [
        "trump", "biden", "elon", "kardashian", "taylor swift", "celebrity",
        "president", "prime minister", "actor", "musician", "foxnews", "cnn",
        "@realdonaldtrump", "@potus", "@foxnews"
    ]
    text = text.lower()
    return any(name in text for name in celebrity_keywords)

def ensure_file_exists(path, headers=None):
    """
    Create a file and its directory if they don't exist.
    Used to ensure CSV files are properly initialized with headers.
    
    Args:
        path (str): File path to create
        headers (list): CSV headers to write if creating a new file
    """
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            if headers:
                writer = csv.writer(f)
                writer.writerow(headers)

def load_ids_from_file(path):
    """
    Load a set of tweet IDs from a text file.
    Used to track which tweets we've already processed.
    
    Args:
        path (str): Path to the file containing tweet IDs
        
    Returns:
        set: Set of tweet IDs as strings
    """
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_id_to_file(path, tweet_id):
    """
    Save a tweet ID to a file to mark it as processed.
    
    Args:
        path (str): File path to save the ID to
        tweet_id (str/int): The tweet ID to save
    """
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(tweet_id) + "\n")

def fallback_cancer_replies():
    """
    Provide fallback replies when OpenAI API is unavailable.
    These are pre-written responses about the AI cancer tool.
    
    Returns:
        list: List of fallback reply messages
    """
    return [
        "Just diagnosed? Don't settle for one opinion. Our AI scans your data and all treatments worldwide. DM if you want the link.",
        "Cancer's terrifying. We built an AI to help with treatment decisions. Can't launch it in the West, so we built it in Albania. DM if you want to see it.",
        "Sending love. Most people don't get the best options. AI can help, but the system blocks it. We're bypassing that. Let me know if you're curious.",
        "This is why we built our AI. It finds better paths when things feel hopeless. Can't promise a cure, but it can guide. DM if you want it."
    ]

def remove_emojis(text):
    """
    Remove emoji characters from text using regex.
    Twitter has character limits, so removing emojis helps stay within limits.
    
    Args:
        text (str): Text to remove emojis from
        
    Returns:
        str: Text with emojis removed
    """
    return re.sub(r'[\U00010000-\U0010ffff]', '', text)

def generate_ai_reply(prompt, system_message, api_key):
    """
    Generate a reply using OpenAI's GPT-3.5-turbo model.
    
    Args:
        prompt (str): The user message/prompt
        system_message (str): Instructions for the AI model
        api_key (str): OpenAI API key
        
    Returns:
        str: Generated reply text, or None if failed
    """
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
    """
    Generate an appropriate reply to a cancer-related tweet.
    Uses AI if available, otherwise falls back to pre-written responses.
    
    Args:
        tweet_text (str): The original tweet text to reply to
        
    Returns:
        str: Generated reply text
    """
    try:
        if not openai_api_key:
            return random.choice(fallback_cancer_replies())

        # System message that defines the AI's personality and behavior
        system_message = """You are a real person on Twitter, not a bot or a brand. You're responding to people tweeting about cancer—often overwhelmed, scared, or grieving.

    You're building an AI tool because your close friend has cancer. Watching them bounce between doctors and struggle for clarity showed you how broken and slow the system is. That pushed you to build something better—outside the U.S., in Albania—because in the West it's nearly impossible to move fast when time matters most.

    The AI isn't a miracle. It reads someone's records, scans, and genetic info, and compares them to global studies, trials, and real-world outcomes to suggest better treatment paths. It brings clarity when things feel lost.

    You are not promoting a product. You're offering something real—because someone you love is still fighting.

    Every reply must:
    - Be under 60 words
    - Be under 120 characters
    - Sound like a real, emotionally honest human
    - Never use marketing language, therapy clichés, hashtags, links, or emojis
    - Never mention celebrity names
    - Never say "sorry for your loss" or offer condolences when a public figure is referenced
    - Be completely unique and different from other replies
    - Avoid repetitive phrases like "feel free to message", "DM if you want", "let me know if"
    - Use "DM me if you want the link" or "feel free to reach out" instead of "email me"

    Context is everything:
    - If the tweet is about a **public figure** (like a president, actor, or celebrity), do **not** express sympathy. Do **not** misread it as a personal loss.
    - Instead, shift the message back to your experience and why you're building the tool. Acknowledge the topic *generally*, not emotionally.

    Be creative and varied in your responses. Use different approaches:
    - Share a brief personal story
    - Mention specific aspects of the AI tool
    - Talk about the global research it accesses
    - Reference the speed and efficiency
    - Discuss the clarity it provides
    - Mention the friend who inspired it

    Only reply to tweets that are personally relevant or clearly written by someone affected by cancer—skip news, politics, or vague posts."""

        # User message with specific instructions for this tweet
        user_message = f"""Tweet: \"{tweet_text}\"

    You're replying to someone tweeting about cancer. Read the context first.

    If it's about a **public figure** (e.g., Joe Biden, a celebrity), do **not** reply with condolences or empathy—as if the person tweeting is personally affected. That would sound wrong. Instead, acknowledge the broader issue and shift the message back to your experience. Mention your friend and the AI tool you're building.

    If the tweet is **personal** (they mention their mom, sibling, or themselves), then you can reply with emotional honesty—briefly mention your friend's cancer and how that led to building the tool.

    CRITICAL: Keep reply under 120 characters. Be extremely concise and direct.

    IMPORTANT: Make this reply completely unique and different. Avoid repetitive phrases. Be creative and varied in your approach.

    Examples of short, varied approaches:
    - "My friend's cancer journey inspired this AI tool."
    - "It scans global studies for better treatment paths."
    - "Built outside the U.S. because we couldn't wait."
    - "Brings clarity when doctors disagree."
    - "Compares cases worldwide for better options."
    - "Finds patterns doctors might miss."
    - "Bypasses the slow system that almost cost time."
    - "Helped people we care about find better paths."

    Be creative and make each reply feel personal and unique."""

        reply = generate_ai_reply(user_message, system_message, openai_api_key)
        if reply:
            return remove_emojis(reply.strip('"\''))[:280]  # Twitter character limit for posting-ready previews
        return random.choice(fallback_cancer_replies())
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        return random.choice(fallback_cancer_replies())

def search_tweets_by_keyword(keyword, count=30):
    """
    Search Twitter for tweets containing specific keywords.
    
    Args:
        keyword (str): The keyword to search for
        count (int): Maximum number of tweets to return
        
    Returns:
        list: List of tweet objects, or empty list if failed
    """
    try:
        query = f"{keyword} lang:en -is:retweet"  # English tweets only, exclude retweets
        response = client.search_recent_tweets(
            query=query,
            tweet_fields=["id", "text", "created_at", "author_id"],
            max_results=min(count, 100)
        )
        return response.data if response.data else []
    except tweepy.TooManyRequests:
        logger.warning(f"Rate limit hit for keyword: {keyword}. Sleeping for 15 minutes.")
        time.sleep(900)  # Wait 15 minutes
        return []
    except Exception as e:
        logger.error(f"Twitter search failed for '{keyword}': {e}")
        return []

def can_reply():
    """
    Check if we can send another reply based on rate limiting.
    Ensures we don't exceed MAX_REPLIES_PER_HOUR.
    
    Returns:
        bool: True if we can reply, False if rate limited
    """
    now = time.time()
    global reply_timestamps
    # Remove timestamps older than 1 hour
    reply_timestamps = [t for t in reply_timestamps if now - t < 3600]
    return len(reply_timestamps) < MAX_REPLIES_PER_HOUR

def looks_like_real_cancer_tweet(text):
    """
    Filter tweets to find genuine cancer-related posts.
    Uses keyword matching to identify real cancer discussions vs. spam/politics.
    
    Args:
        text (str): Tweet text to analyze
        
    Returns:
        bool: True if it looks like a real cancer tweet, False otherwise
    """
    text = text.lower()

    # Keywords that indicate genuine cancer discussion (focusing on current patients, not survivors)
    required_phrases = [
        "diagnosed with", "chemo", "chemotherapy", "radiation", "stage 4",
        "my mom has", "my dad has", "my sister has", "tumor", "scan came back",
        "oncologist", "metastatic", "just found out", "treatment", "currently fighting",
        "going through chemo", "on chemo", "starting chemo", "chemo side effects",
        "radiation side effects", "treatment side effects", "cancer pain", "cancer symptoms",
        "my cancer", "fighting cancer", "battling cancer", "cancer journey", "cancer battle",
        "cancer treatment", "cancer therapy", "cancer medication", "cancer drugs",
        "cancer surgery", "cancer operation", "cancer procedure", "cancer scan",
        "cancer test", "cancer biopsy", "cancer results", "cancer update",
        "cancer progress", "cancer status", "cancer condition", "cancer health",
        "cancer recovery", "cancer healing", "cancer remission", "cancer relapse",
        "cancer recurrence", "cancer spread", "cancer growth", "cancer tumor",
        "cancer mass", "cancer lump", "cancer lesion", "cancer spot",
        "cancer cell", "cancer tissue", "cancer organ", "cancer bone",
        "cancer liver", "cancer lung", "cancer brain", "cancer blood",
        "cancer lymph", "cancer node", "cancer gland", "cancer marrow"
    ]

    # Keywords that indicate spam, politics, or inappropriate content
    blacklist_phrases = [
    "you are a cancer", "low iq", "racist", "white", "black people", "nazis",
    "jews", "israel", "hamas", "muslims", "zionist", "verwoed", "tereblanch",
    "bitch", "fuck", "shove it", "horse mommy", "motherfucker", "brain dead",
    "dipshit", "retard", "dumbass", "cunt"
    ]

    # Keywords that indicate survivor content (to exclude)
    survivor_phrases = [
        "cancer survivor", "survived cancer", "beat cancer", "i beat cancer", 
        "cancer free", "cancer-free", "no evidence of disease", "ned",
        "survivor story", "survivor journey", "survivor experience",
        "survivor life", "survivor tips", "survivor advice", "survivor support",
        "survivor community", "survivor group", "survivor network",
        "survivor celebration", "survivor anniversary", "survivor milestone",
        "survivor victory", "survivor win", "survivor success", "survivor achievement",
        "survivor inspiration", "survivor motivation", "survivor hope",
        "survivor strength", "survivor courage", "survivor warrior",
        "survivor fighter", "survivor hero", "survivor champion",
        "survivor advocate", "survivor awareness", "survivor education",
        "survivor research", "survivor fundraiser", "survivor event",
        "survivor walk", "survivor run", "survivor race", "survivor marathon",
        "survivor triathlon", "survivor challenge", "survivor campaign",
        "survivor movement", "survivor mission", "survivor purpose",
        "survivor legacy", "survivor impact", "survivor difference",
        "survivor change", "survivor help", "survivor support",
        "survivor care", "survivor love", "survivor family",
        "survivor friend", "survivor team", "survivor crew",
        "survivor squad", "survivor tribe", "survivor village",
        "survivor nation", "survivor world", "survivor universe"
    ]

    return (
        any(phrase in text for phrase in required_phrases) and
        not any(bad in text for bad in blacklist_phrases) and
        not any(survivor in text for survivor in survivor_phrases)
    )

def save_tweets_to_csv(tweets, file_path):
    """
    Save found tweets to a CSV file, avoiding duplicates.
    
    Args:
        tweets (list): List of tweet objects to save
        file_path (str): Path to the CSV file
    """
    print(f"🔧 DEBUG: Trying to save {len(tweets)} tweets to {file_path}")
    
    seen_ids = load_ids_from_file(ALL_SEEN_IDS_PATH)
    print(f"🔧 DEBUG: Found {len(seen_ids)} existing IDs in all_seen_ids.txt")
    
    new_tweets = [t for t in tweets if str(t.id) not in seen_ids]
    print(f"🔧 DEBUG: {len(new_tweets)} tweets are new (not duplicates)")

    if not new_tweets:
        print("🔧 DEBUG: No new tweets to save - this shouldn't happen if all_seen_ids.txt is empty!")
        logger.info("No new tweets to save.")
        return

    print(f"🔧 DEBUG: About to save {len(new_tweets)} tweets to CSV...")
    print(f"🔧 DEBUG: File path: {os.path.abspath(file_path)}")
    
    # Check if file exists before writing
    file_exists_before = os.path.exists(file_path)
    print(f"🔧 DEBUG: File exists before writing: {file_exists_before}")

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for i, tweet in enumerate(new_tweets):
            row = [tweet.id, tweet.text.replace("\n", " ").strip(), tweet.created_at, tweet.author_id]
            writer.writerow(row)
            print(f"🔧 DEBUG: Wrote tweet {i+1}: {tweet.id}")
            save_id_to_file(ALL_SEEN_IDS_PATH, tweet.id)

    # Check file after writing
    file_exists_after = os.path.exists(file_path)
    file_size = os.path.getsize(file_path) if file_exists_after else 0
    print(f"🔧 DEBUG: File exists after writing: {file_exists_after}")
    print(f"🔧 DEBUG: File size after writing: {file_size} bytes")

    logger.info(f"Saved {len(new_tweets)} new tweets to {file_path}")
    print(f"🔧 DEBUG: Successfully saved {len(new_tweets)} tweets")

def save_reply_url(url):
    """
    Save a reply URL to a file for tracking purposes.
    
    Args:
        url (str): The URL of the posted reply
    """
    os.makedirs("data", exist_ok=True)  # Make sure 'data/' folder exists
    with open("data/reply_urls.txt", "a", encoding="utf-8") as f:
        f.write(url + "\n")

def save_reply_preview(original_tweet_id, original_tweet_text, reply_text, timestamp=None):
    """
    Save a reply preview before posting it to Twitter.
    This allows for review of what the bot is about to post.
    
    Args:
        original_tweet_id (str): ID of the tweet being replied to
        original_tweet_text (str): Text of the original tweet
        reply_text (str): The generated reply text
        timestamp (str): Optional timestamp, defaults to current time
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    os.makedirs("data", exist_ok=True)
    
    preview_entry = f"""
=== REPLY PREVIEW - {timestamp} ===
Original Tweet ID: {original_tweet_id}
Original Tweet: {original_tweet_text}
Generated Reply: {reply_text}
Status: PENDING
{'='*50}
"""
    
    with open(REPLY_PREVIEWS_PATH, "a", encoding="utf-8") as f:
        f.write(preview_entry)
    
    logger.info(f"Saved reply preview for tweet {original_tweet_id}")

def mark_reply_as_posted(original_tweet_id, reply_url):
    """
    Mark a reply preview as posted by updating its status.
    
    Args:
        original_tweet_id (str): ID of the original tweet
        reply_url (str): URL of the posted reply
    """
    if not os.path.exists(REPLY_PREVIEWS_PATH):
        return
    
    # Read the file
    with open(REPLY_PREVIEWS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace the status for this specific tweet
    pattern = f"Original Tweet ID: {original_tweet_id}.*?Status: PENDING"
    replacement = f"Original Tweet ID: {original_tweet_id}\\nOriginal Tweet: .*?\\nGenerated Reply: .*?\\nStatus: POSTED\\nReply URL: {reply_url}"
    
    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write back to file
    with open(REPLY_PREVIEWS_PATH, "w", encoding="utf-8") as f:
        f.write(updated_content)
    
    logger.info(f"Marked reply for tweet {original_tweet_id} as posted")

def get_pending_replies():
    """
    Get all pending replies from the previews file.
    
    Returns:
        list: List of pending reply dictionaries
    """
    if not os.path.exists(REPLY_PREVIEWS_PATH):
        return []
    
    with open(REPLY_PREVIEWS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find all pending replies
    pending_blocks = re.findall(r'=== REPLY PREVIEW - (.*?) ===\nOriginal Tweet ID: (.*?)\nOriginal Tweet: (.*?)\nGenerated Reply: (.*?)\nStatus: PENDING', content, re.DOTALL)
    
    pending_replies = []
    for timestamp, tweet_id, original_tweet, reply_text in pending_blocks:
        pending_replies.append({
            'timestamp': timestamp.strip(),
            'tweet_id': tweet_id.strip(),
            'original_tweet': original_tweet.strip(),
            'reply_text': reply_text.strip()
        })
    
    return pending_replies

def post_reply(tweet_id, reply_text):
    """
    Post a reply to Twitter.
    
    Args:
        tweet_id (str): ID of the tweet to reply to
        reply_text (str): The reply text to post
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Wait 2 minutes before posting (Twitter rate limiting)
        print(f"⏳ Waiting 2 minutes before posting...")
        time.sleep(120)
        
        # Post the reply
        tweet = post_api.update_status(
            status=reply_text,
            in_reply_to_status_id=tweet_id,
            auto_populate_reply_metadata=True
        )
        
        # Build reply URL
        reply_url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}"
        
        # Save to reply_urls.txt
        os.makedirs("data", exist_ok=True)
        with open("data/reply_urls.txt", "a", encoding="utf-8") as f:
            f.write(reply_url + "\n")
        
        # Update preview status
        mark_reply_as_posted(tweet_id, reply_url)
        
        print(f"✅ Successfully posted reply!")
        print(f"🔗 Reply URL: {reply_url}")
        return True
        
    except Exception as e:
        print(f"❌ Error posting reply: {e}")
        return False

def view_reply_previews():
    """
    Display all reply previews from the Twitter bot.
    """
    print("=== Twitter Bot Reply Previews ===")
    print()
    
    if not os.path.exists(REPLY_PREVIEWS_PATH):
        print("📁 No reply previews found yet!")
        print("   The bot hasn't generated any replies yet.")
        print("   Run the bot first to generate some previews.")
        return
    
    try:
        with open(REPLY_PREVIEWS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        if not content.strip():
            print("📁 File exists but no previews found!")
            print("   The bot hasn't generated any replies yet.")
            return
        
        print(content)
        
        # Count pending vs posted
        pending_count = content.count("Status: PENDING")
        posted_count = content.count("Status: POSTED")
        
        print(f"\n📊 Summary:")
        print(f"   Pending replies: {pending_count}")
        print(f"   Posted replies: {posted_count}")
        print(f"   Total previews: {pending_count + posted_count}")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")

def approve_replies():
    """
    Main function to approve and post replies.
    """
    print("=== Twitter Bot Reply Approval ===")
    print()
    
    # Get pending replies
    pending_replies = get_pending_replies()
    
    if not pending_replies:
        print("📁 No pending replies found!")
        print("   All previews have been posted or there are no previews yet.")
        return
    
    print(f"📋 Found {len(pending_replies)} pending reply(ies):")
    print("-" * 60)
    
    # Display pending replies
    for i, reply in enumerate(pending_replies, 1):
        print(f"\n{i}. Tweet ID: {reply['tweet_id']}")
        print(f"   Time: {reply['timestamp']}")
        print(f"   Original: {reply['original_tweet'][:100]}...")
        print(f"   Reply: {reply['reply_text']}")
        print("-" * 60)
    
    # Ask for approval
    print(f"\n🤔 Do you want to post these {len(pending_replies)} reply(ies)?")
    print("   Options:")
    print("   - 'all' to post all pending replies")
    print("   - '1', '2', '3' etc. to post specific replies")
    print("   - 'none' to skip all")
    
    choice = input("\nEnter your choice: ").strip().lower()
    
    if choice == 'all':
        print(f"\n🚀 Posting all {len(pending_replies)} replies...")
        for i, reply in enumerate(pending_replies, 1):
            print(f"\n📤 Posting reply {i}/{len(pending_replies)}...")
            success = post_reply(reply['tweet_id'], reply['reply_text'])
            if success:
                print(f"✅ Reply {i} posted successfully!")
            else:
                print(f"❌ Failed to post reply {i}")
    
    elif choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(pending_replies):
            reply = pending_replies[index]
            print(f"\n📤 Posting reply {index + 1}...")
            success = post_reply(reply['tweet_id'], reply['reply_text'])
            if success:
                print(f"✅ Reply posted successfully!")
            else:
                print(f"❌ Failed to post reply")
        else:
            print("❌ Invalid reply number!")
    
    elif choice == 'none':
        print("⏸️  Skipping all replies. They remain pending for later approval.")
    
    else:
        print("❌ Invalid choice!")

def collect_and_save_cancer_tweets():
    """
    Main function to search for cancer-related tweets and save them.
    Searches multiple keywords and filters for genuine cancer discussions.
    """
    # Clear duplicate tracking to get fresh results
    print("🧹 Clearing previous duplicate tracking to get fresh results...")
    if os.path.exists(ALL_SEEN_IDS_PATH):
        os.remove(ALL_SEEN_IDS_PATH)
        print("✅ Cleared all_seen_ids.txt")
    
    # List of cancer-related keywords to search for (focusing on current patients, not survivors)
    cancer_keywords = [
        "just diagnosed with cancer", "stage 4 cancer", "my cancer journey",
        "cancer treatment advice", "chemo side effects", "cancer trial", 
        "breast cancer diagnosis", "pancreatic cancer help", "cancer battle", 
        "terminal cancer", "fighting cancer", "my mom has cancer", 
        "my dad has cancer", "my sister has cancer", "my brother has cancer", 
        "cancer pain", "scan came back", "tumor found", "cancer diagnosis",
        "metastatic cancer", "oncology appointment", "chemo started",
        "radiation treatment", "cancer support", "end of life care",
        "cancer is back", "recurrence of cancer", "cancer sucks",
        "hope for cancer patients", "clinical trials for cancer",
        "alternative cancer treatment", "lung cancer diagnosis", 
        "my friend has cancer", "currently fighting cancer", "going through chemo",
        "on chemo", "starting chemo", "chemo side effects", "radiation side effects",
        "treatment side effects", "cancer symptoms", "my cancer", "battling cancer",
        "cancer treatment", "cancer therapy", "cancer medication", "cancer drugs",
        "cancer surgery", "cancer operation", "cancer procedure", "cancer scan",
        "cancer test", "cancer biopsy", "cancer results", "cancer update",
        "cancer progress", "cancer status", "cancer condition", "cancer health",
        "cancer recovery", "cancer healing", "cancer remission", "cancer relapse",
        "cancer recurrence", "cancer spread", "cancer growth", "cancer tumor",
        "cancer mass", "cancer lump", "cancer lesion", "cancer spot",
        "cancer cell", "cancer tissue", "cancer organ", "cancer bone",
        "cancer liver", "cancer lung", "cancer brain", "cancer blood",
        "cancer lymph", "cancer node", "cancer gland", "cancer marrow"
    ]

    # Randomly select 8 keywords to search (to avoid rate limits)
    sampled_keywords = random.sample(cancer_keywords, 8)
    ensure_file_exists(CANCER_TWEETS_PATH, ["tweet_id", "text", "created_at", "author_id"])
    
    all_filtered_tweets = []
    
    for kw in sampled_keywords:
        print(f"🔍 Searching: {kw}")
        tweets = search_tweets_by_keyword(kw)
        filtered_tweets = [t for t in tweets if looks_like_real_cancer_tweet(t.text)]
        print(f"→ Found {len(tweets)} tweets, {len(filtered_tweets)} passed filter.")
        save_tweets_to_csv(filtered_tweets, CANCER_TWEETS_PATH)
        all_filtered_tweets.extend(filtered_tweets)
        time.sleep(random.uniform(10, 20))  # Random delay between searches
    
    # Generate previews directly from search results
    generate_previews_from_tweets(all_filtered_tweets)

def generate_previews_from_tweets(tweets):
    """
    Generate previews directly from tweet objects.
    
    Args:
        tweets (list): List of tweet objects to generate previews for
    """
    preview_count = 0
    processed_ids = set()  # Track IDs processed in this session
    
    print(f"\n🎯 Generating previews from {len(tweets)} filtered tweets...")
    
    for tweet in tweets:
        tweet_id = tweet.id
        
        # Skip if already processed in this session
        if tweet_id in processed_ids:
            continue
            
        tweet_text = tweet.text

        # Skip tweets mentioning celebrities
        if mentions_celebrity(tweet_text):
            print(f"🚫 Skipped tweet (mentions celebrity): {tweet_text[:50]}...")
            continue

        # Skip tweets that don't look like real cancer posts
        if not looks_like_real_cancer_tweet(tweet_text):
            print(f"❌ Skipped tweet (not a real cancer post): {tweet_text[:50]}...")
            continue

        print(f"\n📌 Tweet ID: {tweet_id}")
        print(f"💬 Tweet: {tweet_text}")
        reply = generate_reply(tweet_text)
        print(f"\n🧠 Generated Reply:\n{reply}")
        print("✅ Preview generated - NO POSTING TO TWITTER")
        print("=" * 60)
        
        processed_ids.add(tweet_id)  # Mark as processed
        preview_count += 1
    
    if preview_count == 0:
        print("❌ No suitable tweets found to generate previews.")
    else:
        print(f"\n🎉 Generated {preview_count} preview(s)!")

def show_menu():
    """
    Display the main menu with available options.
    """
    print("=== Twitter Bot - Preview Mode ===")
    print()
    print("Available commands:")
    print("1. 'search' - Search for cancer tweets and generate previews")
    print("2. 'view' - View all reply previews")
    print("3. 'approve' - Approve and post pending replies")
    print("4. 'urls' - View all posted reply URLs")
    print("5. 'menu' - Show this menu")
    print("6. 'exit' - Exit the program")
    print()
    print("Note: This bot only generates previews. No automatic posting to Twitter.")
    print()

def view_reply_urls():
    """
    Display all posted reply URLs.
    """
    urls_file = "data/reply_urls.txt"
    
    print("=== Posted Reply URLs ===")
    print()
    
    if not os.path.exists(urls_file):
        print("📁 No URLs found yet!")
        print("   No replies have been posted yet.")
        return
    
    try:
        with open(urls_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        if not urls:
            print("📁 File exists but no URLs found!")
            return
        
        print(f"📊 Found {len(urls)} posted reply URL(s):")
        print("-" * 60)
        
        for i, url in enumerate(urls, 1):
            print(f"{i:2d}. {url}")
        
        print("-" * 60)
        print(f"Total: {len(urls)} URLs")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")

# Main execution block
if __name__ == "__main__":
    # Verify Twitter credentials before starting
    try:
        user = post_api.verify_credentials()
        print(f"✅ Logged in as: @{user.screen_name} (User ID: {user.id})")
    except Exception as e:
        print("❌ Failed to verify Twitter account:", e)
        exit()

    logger.info("🩺 Liora AI Cancer Tweet Bot Starting - Preview Mode")
    print("\nBot will search for cancer tweets and generate previews (NO POSTING).\n")

    try:
        collect_and_save_cancer_tweets()
        # process_and_reply_to_cancer_tweets() # This function is no longer needed
        print("✅ Search and preview generation complete!")
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        print("🛑 Bot stopped.")