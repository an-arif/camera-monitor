import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import threading
import os
from flask import Flask

# ================= CONFIGURATION =================
ELECTION_URL = "https://klop.electionpoll.live/"
NTFY_URL = "https://ntfy.sh/Cam_Down_Alert"

PAYLOAD = {
    "ScriptManager1": "UpdatePanel2|LinkButton1",
    "__EVENTTARGET": "LinkButton1",
    "__EVENTARGUMENT": "",
    "__VIEWSTATE": "/wEPDwUKLTE3ODYwNTY2OQ9kFgICAw9kFgICBA9kFgJmD2QWBAIJDxBkZBYAZAILDxQrAAJkZGQYAQUJbGlzdHZpZXcxD2dk/9WdmbnKh33QRIEKJv1Y//54OuBVKTJEpXv6Zia8/pk=",
    "__VIEWSTATEGENERATOR": "CA0B0334",
    "__EVENTVALIDATION": "/wEdAAO8/WvpZ9AukelgAXKaRK00ogk53zDmaFecvD6BjQ87rLU3zaTs9Ah+Lyp4AX88QyG4dVnxddWEfq9aGhv0oQ+Fa6VgPzmhScpa8oW5isGj6A==",
    "camid": "8606919079",
    "__ASYNCPOST": "true"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}
# =================================================

# Flask App Setup
app = Flask(__name__)

# State Variables
minutes_since_last_good = 15 
down_cameras_dict = {}
terminal_logs = []  # This list stores our terminal output

def log(message):
    """Prints to the real terminal AND saves to our web terminal"""
    print(message)
    terminal_logs.append(message)
    # Keep only the last 50 lines so the web page doesn't lag over time
    if len(terminal_logs) > 50:
        terminal_logs.pop(0)

def check_website():
    global minutes_since_last_good, down_cameras_dict
    
    current_time = datetime.now().strftime("%I:%M:%S %p")
    log(f"\n[{current_time}] 🌐 Checking website for updates...")

    try:
        response = requests.post(ELECTION_URL, data=PAYLOAD, headers=HEADERS, timeout=15)
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

        if len(down_cameras_dict) > 0:
            log(f"🚨 Web check found {len(down_cameras_dict)} down cameras!")
            minutes_since_last_good = 15
        else:
            if minutes_since_last_good >= 15:
                log("✅ Sending 'All Good' message to phone...")
                all_good_message = f"✅ [{current_time}] All Good: 0 cameras are down."
                requests.post(NTFY_URL, data=all_good_message.encode('utf-8'))
                minutes_since_last_good = 1
            else:
                log(f"All good. Silently waiting. (Minute {minutes_since_last_good}/15)")
                minutes_since_last_good += 1

    except Exception as e:
        log(f"An error occurred: {e}")

def send_alerts():
    if len(down_cameras_dict) > 0:
        log(f"➡️ Beaming alerts to phone...")
        for camera_id, location in down_cameras_dict.items():
            alert_message = f"🚨 Camera STOPPED!\nID: {camera_id}\nLocation: {location}"
            try:
                requests.post(NTFY_URL, data=alert_message.encode('utf-8'), timeout=5)
            except Exception as e:
                log(f"Failed to send notification: {e}")

def run_monitor():
    """This is the infinite loop that runs in the background thread"""
    log("=====================================")
    log("🛡️ Camera Monitoring Service Started")
    log("=====================================")
    requests.post(NTFY_URL, data="🤖 Camera Monitoring Script has started!".encode('utf-8'))

    while True:
        check_website()
        send_alerts()
        time.sleep(30)
        
        if len(down_cameras_dict) > 0:
            log(f"\n[{datetime.now().strftime('%I:%M:%S %p')}] ⏱️ 30-Second Reminder!")
            send_alerts()
            
        time.sleep(30)

# --- FLASK WEB ROUTES ---
@app.route('/')
def home():
    """Serves the live terminal to the web browser"""
    # Join all logs with HTML line breaks
    log_text = "<br>".join(terminal_logs)
    
    # Simple HTML/CSS to make it look like a terminal that auto-refreshes every 5 seconds
    html = f"""
    <html>
        <head>
            <title>Monitor Shell</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ background-color: #121212; color: #00ff00; font-family: monospace; padding: 20px; font-size: 16px; }}
            </style>
        </head>
        <body>
            <h2>Live Monitor Terminal</h2>
            <div>{log_text}</div>
        </body>
    </html>
    """
    return html

# ================= STARTUP =================
if __name__ == '__main__':
    # 1. Start the background worker loop in a separate thread so it doesn't block Flask
    monitor_thread = threading.Thread(target=run_monitor)
    monitor_thread.daemon = True # This ensures the thread dies when Flask shuts down
    monitor_thread.start()
    
    # 2. Start the Flask Web Server
    # Render assigns a dynamic port, so we check for it, otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)