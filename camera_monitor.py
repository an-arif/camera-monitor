import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import threading
import os
from flask import Flask

# ================= CONFIGURATION =================
ELECTION_URL = "https://klop.electionpoll.live/"

# Your exact Discord Webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1491694602661662801/Pzp_kfOVyxObEqGYbXQN7yZLHoLfS_PKydkKJh2SwbrQ63fIam9imdHYtPdJd2sY9SBM"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}
# =================================================

app = Flask(__name__)

# State Variables
minutes_since_last_good = 15 
down_cameras_dict = {}
terminal_logs = []  

def log(message):
    """Prints to the real terminal AND saves to our web terminal"""
    print(message)
    terminal_logs.append(message)
    if len(terminal_logs) > 50:
        terminal_logs.pop(0)

def send_discord_message(message_text):
    """Sends a formatted message to your private Discord server"""
    payload = {"content": message_text}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code not in [200, 204]:
            log(f"❌ Discord Error: {response.status_code} - {response.text}")
    except Exception as e:
        log(f"❌ Failed to reach Discord: {e}")

def check_website():
    global minutes_since_last_good, down_cameras_dict
    
    current_time = datetime.now().strftime("%I:%M:%S %p")
    log(f"\n[{current_time}] 🌐 Fetching fresh tokens...")

    try:
        # 1. Grab fresh ASP.NET tokens
        session = requests.Session()
        get_headers = {"User-Agent": HEADERS["User-Agent"]}
        get_response = session.get(ELECTION_URL, headers=get_headers, timeout=15)
        soup_get = BeautifulSoup(get_response.text, 'html.parser')
        
        viewstate = soup_get.find("input", {"id": "__VIEWSTATE"})
        viewstategenerator = soup_get.find("input", {"id": "__VIEWSTATEGENERATOR"})
        eventvalidation = soup_get.find("input", {"id": "__EVENTVALIDATION"})
        
        if not (viewstate and viewstategenerator and eventvalidation):
            log("❌ ERROR: Could not find security tokens on the page!")
            return

        # 2. Build payload
        dynamic_payload = {
            "ScriptManager1": "UpdatePanel2|LinkButton1",
            "__EVENTTARGET": "LinkButton1",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate["value"],
            "__VIEWSTATEGENERATOR": viewstategenerator["value"],
            "__EVENTVALIDATION": eventvalidation["value"],
            "camid": "8606919079",
            "__ASYNCPOST": "true"
        }

        log("✅ Tokens secured! Submitting data...")

        # 3. Post data and parse cameras
        response = session.post(ELECTION_URL, data=dynamic_payload, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            log(f"Server returned status {response.status_code}. Retrying later.")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        red_cameras = soup.find_all('a', class_='btn-danger')
        
        down_cameras_dict.clear()
        for camera in red_cameras:
            camera_id = camera.text.strip()
            location = camera.get('data-original-title', 'Unknown Location')
            down_cameras_dict[camera_id] = location

        # 4. Handle Timers
        if len(down_cameras_dict) > 0:
            log(f"🚨 Web check found {len(down_cameras_dict)} down cameras!")
            minutes_since_last_good = 15 
        else:
            if minutes_since_last_good >= 15:
                log("✅ Sending 'All Good' message to Discord...")
                all_good_message = f"✅ **[{current_time}] All Good:** 0 cameras are down. Everything is running smoothly."
                send_discord_message(all_good_message)
                minutes_since_last_good = 1
            else:
                log(f"All good. Silently waiting. (Minute {minutes_since_last_good}/15)")
                minutes_since_last_good += 1

    except Exception as e:
        log(f"❌ An error occurred: {e}")

def send_bundled_alerts():
    if len(down_cameras_dict) > 0:
        log(f"➡️ Beaming bundled alert to Discord...")
        
        lines = ["🚨 **CAMERAS STOPPED** 🚨"]
        for camera_id, location in down_cameras_dict.items():
            lines.append(f"• **{camera_id}**: {location}")
            
        alert_message = "\n".join(lines)
        send_discord_message(alert_message)

def run_monitor():
    log("=====================================")
    log("🛡️ Camera Monitoring Service Started")
    log("=====================================")
    send_discord_message("🤖 **Camera Monitoring Script has restarted successfully!**")

    while True:
        check_website()
        
        if len(down_cameras_dict) > 0:
            send_bundled_alerts()
            time.sleep(30)
            log(f"\n[{datetime.now().strftime('%I:%M:%S %p')}] ⏱️ 30-Second Reminder!")
            send_bundled_alerts()
            time.sleep(30)
        else:
            time.sleep(60)

# --- FLASK WEB ROUTES ---

# 1. The Route that handles the button click
@app.route('/test-alert', methods=['POST'])
def test_alert():
    current_time = datetime.now().strftime("%I:%M:%S %p")
    log(f"\n[{current_time}] 🧪 Manual test triggered from web interface!")
    send_discord_message("🧪 **TEST ALERT:** The manual test button on your web dashboard was clicked! Notifications are working perfectly.")
    return "Success", 200

# 2. The Main Page
@app.route('/')
def home():
    log_text = "<br>".join(terminal_logs)
    
    # We added CSS for the button and a Javascript fetch() command to click it without reloading
    html = f"""
    <html>
        <head>
            <title>Monitor Shell</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ background-color: #121212; color: #00ff00; font-family: monospace; padding: 20px; font-size: 16px; line-height: 1.5; }}
                .test-btn {{ background-color: #00ff00; color: #121212; border: none; padding: 10px 20px; font-size: 16px; font-weight: bold; cursor: pointer; margin-bottom: 20px; border-radius: 5px; }}
                .test-btn:hover {{ background-color: #00cc00; }}
                .test-btn:active {{ background-color: #ffffff; }}
            </style>
        </head>
        <body>
            <h2>Live Monitor Terminal</h2>
            <button class="test-btn" onclick="fetch('/test-alert', {{method: 'POST'}})">🧪 Send Test Discord Alert</button>
            <div>{log_text}</div>
        </body>
    </html>
    """
    return html

# ================= STARTUP =================
if __name__ == '__main__':
    monitor_thread = threading.Thread(target=run_monitor)
    monitor_thread.daemon = True 
    monitor_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
