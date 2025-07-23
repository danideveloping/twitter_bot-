import subprocess
import sys
import time
import threading
import os

def run_bot():
    """Run the Twitter bot in a separate process"""
    print("🤖 Starting Twitter Bot...")
    try:
        # Run bot from parent directory
        subprocess.run([sys.executable, "../twitter_bot.py"], check=True)
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")

def run_dashboard():
    """Run the web dashboard in a separate process"""
    print("🌐 Starting Web Dashboard...")
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
        print("🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Dashboard error: {e}")

def main():
    print("🚀 Starting Twitter Bot Dashboard System")
    print("=" * 50)
    
    # Check if required files exist
    if not os.path.exists("../twitter_bot.py"):
        print("❌ twitter_bot.py not found in parent directory!")
        return
    
    if not os.path.exists("app.py"):
        print("❌ app.py not found!")
        return
    
    print("📋 System Components:")
    print("   🤖 Twitter Bot (twitter_bot.py)")
    print("   🌐 Web Dashboard (app.py)")
    print("   📁 Data files in data/ folder")
    print()
    
    print("🎯 Starting both services...")
    print("   - Bot will run continuously and post replies")
    print("   - Dashboard will be available at http://localhost:5000")
    print("   - Press Ctrl+C to stop both services")
    print()
    
    # Start both processes in separate threads
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    
    try:
        # Start the dashboard first (it's faster to start)
        dashboard_thread.start()
        time.sleep(2)  # Give dashboard time to start
        
        # Then start the bot
        bot_thread.start()
        
        print("✅ Both services started successfully!")
        print("🌐 Dashboard: http://localhost:5000")
        print("🤖 Bot: Running in background")
        print()
        print("⏹️  Press Ctrl+C to stop all services")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        print("✅ Services stopped")

if __name__ == "__main__":
    main() 