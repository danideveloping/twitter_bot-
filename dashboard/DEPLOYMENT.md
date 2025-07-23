# Dashboard Deployment Guide

## 🚀 Deploy to Render

### Option 1: Deploy via Render Dashboard (Recommended)

1. **Go to Render Dashboard**
   - Visit https://dashboard.render.com
   - Sign in to your account

2. **Create New Web Service**
   - Click "New +" button
   - Select "Web Service"
   - Connect your GitHub repository

3. **Configure Service**
   - **Name**: `twitter-bot-dashboard`
   - **Root Directory**: `dashboard` (if your dashboard files are in a subfolder)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

4. **Environment Variables** (if needed)
   - Add any environment variables your dashboard needs

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy your dashboard

### Option 2: Deploy via render.yaml (Automatic)

If you have the `render.yaml` file in your repository:

1. **Push to GitHub**
   - Make sure all dashboard files are committed and pushed

2. **Connect Repository**
   - Go to Render Dashboard
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file

3. **Auto-Deploy**
   - Render will automatically create the service based on the configuration

## 🌐 Access Your Dashboard

Once deployed, your dashboard will be available at:
```
https://your-dashboard-name.onrender.com
```

## 📁 Required Files for Deployment

Make sure these files are in your `dashboard/` folder:
- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `runtime.txt` - Python version
- `render.yaml` - Render configuration
- `templates/dashboard.html` - Dashboard template

## 🔧 Configuration Options

### Change Dashboard Name
Edit `render.yaml`:
```yaml
services:
  - type: web
    name: your-custom-name  # Change this
```

### Change Python Version
Edit `runtime.txt`:
```
python-3.11.0  # Change to your preferred version
```

### Add Environment Variables
Edit `render.yaml`:
```yaml
services:
  - type: web
    name: twitter-bot-dashboard
    envVars:
      - key: YOUR_VAR
        value: your_value
```

## 🐛 Troubleshooting

### Dashboard Not Loading
- Check Render logs for errors
- Ensure all required files are in the correct location
- Verify the start command is correct

### Data Not Showing
- Make sure your bot is running and creating data files
- Check that the dashboard can access the data files
- Verify file paths are correct

### Build Errors
- Check that `requirements.txt` includes all dependencies
- Ensure Python version is compatible
- Review build logs for specific errors

## 💡 Tips

1. **Free Tier**: Render's free tier is perfect for testing
2. **Auto-Deploy**: Every push to your main branch will trigger a new deployment
3. **Logs**: Check Render logs for debugging information
4. **Custom Domain**: You can add a custom domain later if needed

## 🔗 Connect with Your Bot

If your bot is also deployed on Render:
- Both services can run simultaneously
- Dashboard will read data from your bot's data files
- You can monitor bot activity in real-time 