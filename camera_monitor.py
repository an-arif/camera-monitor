import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import threading
import os
from flask import Flask

# ================= CONFIGURATION =================
ELECTION_URL = "https://klop.electionpoll.live/"
NTFY_URL = "https://ntfy.sh/Cam_Down_Alert_v2" 

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

def check_website():
    global minutes_since_last_good, down_cameras_dict
    
    current_time = datetime.now().strftime("%I:%M:%S %p")
    log(f"\n[{current_time}] 🌐 Fetching fresh tokens...")

    try:
        # Use a session so cookies persist between the GET and POST requests
        session = requests.Session()
        
        # 1. First, GET the page to grab fresh ASP.NET tokens
        get_headers = {"User-Agent": HEADERS["User-Agent"]}
        get_response = session.get(ELECTION_URL, headers=get_headers, timeout=15)
        
        soup_get = BeautifulSoup(get_response.text, 'html.parser')
        
        viewstate = soup_get.find("input", {"id": "__VIEWSTATE"})
        viewstategenerator = soup_get.find("input", {"id": "__VIEWSTATEGENERATOR"})
        eventvalidation = soup_get.find("input", {"id": "__EVENTVALIDATION"})
        
        if not (viewstate and viewstategenerator and eventvalidation):
            log("❌ ERROR: Could not find security tokens on the page!")
            return

        # 2. Build the payload dynamically using the fresh tokens
        dynamic_payload = {
            "ScriptManager1": "UpdatePanel2|LinkButton1",
            "__EVENTTARGET": "LinkButton1",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate["value"],
            "__VIEWSTATEGENERATOR": viewstategenerator["value"],
            "__EVENTVALIDATION": eventvalidation["value"],
            "camid": "8606919079", # The mobile number
            "__ASYNCPOST": "true"
        }

        log("✅ Tokens secured! Submitting data...")

        # 3. POST the data to get the camera status
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

        if len(down_cameras_dict) > 0:
            log(f"🚨 Web check found {len(down_cameras_dict)} down cameras!")
            minutes_since_last_good = 15
        else:
            if minutes_since_last_good >= 15:
                log("✅ Sending 'All Good' message to phone...")
                all_good_message = f"✅ [{current_time}] All Good: 0 cameras are down."
                
                # Check exactly what ntfy responds with
                ntfy_response = requests.post(NTFY_URL, data=all_good_message.encode('utf-8'))
                if ntfy_response.status_code != 200:
                    log(f"❌ NTFY REJECTED IT! Error Code: {ntfy_response.status_code} - {ntfy_response.text}")
                
                minutes_since_last_good = 1
            else:
                log(f"All good. Silently waiting. (Minute {minutes_since_last_good}/15)")
                minutes_since_last_good += 1

    except Exception as e:
        log(f"❌ An error occurred: {e}")

def send_bundled_alerts():
    if len(down_cameras_dict) > 0:
        log(f"➡️ Beaming bundled alert to phone...")
        
        lines = ["🚨 CAMERAS STOPPED 🚨"]
        for camera_id, location in down_cameras_dict.items():
            lines.append(f"• {camera_id}: {location}")
            
        alert_message = "\n".join(lines)
        
        try:
            requests.post(NTFY_URL, data=alert_message.encode('utf-8'), timeout=5)
        except Exception as e:
            log(f"Failed to send notification: {e}")

def run_monitor():
    log("=====================================")
    log("🛡️ Camera Monitoring Service Started")
    log("=====================================")
    requests.post(NTFY_URL, data="🤖 Camera Monitoring Script has restarted!".encode('utf-8'))

    minutes_down = 0

    while True:
        check_website()
        
        if len(down_cameras_dict) > 0:
            if minutes_down % 10 == 0:
                send_bundled_alerts()
            minutes_down += 1
        else:
            minutes_down = 0
            
        time.sleep(60)

# --- FLASK WEB ROUTES ---
@app.route('/')
def home():
    log_text = "<br>".join(terminal_logs)
    html = f"""
    <html>
        <head>
            <title>Monitor Shell</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ background-color: #121212; color: #00ff00; font-family: monospace; padding: 20px; font-size: 16px; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <h2>Live Monitor Terminal</h2>
            <div>{log_text}</div>
        </body>
    </html>
    """
    return html

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=run_monitor)
    monitor_thread.daemon = True 
    monitor_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)