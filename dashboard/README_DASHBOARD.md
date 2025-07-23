# Twitter Bot Web Dashboard

A real-time web dashboard to monitor your Twitter bot's activity, posted replies, and engagement metrics.

## 🚀 Quick Start

### Option 1: Start Both Bot and Dashboard Together
```bash
python start_dashboard.py
```

### Option 2: Start Dashboard Only (if bot is already running)
```bash
python app.py
```

### Option 3: Start Bot Only (if you don't need the dashboard)
```bash
python twitter_bot.py
```

## 🌐 Access the Dashboard

Once started, open your web browser and go to:
```
http://localhost:5000
```

## 📊 Dashboard Features

### Real-Time Statistics
- **Total Replies**: Number of replies posted by the bot
- **Reply URLs**: Number of reply URLs tracked
- **Engagement Records**: Number of engagement metrics tracked
- **Responses Received**: Number of responses to bot tweets

### Live Data Tabs

#### 1. **Posted Replies Tab**
- Shows all replies posted by the bot
- Displays original tweet text and bot's reply
- Includes timestamps and direct links to Twitter
- Sorted by newest first

#### 2. **Reply URLs Tab**
- Lists all reply URLs for easy access
- Clickable links that open in new tabs
- Numbered for easy reference

#### 3. **Engagement Tab**
- Shows engagement metrics for bot tweets
- Displays likes, retweets, replies, and quotes
- Tracks performance over time

#### 4. **Responses Tab**
- Shows responses received from other users
- Displays response text and author information
- Tracks engagement with the bot

### Auto-Refresh
- Dashboard automatically refreshes every 30 seconds
- Manual refresh button available
- Live status indicator shows system is running

## 🔧 Technical Details

### Files Created
- `app.py` - Flask web application
- `templates/dashboard.html` - Dashboard HTML template
- `start_dashboard.py` - Startup script for both services

### Dependencies Added
- `flask==2.3.3` - Web framework for the dashboard

### Data Sources
The dashboard reads from the same data files as the bot:
- `data/posted_replies.csv` - Detailed reply information
- `data/reply_urls.txt` - List of reply URLs
- `data/engagement_metrics.csv` - Engagement data
- `data/responses_tracking.csv` - Response tracking

## 🎯 Use Cases

### Monitor Bot Activity
- See how many replies the bot has posted
- Track engagement with bot tweets
- Monitor responses from users

### Quality Control
- Review posted replies for quality
- Check if replies are being posted correctly
- Monitor for any issues or errors

### Performance Tracking
- Track engagement metrics over time
- See which replies get the most engagement
- Monitor bot performance and effectiveness

### Easy Access
- Quick access to all reply URLs
- No need to dig through files
- Real-time updates as bot runs

## 🛠️ Customization

### Change Port
To run the dashboard on a different port, edit `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Change 5000 to your preferred port
```

### Change Refresh Rate
To change auto-refresh interval, edit `templates/dashboard.html`:
```javascript
refreshInterval = setInterval(loadAllData, 60000);  // Change 30000 to your preferred interval (in milliseconds)
```

### Add New Data Sources
To add new data sources, create new API endpoints in `app.py` and corresponding tabs in `dashboard.html`.

## 🔒 Security Notes

- Dashboard runs on `localhost` by default (not accessible from outside)
- For production use, consider adding authentication
- Dashboard only reads data files (doesn't modify bot data)

## 🐛 Troubleshooting

### Dashboard Won't Start
- Check if Flask is installed: `pip install flask`
- Ensure port 5000 is not in use by another application
- Check console for error messages

### No Data Showing
- Ensure the bot has been running and posting replies
- Check that data files exist in the `data/` folder
- Verify file permissions allow reading the data files

### Dashboard Not Updating
- Check browser console for JavaScript errors
- Ensure the bot is actively posting new replies
- Try manual refresh button

## 📱 Mobile Friendly

The dashboard is responsive and works on:
- Desktop browsers
- Mobile phones
- Tablets
- Any device with a web browser

## 🎨 Design Features

- Modern, clean interface
- Gradient backgrounds and smooth animations
- Hover effects and visual feedback
- Color-coded tabs and cards
- Professional typography and spacing 