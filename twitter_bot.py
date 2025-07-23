import os
import csv
import time
import random
import logging
import re
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
import tweepy
import schedule

# Load environment variables from .env file
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Debug: Check if credentials are loaded
print(f"🔑 Twitter API Key loaded: {'Yes' if TWITTER_API_KEY else 'No'}")
print(f"🔑 Twitter API Secret loaded: {'Yes' if TWITTER_API_SECRET else 'No'}")
print(f"🔑 Twitter Access Token loaded: {'Yes' if TWITTER_ACCESS_TOKEN else 'No'}")
print(f"🔑 Twitter Access Secret loaded: {'Yes' if TWITTER_ACCESS_SECRET else 'No'}")
print(f"🔑 Twitter Bearer Token loaded: {'Yes' if TWITTER_BEARER_TOKEN else 'No'}")

# Check if all required credentials are present
if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET, TWITTER_BEARER_TOKEN]):
    print("❌ ERROR: Missing Twitter API credentials!")
    print("Please make sure your .env file contains:")
    print("TWITTER_API_KEY=your_api_key")
    print("TWITTER_API_SECRET=your_api_secret")
    print("TWITTER_ACCESS_TOKEN=your_access_token")
    print("TWITTER_ACCESS_SECRET=your_access_secret")
    print("TWITTER_BEARER_TOKEN=your_bearer_token")
    exit(1)

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

# Initialize Twitter API clients
print("🔧 Initializing Twitter clients...")

# Create separate clients for different purposes
# Client for reading/searching tweets (using Bearer token)
read_client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,  # Add Bearer token for search endpoints
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# Client for posting replies (using same OAuth credentials + Bearer token for searching)
write_client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,  # Add Bearer token for search endpoints
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# Also keep the old API for compatibility
auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
post_api = tweepy.API(auth)

def show_diagnostic_info():
    """Display current diagnostic information about Twitter credentials"""
    print("\n🔧 CURRENT DIAGNOSTIC INFORMATION:")
    print(f"   API Key: {TWITTER_API_KEY[:5]}..." if TWITTER_API_KEY else "❌ Missing")
    print(f"   API Secret: {TWITTER_API_SECRET[:5]}..." if TWITTER_API_SECRET else "❌ Missing")
    print(f"   Access Token: {TWITTER_ACCESS_TOKEN[:5]}..." if TWITTER_ACCESS_TOKEN else "❌ Missing")
    print(f"   Access Secret: {TWITTER_ACCESS_SECRET[:5]}..." if TWITTER_ACCESS_SECRET else "❌ Missing")
    print(f"   Bearer Token: {TWITTER_BEARER_TOKEN[:10]}..." if TWITTER_BEARER_TOKEN else "❌ Missing")
    print(f"   Bot Username: {BOT_USERNAME if 'BOT_USERNAME' in globals() else 'Not set'}")
    print(f"   Bot User ID: {BOT_USER_ID if 'BOT_USER_ID' in globals() else 'Not set'}")
    print()

# Test the clients
try:
    print("🔧 Testing Twitter clients...")
    
    # Test read client (OAuth credentials)
    print("🔧 Testing read client (OAuth)...")
    try:
        test_search = read_client.search_recent_tweets(query="test", max_results=10)
        print("✅ Read client works")
    except tweepy.Unauthorized as e:
        print(f"❌ Read client failed: 401 Unauthorized - {e}")
        print("⚠️  OAuth credentials may be invalid or expired")
        print("⚠️  Possible causes:")
        print("   - API Key/Secret are incorrect")
        print("   - Access Token/Secret are incorrect")
        print("   - Tokens have expired")
        print("   - Account doesn't have proper permissions")
        print("   - API plan doesn't include search endpoints")
    except Exception as e:
        print(f"❌ Read client failed: {e}")
    
    # Test write client (OAuth credentials)
    print("🔧 Testing write client (OAuth)...")
    try:
        me = write_client.get_me()
        if me.data:
            print(f"✅ Write client works: @{me.data.username}")
            BOT_USERNAME = me.data.username
            BOT_USER_ID = me.data.id
            
            # Test if write client can also search (as backup)
            try:
                test_search_write = write_client.search_recent_tweets(query="test", max_results=10)
                print("✅ Write client can also search (backup available)")
            except Exception as e:
                print(f"⚠️  Write client cannot search: {e}")
                print("⚠️  Will need to fix API permissions for searching")
        else:
            print("❌ Write client failed - no user data returned")
            raise Exception("No user data returned")
    except tweepy.Unauthorized as e:
        print(f"❌ Write client failed: 401 Unauthorized - {e}")
        print("⚠️  OAuth credentials may be invalid or expired")
        show_diagnostic_info()
        print("💡 SOLUTIONS TO TRY:")
        print("1. Regenerate all Twitter API credentials in your Twitter Developer Portal")
        print("2. Make sure you have the correct API plan (Basic, Pro, or Enterprise)")
        print("3. Ensure your app has the required permissions (Read and Write)")
        print("4. Check that your .env file is in the correct location")
        print("5. Verify that the credentials are copied correctly (no extra spaces)")
        exit(1)
    except Exception as e:
        print(f"❌ Write client failed: {e}")
        exit(1)
        
except Exception as e:
    print(f"❌ Twitter client test failed: {e}")
    exit(1)

# Keep the old API for compatibility with some functions
auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
post_api = tweepy.API(auth)

# File paths and configuration
CANCER_TWEETS_PATH = "data/cancer_posts.csv"  # Stores found cancer-related tweets
ALL_SEEN_IDS_PATH = "data/all_seen_ids.txt"   # Tracks which tweets we've already seen
REPLY_PREVIEWS_PATH = "data/reply_previews.txt"  # Stores reply previews before posting
RESPONSES_TRACKING_PATH = "data/responses_tracking.csv"  # Tracks responses to our replies
ENGAGEMENT_METRICS_PATH = "data/engagement_metrics.csv"  # Tracks likes, retweets, etc.
POSTED_REPLIES_PATH = "data/posted_replies.csv"  # Detailed tracking of all posted replies
REPLY_URLS_PATH = "data/reply_urls.txt"  # Simple list of reply URLs

# OPTIMIZED RATE LIMITING - Twitter-friendly but more active
MAX_REPLIES_PER_HOUR = 15                    # Increased from 5 to 15 (still well under Twitter's 100/hour limit)
MAX_REPLIES_PER_DAY = 80                     # Increased from 30 to 80 (conservative daily limit)
MIN_DELAY_BETWEEN_POSTS = 120                # Minimum 2 minutes between posts (reduced from 5 minutes)
MAX_DELAY_BETWEEN_POSTS = 300                # Maximum 5 minutes between posts (reduced from 10 minutes)
BOT_CYCLE_HOURS = 4                          # Run every 4 hours instead of 6 (more frequent cycles)

reply_timestamps = []                         # Tracks when replies were sent for rate limiting
daily_reply_count = 0                         # Tracks daily reply count
last_reset_date = None                        # Tracks when to reset daily count

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
        # Political figures
        "trump", "biden", "obama", "clinton", "bush", "reagan", "carter", "ford", "nixon",
        "kamala", "harris", "pence", "mike pence", "pelosi", "mcconnell", "schumer",
        "aoc", "alexandria ocasio-cortez", "bernie", "sanders", "warren", "elizabeth warren",
        "desantis", "ron desantis", "haley", "nikki haley", "christie", "chris christie",
        "ramaswamy", "vivek", "scott", "tim scott", "binkley", "ryan binkley",
        
        # Entertainment celebrities
        "elon", "musk", "elon musk", "kardashian", "kim kardashian", "kylie jenner",
        "taylor swift", "beyonce", "jay z", "jay-z", "rihanna", "adele", "lady gaga",
        "justin bieber", "drake", "post malone", "ed sheeran", "bruno mars",
        "tom hanks", "julia roberts", "brad pitt", "angelina jolie", "leonardo dicaprio",
        "meryl streep", "denzel washington", "sandra bullock", "george clooney",
        "jennifer lawrence", "chris hemsworth", "scarlett johansson", "robert downey jr",
        "chris evans", "mark ruffalo", "jeremy renner", "chris pratt", "tom holland",
        "zendaya", "timothee chalamet", "florence pugh", "anya taylor-joy",
        
        # Sports figures
        "lebron", "lebron james", "michael jordan", "kobe bryant", "kobe",
        "tom brady", "cristiano ronaldo", "ronaldo", "messi", "lionel messi",
        "serena williams", "venus williams", "tiger woods", "mike tyson",
        "floyd mayweather", "conor mcgregor", "ufc", "nba", "nfl", "mlb", "nhl",
        
        # Business figures
        "jeff bezos", "bezos", "bill gates", "gates", "mark zuckerberg", "zuckerberg",
        "tim cook", "cook", "sundar pichai", "pichai", "satya nadella", "nadella",
        "warren buffett", "buffett", "charles koch", "koch", "george soros", "soros",
        
        # Media personalities
        "oprah", "oprah winfrey", "ellen", "ellen degeneres", "jimmy kimmel",
        "jimmy fallon", "stephen colbert", "trevor noah", "john oliver",
        "bill maher", "seth meyers", "james corden", "graham norton",
        "anderson cooper", "rachel maddow", "tucker carlson", "sean hannity",
        "laura ingraham", "jeanine pirro", "jesse watters", "greg gutfeld",
        
        # News organizations
        "foxnews", "cnn", "msnbc", "abc", "cbs", "nbc", "pbs", "npr",
        "bbc", "reuters", "associated press", "ap", "bloomberg", "cnbc",
        
        # Social media personalities
        "mrbeast", "mr beast", "pewdiepie", "pew die pie", "logan paul",
        "jake paul", "ksi", "sidemen", "david dobrik", "casey neistat",
        "marques brownlee", "mkbhd", "linus tech tips", "philip defranco",
        
        # Generic terms
        "celebrity", "celebrities", "famous", "star", "stars", "actor", "actress",
        "singer", "rapper", "athlete", "player", "coach", "president", "prime minister",
        "governor", "senator", "congressman", "congresswoman", "representative",
        "mayor", "ceo", "founder", "influencer", "youtuber", "streamer",
        
        # Specific handles
        "@realdonaldtrump", "@potus", "@foxnews", "@cnn", "@msnbc", "@abc", "@cbs",
        "@nbc", "@bbc", "@reuters", "@ap", "@bloomberg", "@cnbc", "@elonmusk",
        "@taylorswift13", "@beyonce", "@rihanna", "@adele", "@ladygaga",
        "@justinbieber", "@drake", "@postmalone", "@edsheeran", "@brunomars"
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

def get_bot_user_id():
    """
    Get the bot's user ID for tracking responses.
    
    Returns:
        str: Bot's user ID, or None if failed
    """
    try:
        user = post_api.verify_credentials()
        return str(user.id)
    except Exception as e:
        logger.error(f"Failed to get bot user ID: {e}")
        return None

def check_for_responses():
    """
    Check for responses (replies, mentions) to the bot's tweets.
    
    Returns:
        list: List of response tweets
    """
    try:
        bot_user_id = get_bot_user_id()
        if not bot_user_id:
            logger.error("Could not get bot user ID for response tracking")
            return []
        
        # Get mentions of the bot
        mentions = read_client.get_users_mentions(
            id=bot_user_id,
            tweet_fields=["id", "text", "created_at", "author_id", "in_reply_to_user_id"],
            max_results=50
        )
        
        responses = []
        if mentions.data:
            for mention in mentions.data:
                # Only include actual replies (not just mentions)
                if mention.in_reply_to_user_id == bot_user_id:
                    responses.append(mention)
        
        logger.info(f"Found {len(responses)} responses to bot tweets")
        return responses
        
    except Exception as e:
        logger.error(f"Error checking for responses: {e}")
        return []

def get_tweet_engagement(tweet_id):
    """
    Get engagement metrics for a specific tweet.
    
    Args:
        tweet_id (str): The tweet ID to check
        
    Returns:
        dict: Engagement metrics (likes, retweets, replies)
    """
    try:
        tweet = read_client.get_tweet(
            id=tweet_id,
            tweet_fields=["public_metrics"]
        )
        
        if tweet.data and hasattr(tweet.data, 'public_metrics'):
            metrics = tweet.data.public_metrics
            return {
                'likes': metrics.get('like_count', 0),
                'retweets': metrics.get('retweet_count', 0),
                'replies': metrics.get('reply_count', 0),
                'quotes': metrics.get('quote_count', 0)
            }
        return {'likes': 0, 'retweets': 0, 'replies': 0, 'quotes': 0}
        
    except Exception as e:
        logger.error(f"Error getting engagement for tweet {tweet_id}: {e}")
        return {'likes': 0, 'retweets': 0, 'replies': 0, 'quotes': 0}

def save_response_data(response_tweet, original_tweet_id):
    """
    Save response data to CSV for tracking.
    
    Args:
        response_tweet: Tweet object representing the response
        original_tweet_id (str): ID of the original tweet we replied to
    """
    ensure_file_exists(RESPONSES_TRACKING_PATH, [
        "response_tweet_id", "response_text", "response_author_id", 
        "response_created_at", "original_tweet_id", "response_type"
    ])
    
    with open(RESPONSES_TRACKING_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        row = [
            response_tweet.id,
            response_tweet.text.replace("\n", " ").strip(),
            response_tweet.author_id,
            response_tweet.created_at,
            original_tweet_id,
            "reply"  # Could be "reply", "mention", "quote" etc.
        ]
        writer.writerow(row)
    
    logger.info(f"Saved response data for tweet {response_tweet.id}")

def save_engagement_metrics(tweet_id, metrics, timestamp=None):
    """
    Save engagement metrics for a tweet.
    
    Args:
        tweet_id (str): The tweet ID
        metrics (dict): Engagement metrics
        timestamp (str): Optional timestamp, defaults to current time
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    ensure_file_exists(ENGAGEMENT_METRICS_PATH, [
        "tweet_id", "timestamp", "likes", "retweets", "replies", "quotes"
    ])
    
    with open(ENGAGEMENT_METRICS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        row = [
            tweet_id,
            timestamp,
            metrics.get('likes', 0),
            metrics.get('retweets', 0),
            metrics.get('replies', 0),
            metrics.get('quotes', 0)
        ]
        writer.writerow(row)
    
    logger.info(f"Saved engagement metrics for tweet {tweet_id}")

def track_all_responses():
    """
    Main function to check for and track all responses to bot tweets.
    """
    print("🔍 Checking for responses to bot tweets...")
    
    # Get responses
    responses = check_for_responses()
    
    if not responses:
        print("📭 No new responses found.")
        return
    
    print(f"📨 Found {len(responses)} response(s)!")
    
    # Track each response
    for response in responses:
        print(f"\n📌 Response from @{response.author_id}:")
        print(f"💬 {response.text[:100]}...")
        
        # Save response data
        save_response_data(response, response.in_reply_to_user_id)
        
        # Get and save engagement metrics for the original tweet
        original_tweet_id = response.in_reply_to_user_id
        metrics = get_tweet_engagement(original_tweet_id)
        save_engagement_metrics(original_tweet_id, metrics)
        
        print(f"✅ Tracked response and engagement metrics")
    
    print(f"\n🎉 Successfully tracked {len(responses)} response(s)!")

def view_responses():
    """
    Display all tracked responses to bot tweets.
    """
    print("=== Bot Response Tracking ===")
    print()
    
    if not os.path.exists(RESPONSES_TRACKING_PATH):
        print("📁 No response data found yet!")
        print("   No responses have been tracked yet.")
        print("   Run 'track' to check for responses.")
        return
    
    try:
        with open(RESPONSES_TRACKING_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            responses = list(reader)
        
        if not responses:
            print("📁 File exists but no responses found!")
            return
        
        print(f"📊 Found {len(responses)} tracked response(s):")
        print("-" * 80)
        
        for i, response in enumerate(responses, 1):
            print(f"\n{i}. Response ID: {response['response_tweet_id']}")
            print(f"   Author: @{response['response_author_id']}")
            print(f"   Time: {response['response_created_at']}")
            print(f"   Original Tweet: {response['original_tweet_id']}")
            print(f"   Response: {response['response_text'][:100]}...")
            print("-" * 80)
        
        print(f"\n📈 Total responses tracked: {len(responses)}")
        
    except Exception as e:
        print(f"❌ Error reading response data: {e}")

def view_engagement_metrics():
    """
    Display engagement metrics for bot tweets.
    """
    print("=== Bot Engagement Metrics ===")
    print()
    
    if not os.path.exists(ENGAGEMENT_METRICS_PATH):
        print("📁 No engagement data found yet!")
        print("   No engagement metrics have been tracked yet.")
        print("   Run 'track' to check for responses and engagement.")
        return
    
    try:
        with open(ENGAGEMENT_METRICS_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            metrics = list(reader)
        
        if not metrics:
            print("📁 File exists but no metrics found!")
            return
        
        print(f"📊 Found {len(metrics)} engagement record(s):")
        print("-" * 80)
        
        # Group by tweet ID to show latest metrics for each tweet
        tweet_metrics = {}
        for record in metrics:
            tweet_id = record['tweet_id']
            if tweet_id not in tweet_metrics or record['timestamp'] > tweet_metrics[tweet_id]['timestamp']:
                tweet_metrics[tweet_id] = record
        
        for i, (tweet_id, record) in enumerate(tweet_metrics.items(), 1):
            print(f"\n{i}. Tweet ID: {tweet_id}")
            print(f"   Last Updated: {record['timestamp']}")
            print(f"   ❤️  Likes: {record['likes']}")
            print(f"   🔄 Retweets: {record['retweets']}")
            print(f"   💬 Replies: {record['replies']}")
            print(f"   📝 Quotes: {record['quotes']}")
            print("-" * 80)
        
        # Calculate totals
        total_likes = sum(int(m['likes']) for m in tweet_metrics.values())
        total_retweets = sum(int(m['retweets']) for m in tweet_metrics.values())
        total_replies = sum(int(m['replies']) for m in tweet_metrics.values())
        total_quotes = sum(int(m['quotes']) for m in tweet_metrics.values())
        
        print(f"\n📈 Total Engagement:")
        print(f"   ❤️  Total Likes: {total_likes}")
        print(f"   🔄 Total Retweets: {total_retweets}")
        print(f"   💬 Total Replies: {total_replies}")
        print(f"   📝 Total Quotes: {total_quotes}")
        print(f"   🎯 Total Interactions: {total_likes + total_retweets + total_replies + total_quotes}")
        
    except Exception as e:
        print(f"❌ Error reading engagement data: {e}")

def export_response_data():
    """
    Export response data to a readable format.
    """
    print("=== Exporting Response Data ===")
    print()
    
    if not os.path.exists(RESPONSES_TRACKING_PATH):
        print("📁 No response data to export!")
        return
    
    try:
        with open(RESPONSES_TRACKING_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            responses = list(reader)
        
        if not responses:
            print("📁 No responses to export!")
            return
        
        # Create export file
        export_path = "data/responses_export.txt"
        with open(export_path, "w", encoding="utf-8") as f:
            f.write("=== BOT RESPONSES EXPORT ===\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Responses: {len(responses)}\n\n")
            
            for i, response in enumerate(responses, 1):
                f.write(f"RESPONSE #{i}\n")
                f.write(f"Response ID: {response['response_tweet_id']}\n")
                f.write(f"Author: @{response['response_author_id']}\n")
                f.write(f"Time: {response['response_created_at']}\n")
                f.write(f"Original Tweet: {response['original_tweet_id']}\n")
                f.write(f"Response Text: {response['response_text']}\n")
                f.write("-" * 60 + "\n\n")
        
        print(f"✅ Exported {len(responses)} responses to {export_path}")
        
    except Exception as e:
        print(f"❌ Error exporting data: {e}")

def fallback_cancer_replies():
    """
    Provide fallback replies when OpenAI API is unavailable.
    These are pre-written responses about the AI cancer tool.
    Note: Call-to-action will be added automatically by the system.
    
    Returns:
        list: List of fallback reply messages
    """
    return [
        "Just diagnosed? Don't settle for one opinion. Our AI scans your data and all treatments worldwide.",
        "Cancer's terrifying. We built an AI to help with treatment decisions. Can't launch it in the West, so we built it in Albania.",
        "Sending love. Most people don't get the best options. AI can help, but the system blocks it. We're bypassing that.",
        "This is why we built our AI. It finds better paths when things feel hopeless. Can't promise a cure, but it can guide.",
        "My friend's cancer journey inspired this AI tool. It scans global studies for better treatment paths.",
        "Built outside the U.S. because we couldn't wait. Brings clarity when doctors disagree.",
        "Compares cases worldwide for better options. Finds patterns doctors might miss.",
        "Bypasses the slow system that almost cost time. Helped people we care about find better paths."
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
            base_reply = random.choice(fallback_cancer_replies())
        else:
            # System message that defines the AI's personality and behavior
            system_message = """You are a real person on Twitter, not a bot or a brand. You're responding to people tweeting about cancer—often overwhelmed, scared, or grieving.

    You're building an AI tool because your close friend has cancer. Watching them bounce between doctors and struggle for clarity showed you how broken and slow the system is. That pushed you to build something better—outside the U.S., in Albania—because in the West it's nearly impossible to move fast when time matters most.

    The AI isn't a miracle. It reads someone's records, scans, and genetic info, and compares them to global studies, trials, and real-world outcomes to suggest better treatment paths. It brings clarity when things feel lost.

    You are not promoting a product. You're offering something real—because someone you love is still fighting.

    Every reply must:
    - Be under 50 words (to leave room for call-to-action)
    - Be under 100 characters (to leave room for call-to-action)
    - Sound like a real, emotionally honest human talking to a friend
    - Never use marketing language, therapy clichés, hashtags, links, or emojis
    - Never mention celebrity names
    - Never say "sorry for your loss" or offer condolences when a public figure is referenced
    - Be completely unique and different from other replies
    - DO NOT include any call-to-action phrases - the system will add them automatically
    - Feel natural and conversational, not like advertising

    CONVERSION STRATEGIES (make it feel like talking to a friend):

    1. NATURAL CONVERSATION:
    - Share personal experience: "My friend's cancer journey inspired this"
    - Be honest about limitations: "It's not a miracle, but it helps"
    - Talk like a friend would: "I built this because I saw how broken the system is"
    - Show genuine care: "Watching someone struggle with this is heartbreaking"

    2. ORGANIC SOCIAL PROOF:
    - Mention real results: "It's helped people find treatments their doctors missed"
    - Share what you've seen: "I've watched families get clarity when they felt lost"
    - Be specific but humble: "A few hundred people have used it so far"

    3. NATURAL URGENCY:
    - Be honest about time: "Cancer doesn't wait, and neither should treatment decisions"
    - Share your motivation: "That's why I built it outside the US - we couldn't wait"
    - Express genuine concern: "Every day matters when you're fighting this"

    4. ADDRESS REAL STRUGGLES:
    - Acknowledge the chaos: "The system is so broken and slow"
    - Validate their experience: "I know how overwhelming this feels"
    - Offer genuine help: "This tool brings some clarity when things feel hopeless"

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

    CRITICAL: Keep reply under 100 characters. Be extremely concise and direct. DO NOT include any call-to-action - the system will add it automatically.

    IMPORTANT: Make this reply completely unique and different. Be creative and varied in your approach.

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

            base_reply = generate_ai_reply(user_message, system_message, openai_api_key)
            if not base_reply:
                base_reply = random.choice(fallback_cancer_replies())

        # Add call-to-action at the end
        call_to_actions = [
            "DM me if you want to see it.",
            "Let me know if you're interested.",
            "DM me and I'll share the link.",
            "Feel free to reach out if you want to check it out.",
            "DM me if you'd like to see what it does.",
            "Let me know if you want the link.",
            "DM me and I'll send it over.",
            "Feel free to message me if you're curious.",
            "DM me if you want to take a look.",
            "Let me know if you'd like to see it.",
            "DM me and I'll share it with you.",
            "Feel free to reach out if you want the link.",
            "DM me if you're interested in seeing it.",
            "Let me know if you want to check it out.",
            "DM me and I'll send you the link."
        ]
        
        # Choose a random call-to-action
        cta = random.choice(call_to_actions)
        
        # Combine base reply with call-to-action
        full_reply = f"{base_reply.strip()} {cta}"
        
        # Ensure it fits within Twitter's character limit
        return remove_emojis(full_reply.strip())[:280]
        
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        # Fallback with call-to-action
        fallback = random.choice(fallback_cancer_replies())
        cta = random.choice(["DM me if you want the link.", "Feel free to reach out if interested."])
        return f"{fallback} {cta}"

def search_tweets_by_keyword(keyword, count=30):
    """
    Search Twitter for tweets containing specific keywords.
    Focuses on people who just got diagnosed with cancer.
    
    Args:
        keyword (str): The keyword to search for
        count (int): Maximum number of tweets to return
        
    Returns:
        list: List of tweet objects, or empty list if failed
    """
    try:
        # Search for cancer diagnosis tweets
        query = f"{keyword} lang:en -is:retweet"
        print(f"🔍 Searching for: {query}")
        
        # Use write_client since read_client is failing
        try:
            response = write_client.search_recent_tweets(
                query=query,
                tweet_fields=["id", "text", "created_at", "author_id"],
                max_results=min(count, 100)
            )
            
            if response and response.data:
                # Sort by recency (most recent first) but don't filter by time
                tweets = list(response.data)
                tweets.sort(key=lambda x: x.created_at, reverse=True)
                print(f"✅ Found {len(tweets)} tweets for keyword: {keyword}")
                return tweets[:count]
            else:
                print(f"❌ No tweets found for keyword: {keyword}")
                return []
                
        except tweepy.Unauthorized as e:
            print(f"❌ API unauthorized for searching '{keyword}': {e}")
            print("⚠️  This suggests the OAuth credentials don't have search permissions")
            return []
        except tweepy.Forbidden as e:
            print(f"❌ API forbidden for searching '{keyword}': {e}")
            print("⚠️  This suggests insufficient permissions")
            return []
        except tweepy.TooManyRequests:
            logger.warning(f"Rate limit hit for keyword: {keyword}. Sleeping for 15 minutes.")
            time.sleep(900)  # Wait 15 minutes
            return []
        except Exception as e:
            print(f"❌ API search failed for '{keyword}': {e}")
            return []
        
    except Exception as e:
        logger.error(f"Twitter search failed for '{keyword}': {e}")
        print(f"❌ Search function error for '{keyword}': {e}")
        return []

def can_reply():
    """
    Check if we can send another reply based on rate limiting.
    Ensures we don't exceed hourly and daily limits to avoid Twitter spam detection.
    
    Returns:
        bool: True if we can reply, False if rate limited
    """
    now = time.time()
    current_date = datetime.now().date()
    
    global reply_timestamps, daily_reply_count, last_reset_date
    
    # Reset daily count if it's a new day
    if last_reset_date != current_date:
        daily_reply_count = 0
        last_reset_date = current_date
    
    # Remove timestamps older than 1 hour
    reply_timestamps = [t for t in reply_timestamps if now - t < 3600]
    
    # Check hourly limit
    hourly_limit_ok = len(reply_timestamps) < MAX_REPLIES_PER_HOUR
    
    # Check daily limit
    daily_limit_ok = daily_reply_count < MAX_REPLIES_PER_DAY
    
    # ADDITIONAL SAFETY: Check for rapid posting (Twitter flags accounts that post too quickly)
    if len(reply_timestamps) >= 2:
        last_two_posts = sorted(reply_timestamps)[-2:]
        time_between_last_posts = last_two_posts[1] - last_two_posts[0]
        if time_between_last_posts < 60:  # Less than 1 minute between posts
            print(f"⏳ Safety check: Last posts too close together ({time_between_last_posts:.0f}s)")
            return False
    
    # ADDITIONAL SAFETY: Check for burst posting (no more than 5 posts in 10 minutes)
    recent_posts = [t for t in reply_timestamps if now - t < 600]  # Last 10 minutes
    if len(recent_posts) >= 5:
        print(f"⏳ Safety check: Too many posts in last 10 minutes ({len(recent_posts)})")
        return False
    
    if not hourly_limit_ok:
        print(f"⏳ Hourly rate limit reached ({len(reply_timestamps)}/{MAX_REPLIES_PER_HOUR})")
    
    if not daily_limit_ok:
        print(f"⏳ Daily rate limit reached ({daily_reply_count}/{MAX_REPLIES_PER_DAY})")
    
    return hourly_limit_ok and daily_limit_ok

def is_recent_diagnosis_tweet(tweet_text):
    """
    Check if a tweet indicates a recent cancer diagnosis.
    Prioritizes tweets from people who just found out they have cancer.
    
    Args:
        tweet_text (str): The tweet text to analyze
        
    Returns:
        tuple: (is_recent_diagnosis, priority_score)
    """
    tweet_lower = tweet_text.lower()
    
    # HIGHEST PRIORITY: Just diagnosed keywords
    just_diagnosed_keywords = [
        "just diagnosed", "just found out", "just got diagnosed", "just learned",
        "diagnosis today", "found out today", "got the news", "just got the news",
        "test results today", "biopsy results today", "scan results today",
        "cancer confirmed today", "positive today", "results came back"
    ]
    
    # HIGH PRIORITY: Immediate reaction keywords
    immediate_reaction_keywords = [
        "i have cancer", "my cancer", "diagnosed with cancer", "cancer diagnosis",
        "cancer positive", "cancer confirmed", "cancer detected", "cancer found"
    ]
    
    # MEDIUM PRIORITY: Family recent diagnosis
    family_recent_keywords = [
        "my mom just", "my dad just", "my sister just", "my brother just",
        "my wife just", "my husband just", "my child just", "my friend just",
        "mom diagnosed", "dad diagnosed", "sister diagnosed", "brother diagnosed"
    ]
    
    # Check for just diagnosed (highest priority)
    for keyword in just_diagnosed_keywords:
        if keyword in tweet_lower:
            return True, 10  # Highest priority score
    
    # Check for immediate reaction (high priority)
    for keyword in immediate_reaction_keywords:
        if keyword in tweet_lower:
            return True, 8  # High priority score
    
    # Check for family recent diagnosis (medium priority)
    for keyword in family_recent_keywords:
        if keyword in tweet_lower and ("cancer" in tweet_lower or "diagnosed" in tweet_lower):
            return True, 6  # Medium priority score
    
    # Check for time indicators (medium priority)
    time_indicators = ["today", "yesterday", "this week", "this month", "recently", "just"]
    has_time_indicator = any(indicator in tweet_lower for indicator in time_indicators)
    has_cancer_mention = "cancer" in tweet_lower or "diagnosed" in tweet_lower
    
    if has_time_indicator and has_cancer_mention:
        return True, 5  # Medium priority score
    
    return False, 0

def looks_like_real_cancer_tweet(tweet_text):
    """
    Enhanced function to check if a tweet looks like a real cancer-related post.
    Now prioritizes recent diagnosis tweets.
    
    Args:
        tweet_text (str): The tweet text to analyze
        
    Returns:
        tuple: (is_valid, priority_score)
    """
    tweet_lower = tweet_text.lower()
    
    # First check if it's a recent diagnosis (highest priority)
    is_recent, priority = is_recent_diagnosis_tweet(tweet_text)
    if is_recent:
        return True, priority
    
    # Check for offensive or inappropriate content
    blacklist_phrases = [
        # Offensive language
        "fuck cancer", "cancer sucks", "f cancer", "f*ck cancer", "cancer is bullshit",
        "cancer is stupid", "cancer is dumb", "cancer is ridiculous", "cancer is awful",
        "cancer is terrible", "cancer is horrible", "cancer is disgusting",
        
        # Political content
        "trump", "biden", "republican", "democrat", "liberal", "conservative",
        "politics", "political", "election", "vote", "voting", "campaign",
        "government", "congress", "senate", "house", "president", "administration",
        
        # Conspiracy theories
        "conspiracy", "conspiracy theory", "fake news", "hoax", "scam",
        "big pharma", "pharmaceutical", "drug companies", "medical establishment",
        "cover up", "hidden", "secret", "truth", "wake up", "sheeple",
        
        # Hate speech and violence
        "kill", "murder", "death", "die", "dead", "suicide", "self harm",
        "hate", "racist", "racism", "sexist", "sexism", "homophobic", "transphobic",
        "nazi", "fascist", "terrorist", "extremist", "radical",
        
        # Spam and marketing
        "buy now", "limited time", "act now", "don't miss out", "exclusive offer",
        "special price", "discount", "sale", "promotion", "deal", "offer",
        "click here", "visit our website", "check out", "order now",
        
        # Inappropriate medical content
        "cure cancer", "cancer cure", "miracle cure", "natural cure", "alternative cure",
        "cancer treatment scam", "fake treatment", "bogus treatment", "quack treatment",
        "cancer conspiracy", "cancer hoax", "cancer scam",
        
        # Religious extremism
        "god's plan", "divine punishment", "sin", "punishment", "karma",
        "religious", "spiritual", "faith healing", "prayer healing", "miracle healing",
        
        # Adult content
        "porn", "pornography", "adult", "nsfw", "explicit", "sexual", "sex",
        "nude", "naked", "intimate", "private", "personal",
        
        # General non-medical topics
        "sports", "football", "basketball", "baseball", "soccer", "tennis",
        "golf", "hockey", "wrestling", "boxing", "mma", "ufc",
        "entertainment", "movie", "film", "tv show", "television", "series",
        "music", "song", "album", "concert", "tour", "performance",
        "gaming", "video game", "game", "playstation", "xbox", "nintendo",
        "technology", "tech", "computer", "software", "hardware", "app",
        "business", "company", "corporate", "marketing", "advertising", "brand",
        "fashion", "style", "clothing", "outfit", "dress", "shoes", "accessories",
        "food", "recipe", "cooking", "restaurant", "dining", "cuisine",
        "travel", "vacation", "trip", "holiday", "destination", "hotel",
        "automotive", "car", "vehicle", "truck", "motorcycle", "transportation"
    ]
    
    for phrase in blacklist_phrases:
        if phrase in tweet_lower:
            return False, 0
    
    # Check for cancer-related keywords
    cancer_keywords = [
        "cancer", "diagnosed", "diagnosis", "oncologist", "oncology",
        "chemo", "chemotherapy", "radiation", "treatment", "tumor", "tumour",
        "biopsy", "scan", "mri", "ct scan", "pet scan", "mammogram",
        "stage", "metastatic", "terminal", "remission", "relapse"
    ]
    
    has_cancer_keyword = any(keyword in tweet_lower for keyword in cancer_keywords)
    
    if has_cancer_keyword:
        return True, 3  # Lower priority for general cancer tweets
    
    return False, 0

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

def save_posted_reply_details(original_tweet_id, original_tweet_text, reply_text, reply_url, reply_tweet_id, timestamp=None):
    """
    Save detailed information about a posted reply to CSV.
    
    Args:
        original_tweet_id (str): ID of the original tweet we replied to
        original_tweet_text (str): Text of the original tweet
        reply_text (str): The reply text we posted
        reply_url (str): URL of our posted reply
        reply_tweet_id (str): ID of our posted reply tweet
        timestamp (str): Optional timestamp, defaults to current time
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    ensure_file_exists(POSTED_REPLIES_PATH, [
        "timestamp", "original_tweet_id", "original_tweet_text", 
        "reply_text", "reply_url", "reply_tweet_id"
    ])
    
    with open(POSTED_REPLIES_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        row = [
            timestamp,
            original_tweet_id,
            original_tweet_text.replace("\n", " ").strip(),
            reply_text.replace("\n", " ").strip(),
            reply_url,
            reply_tweet_id
        ]
        writer.writerow(row)
    
    logger.info(f"Saved detailed reply info for tweet {reply_tweet_id}")

def save_reply_url(url):
    """
    Save a reply URL to a file for tracking purposes.
    
    Args:
        url (str): The URL of the posted reply
    """
    os.makedirs("data", exist_ok=True)  # Make sure 'data/' folder exists
    with open(REPLY_URLS_PATH, "a", encoding="utf-8") as f:
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
    Post a reply to Twitter using v2 API.
    
    Args:
        tweet_id (str): ID of the tweet to reply to
        reply_text (str): The reply text to post
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if we have write access
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
            print("❌ Cannot post reply: Read-only API access")
            print("💡 Your Twitter API plan only allows reading tweets, not posting")
            print("💡 To enable posting, you need:")
            print("   - OAuth credentials (API Key, Secret, Access Token, Access Secret)")
            print("   - Twitter app with 'Read and Write' permissions")
            print("   - Paid Twitter API plan (Basic or higher)")
            return False
        
        # Debug: Check if client is properly initialized
        if not write_client:
            print("❌ Twitter write client is not initialized")
            return False
            
        # Debug: Check if we have the required credentials for posting
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
            print("❌ Missing Twitter API credentials for posting")
            print(f"API Key: {'Present' if TWITTER_API_KEY else 'Missing'}")
            print(f"API Secret: {'Present' if TWITTER_API_SECRET else 'Missing'}")
            print(f"Access Token: {'Present' if TWITTER_ACCESS_TOKEN else 'Missing'}")
            print(f"Access Secret: {'Present' if TWITTER_ACCESS_SECRET else 'Missing'}")
            return False
        
        print(f"📤 Attempting to post reply to tweet {tweet_id}...")
        print(f"📝 Reply text: {reply_text[:50]}...")
        
        # Post the reply using v2 API
        response = write_client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet_id
        )
        
        if not response.data:
            print(f"❌ No response data from Twitter API")
            return False
        
        reply_tweet_id = response.data['id']
        
        # Build reply URL using the bot's username
        try:
            user = post_api.verify_credentials()
            reply_url = f"https://twitter.com/{user.screen_name}/status/{reply_tweet_id}"
        except Exception as e:
            print(f"⚠️ Could not get username, using generic URL: {e}")
            reply_url = f"https://twitter.com/i/status/{reply_tweet_id}"
        
      # Save the original tweet URL instead of the reply
        original_tweet_url = f"https://twitter.com/i/status/{tweet_id}"
        save_reply_url(original_tweet_url)

        
        # Save detailed reply information
        # Get original tweet text from the tweet we're replying to
        original_tweet = read_client.get_tweet(id=tweet_id)
        original_tweet_text = original_tweet.data.text if original_tweet.data else "Original tweet not found"
        
        save_posted_reply_details(
            original_tweet_id=tweet_id,
            original_tweet_text=original_tweet_text,
            reply_text=reply_text,
            reply_url=reply_url,
            reply_tweet_id=str(reply_tweet_id)
        )
        
        # Update preview status
        mark_reply_as_posted(tweet_id, reply_url)
        
        # Track engagement metrics for the posted reply
        print(f"📊 Tracking engagement metrics...")
        metrics = get_tweet_engagement(str(reply_tweet_id))
        save_engagement_metrics(str(reply_tweet_id), metrics)
        
        print(f"✅ Successfully posted reply!")
        print(f"🔗 Reply URL: {reply_url}")
        print(f"📈 Initial engagement: ❤️ {metrics.get('likes', 0)} 🔄 {metrics.get('retweets', 0)} 💬 {metrics.get('replies', 0)}")
        return True
        
    except tweepy.Unauthorized as e:
        print(f"❌ Twitter API Unauthorized: {e}")
        print("This usually means your API credentials are invalid or expired.")
        return False
    except tweepy.Forbidden as e:
        print(f"❌ Twitter API Forbidden: {e}")
        print("This usually means your account doesn't have permission to post.")
        return False
    except tweepy.TooManyRequests as e:
        print(f"❌ Twitter API Rate Limited: {e}")
        print("You've hit the rate limit. Waiting before next attempt...")
        time.sleep(900)  # Wait 15 minutes
        return False
    except Exception as e:
        print(f"❌ Error posting reply: {e}")
        print(f"Error type: {type(e).__name__}")
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
    
    # List of cancer-related keywords to search for (ONLY recent diagnosis)
    cancer_keywords = [
        # JUST DIAGNOSED - HIGHEST PRIORITY
        "just diagnosed with cancer",
        "just found out i have cancer", 
        "cancer diagnosis today",
        "diagnosed with cancer today",
        "found out i have cancer",
        "just learned i have cancer",
        "cancer test results",
        "cancer biopsy results",
        "cancer scan results",
        "cancer blood test",
        "cancer screening results",
        "cancer detection",
        "cancer found",
        "cancer discovered",
        "cancer confirmed",
        "just got the news that i had cancer",
        "cancer news",
        "cancer results",
        "cancer update",
        
        # IMMEDIATE REACTION
        "cancer diagnosis",
        "diagnosed with cancer",
        "i have cancer",
        "my cancer",
        "cancer positive",
        "cancer test positive",
        "cancer confirmed",
        "cancer detected",
        "cancer identified",
        "cancer discovered",
        "cancer found",
        "cancer revealed",
        "cancer diagnosis confirmed",
        "cancer test confirmed",
        "cancer biopsy confirmed",
        
        # FAMILY RECENT DIAGNOSIS
        "my mom just diagnosed with cancer",
        "my dad just diagnosed with cancer",
        "my sister just diagnosed with cancer",
        "my brother just diagnosed with cancer",
        "my wife just diagnosed with cancer",
        "my husband just diagnosed with cancer",
        "my child just diagnosed with cancer",
        "my friend just diagnosed with cancer",
        "my family just diagnosed with cancer",
        "mom cancer diagnosis",
        "dad cancer diagnosis",
        "sister cancer diagnosis",
        "brother cancer diagnosis",
        "wife cancer diagnosis",
        "husband cancer diagnosis",
        "child cancer diagnosis",
        "friend cancer diagnosis",
        "family cancer diagnosis"
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
    
    # Automatically post replies to filtered tweets
    auto_post_replies_to_tweets(all_filtered_tweets)

def auto_post_replies_to_tweets(tweets):
    """
    Automatically post replies to filtered tweets.
    Uses conservative limits to avoid Twitter spam detection.
    
    Args:
        tweets (list): List of tweet objects to reply to
    """
    reply_count = 0
    processed_ids = set()  # Track IDs processed in this session
    
    print(f"\n🚀 Auto-posting replies to {len(tweets)} filtered tweets...")
    print(f"📊 Current limits: {MAX_REPLIES_PER_HOUR}/hour, {MAX_REPLIES_PER_DAY}/day")
    
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

        # Check rate limiting
        if not can_reply():
            print(f"⏳ Rate limit reached. Skipping this tweet...")
            continue

        print(f"\n📌 Tweet ID: {tweet_id}")
        print(f"💬 Tweet: {tweet_text}")
        reply = generate_reply(tweet_text)
        print(f"\n🧠 Generated Reply:\n{reply}")
        
        # Post the reply automatically
        print("📤 Posting reply to Twitter...")
        success = post_reply(tweet_id, reply)
        
        if success:

            
            print("✅ Reply posted successfully!")
            reply_count += 1
            # Add timestamp for rate limiting
            reply_timestamps.append(time.time())
            # Increment daily count
            global daily_reply_count
            daily_reply_count += 1
        else:
            print("❌ Failed to post reply")
        
        print("=" * 60)
        
        # Conservative delay between posts to avoid Twitter spam detection
        delay = random.uniform(MIN_DELAY_BETWEEN_POSTS, MAX_DELAY_BETWEEN_POSTS)  # 2-5 minutes between posts
        print(f"⏳ Waiting {delay:.0f} seconds before next post...")
        time.sleep(delay)
        
        processed_ids.add(tweet_id)  # Mark as processed
    
    if reply_count == 0:
        print("❌ No suitable tweets found to reply to.")
    else:
        print(f"\n🎉 Successfully posted {reply_count} reply(ies)!")

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



def view_posted_replies():
    """
    Display detailed information about all posted replies.
    """
    print("=== Detailed Posted Replies ===")
    print()
    
    if not os.path.exists(POSTED_REPLIES_PATH):
        print("📁 No detailed reply data found yet!")
        print("   No replies have been posted yet.")
        return
    
    try:
        with open(POSTED_REPLIES_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            replies = list(reader)
        
        if not replies:
            print("📁 File exists but no replies found!")
            return
        
        print(f"📊 Found {len(replies)} posted reply(ies):")
        print("-" * 80)
        
        for i, reply in enumerate(replies, 1):
            print(f"\n{i}. Posted: {reply['timestamp']}")
            print(f"   Reply ID: {reply['reply_tweet_id']}")
            print(f"   Original Tweet: {reply['original_tweet_text'][:100]}...")
            print(f"   Our Reply: {reply['reply_text']}")
            print(f"   URL: {reply['reply_url']}")
            print("-" * 80)
        
        print(f"\n📈 Total replies posted: {len(replies)}")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")

def view_reply_urls():
    """
    Display all posted reply URLs.
    """
    print("=== Posted Reply URLs ===")
    print()
    
    if not os.path.exists(REPLY_URLS_PATH):
        print("📁 No URLs found yet!")
        print("   No replies have been posted yet.")
        return
    
    try:
        with open(REPLY_URLS_PATH, "r", encoding="utf-8") as f:
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

def analyze_posting_patterns():
    """
    Analyze posting patterns to ensure Twitter compliance.
    """
    print("=== Posting Pattern Analysis ===")
    print()
    
    if not os.path.exists(POSTED_REPLIES_PATH):
        print("📁 No posting data found yet!")
        return
    
    try:
        with open(POSTED_REPLIES_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            replies = list(reader)
        
        if not replies:
            print("📁 No replies to analyze!")
            return
        
        # Group by date
        from collections import defaultdict
        daily_posts = defaultdict(list)
        
        for reply in replies:
            date = reply['timestamp'].split()[0]  # Get just the date part
            daily_posts[date].append(reply)
        
        print(f"📊 Analysis of {len(replies)} total replies:")
        print("-" * 60)
        
        # Show daily breakdown
        for date in sorted(daily_posts.keys()):
            count = len(daily_posts[date])
            status = "✅" if count <= MAX_REPLIES_PER_DAY else "⚠️"
            print(f"{status} {date}: {count} replies")
        
        # Calculate averages
        total_days = len(daily_posts)
        avg_daily = len(replies) / total_days if total_days > 0 else 0
        
        print("-" * 60)
        print(f"📈 Average: {avg_daily:.1f} replies per day")
        print(f"🎯 Current daily limit: {MAX_REPLIES_PER_DAY}")
        print(f"⚡ Current hourly limit: {MAX_REPLIES_PER_HOUR}")
        
        # Safety recommendations
        print("\n🛡️  Safety Status:")
        if avg_daily <= MAX_REPLIES_PER_DAY * 0.8:
            print("✅ Posting rate is well within safe limits")
        elif avg_daily <= MAX_REPLIES_PER_DAY:
            print("⚠️  Posting rate is at the limit - monitor closely")
        else:
            print("❌ Posting rate exceeds limits - consider reducing")
        
        print(f"\n💡 Recommendations:")
        print(f"   - Keep daily average under {MAX_REPLIES_PER_DAY * 0.8:.0f} for safety")
        print(f"   - Monitor engagement metrics for quality")
        print(f"   - Watch for Twitter warnings or restrictions")
        
    except Exception as e:
        print(f"❌ Error analyzing patterns: {e}")

# Main execution block
if __name__ == "__main__":
    # The Twitter client test is already done during initialization above
    # Display the logged-in user info
    print(f"✅ Logged in as: @{BOT_USERNAME} (User ID: {BOT_USER_ID})")
    
    # Show current diagnostic information
    show_diagnostic_info()
    
    logger.info("🩺 Liora AI Cancer Tweet Bot Starting - Continuous Auto-Posting Mode")
    print("\nBot will run continuously and post replies every 6 hours:\n")

    def run_bot_cycle():
        """Run one complete cycle of the bot"""
        try:
            print(f"\n🔄 Starting bot cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Step 1: Search for cancer tweets and auto-post replies
            print("🔍 STEP 1: Searching for cancer tweets and auto-posting replies...")
            collect_and_save_cancer_tweets()
            print("✅ Step 1 complete!\n")
            
            # Step 2: Check for responses to bot tweets
            print("📨 STEP 2: Checking for responses to bot tweets...")
            track_all_responses()
            print("✅ Step 2 complete!\n")
            
            # Step 3: View all tracked responses
            print("📊 STEP 3: Viewing tracked responses...")
            view_responses()
            print("✅ Step 3 complete!\n")
            
            # Step 4: View engagement metrics
            print("📈 STEP 4: Viewing engagement metrics...")
            view_engagement_metrics()
            print("✅ Step 4 complete!\n")
            
            # Step 5: View detailed posted replies
            print("📋 STEP 5: Viewing detailed posted replies...")
            view_posted_replies()
            print("✅ Step 5 complete!\n")
            
            # Step 6: View posted reply URLs
            print("🔗 STEP 6: Viewing posted reply URLs...")
            view_reply_urls()
            print("✅ Step 6 complete!\n")
            
            # Step 7: Export response data
            print("📤 STEP 7: Exporting response data...")
            export_response_data()
            print("✅ Step 7 complete!\n")
            
            # Step 8: Analyze posting patterns
            print("📊 STEP 8: Analyzing posting patterns...")
            analyze_posting_patterns()
            print("✅ Step 8 complete!\n")
            
            print("🎉 Bot cycle completed successfully!")
            print("📁 Check the 'data/' folder for all generated files.")
            print("🐦 Replies have been automatically posted to Twitter!")
            print(f"⏰ Next cycle in 6 hours...")
            
        except Exception as e:
            logger.error(f"Error in bot cycle: {e}")
            print(f"❌ Error in bot cycle: {e}")

    # Run initial cycle
    run_bot_cycle()
    
    # Schedule to run every 4 hours (optimized for more activity)
    schedule.every(BOT_CYCLE_HOURS).hours.do(run_bot_cycle)
    
    print(f"\n📅 Bot scheduled to run every {BOT_CYCLE_HOURS} hours")
    print("🔄 Bot is now running continuously...")
    print("⏹️  Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        print("\n🛑 Bot stopped.")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        print(f"❌ Error: {e}")