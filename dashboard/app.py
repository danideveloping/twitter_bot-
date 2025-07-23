from flask import Flask, render_template, jsonify, request
import csv
import os
import json
from datetime import datetime
import time

app = Flask(__name__)

# File paths (point to parent directory where bot creates data)
POSTED_REPLIES_PATH = "../data/posted_replies.csv"
REPLY_URLS_PATH = "../data/reply_urls.txt"
ENGAGEMENT_METRICS_PATH = "../data/engagement_metrics.csv"
RESPONSES_TRACKING_PATH = "../data/responses_tracking.csv"

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/replies')
def get_replies():
    """API endpoint to get posted replies"""
    replies = []
    
    if os.path.exists(POSTED_REPLIES_PATH):
        try:
            with open(POSTED_REPLIES_PATH, 'r', encoding='utf-8') as f:
                # Read CSV without headers and assign column names
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 5:  # Ensure we have enough columns
                        reply = {
                            'timestamp': row[0],
                            'original_tweet_id': row[1],
                            'original_tweet_text': row[2],
                            'reply_text': row[3],
                            'reply_url': row[4],
                            'reply_tweet_id': row[5] if len(row) > 5 else ''
                        }
                        replies.append(reply)
        except Exception as e:
            print(f"Error reading replies: {e}")
    
    # Sort by timestamp (newest first)
    replies.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return jsonify(replies)

@app.route('/api/urls')
def get_urls():
    """API endpoint to get reply URLs"""
    urls = []
    
    if os.path.exists(REPLY_URLS_PATH):
        try:
            with open(REPLY_URLS_PATH, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            print(f"Error reading URLs: {e}")
    
    return jsonify(urls)

@app.route('/api/engagement')
def get_engagement():
    """API endpoint to get engagement metrics"""
    engagement = []
    
    if os.path.exists(ENGAGEMENT_METRICS_PATH):
        try:
            with open(ENGAGEMENT_METRICS_PATH, 'r', encoding='utf-8') as f:
                # Read CSV without headers and assign column names
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 6:  # Ensure we have enough columns
                        record = {
                            'tweet_id': row[0],
                            'timestamp': row[1],
                            'likes': row[2],
                            'retweets': row[3],
                            'replies': row[4],
                            'quotes': row[5]
                        }
                        engagement.append(record)
        except Exception as e:
            print(f"Error reading engagement: {e}")
    
    return jsonify(engagement)

@app.route('/api/responses')
def get_responses():
    """API endpoint to get responses to bot tweets"""
    responses = []
    
    if os.path.exists(RESPONSES_TRACKING_PATH):
        try:
            with open(RESPONSES_TRACKING_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                responses = list(reader)
        except Exception as e:
            print(f"Error reading responses: {e}")
    
    return jsonify(responses)

@app.route('/api/stats')
def get_stats():
    """API endpoint to get overall statistics"""
    stats = {
        'total_replies': 0,
        'total_urls': 0,
        'total_engagement_records': 0,
        'total_responses': 0,
        'last_updated': None
    }
    
    # Count replies
    if os.path.exists(POSTED_REPLIES_PATH):
        try:
            with open(POSTED_REPLIES_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                replies = list(reader)
                stats['total_replies'] = len(replies)
                if replies:
                    stats['last_updated'] = replies[0][0] if len(replies[0]) > 0 else ''
        except Exception as e:
            print(f"Error counting replies: {e}")
    
    # Count URLs
    if os.path.exists(REPLY_URLS_PATH):
        try:
            with open(REPLY_URLS_PATH, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
                stats['total_urls'] = len(urls)
        except Exception as e:
            print(f"Error counting URLs: {e}")
    
    # Count engagement records
    if os.path.exists(ENGAGEMENT_METRICS_PATH):
        try:
            with open(ENGAGEMENT_METRICS_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                engagement = list(reader)
                stats['total_engagement_records'] = len(engagement)
        except Exception as e:
            print(f"Error counting engagement: {e}")
    
    # Count responses
    if os.path.exists(RESPONSES_TRACKING_PATH):
        try:
            with open(RESPONSES_TRACKING_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                responses = list(reader)
                stats['total_responses'] = len(responses)
        except Exception as e:
            print(f"Error counting responses: {e}")
    
    return jsonify(stats)

if __name__ == '__main__':
    # Get port from environment variable (for Render deployment)
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 