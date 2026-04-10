import time
import json
import threading
import os
import sys
import psutil
import socket
import subprocess
import serial
import csv
import shutil
import random
import re
import gzip
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_socketio import SocketIO

from AtmosTrend import AtmosTrend
from AtmosInsights import AtmosInsights

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "historical_logs")
CONFIG_FILE = os.path.join(BASE_DIR, "atmos_config.json")
POLL_INTERVAL = 2
BOOT_TIME = psutil.boot_time()
PORT = 8080

# --- STRICT HARDWARE IMPORTS ---
HAVE_BME = False
try:
    import board
    import busio
    import adafruit_bme680
    HAVE_BME = True
    print("[SYSTEM] BME680/688 libraries detected.")
except ImportError:
    print("[WARN] BME680 libraries missing. Environmental data will report 0.")

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception: return "127.0.0.1"

def get_wifi_info():
    ssid = "Ethernet / Unknown"
    signal = "0 dBm"
    try:
        output = subprocess.check_output("iwconfig", shell=True).decode()
        if "ESSID:" in output: ssid = output.split('ESSID:"')[1].split('"')[0]
        if "Signal level=" in output: signal = output.split("Signal level=")[1].split(" ")[0] + " dBm"
    except: pass
    return ssid, signal

def pm25_to_aqi_cpcb(pm25):
    if pm25 is None or pm25 <= 0: return 0, "Unknown"
    c = float(pm25)
    breakpoints = [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200), (91, 120, 201, 300), (121, 250, 301, 400), (251, 500, 401, 500)]
    aqi = 500
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= c <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (c - c_low) + i_low
            break
    aqi = round(aqi)
    if aqi <= 50: cat = "Good"
    elif aqi <= 100: cat = "Satisfactory"
    elif aqi <= 200: cat = "Moderate"
    elif aqi <= 300: cat = "Poor"
    elif aqi <= 400: cat = "Very Poor"
    else: cat = "Severe"
    return aqi, cat

class IAQProcessor:
    def process(self, raw_data):
        if not raw_data: return {}
        pm25 = raw_data.get('pm25', 0)
        aqi_val, aqi_cat = pm25_to_aqi_cpcb(pm25)
        return {'aqi': aqi_val, 'aqi_category': aqi_cat}

class SensorManager:
    def __init__(self):
        self.bme = None
        self.ser = None
        self.status = "Init"
        self._init_hardware()

    def _init_hardware(self):
        if HAVE_BME:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.bme = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x76)
            except Exception as e:
                print(f"[ERROR] BME688 Initialization Failed: {e}")
        try:
            port = '/dev/serial0' if os.path.exists('/dev/serial0') else '/dev/ttyAMA0'
            self.ser = serial.Serial(port, 9600, timeout=2)
        except Exception as e:
            print(f"[ERROR] PMS5003 Serial Initialization Failed: {e}")
            self.status = "Serial Error"
        if self.bme or self.ser: self.status = "OK"

    def read_pms_raw(self):
        if not self.ser: return None, None, None
        try:
            self.ser.reset_input_buffer()
            start = time.time()
            while (time.time() - start) < 1.5:
                if self.ser.read() == b'\x42' and self.ser.read() == b'\x4D':
                    frame = b'\x42\x4D' + self.ser.read(30)
                    if len(frame) == 32:
                        return frame[10] << 8 | frame[11], frame[12] << 8 | frame[13], frame[14] << 8 | frame[15]
        except Exception: pass
        return None, None, None

    def read(self):
        data = { 'temperature': 0, 'humidity': 0, 'pressure': 0, 'pm1': 0, 'pm25': 0, 'pm10': 0, 'gas_resistance': 0 }
        if self.bme:
            try:
                data['temperature'] = round(self.bme.temperature, 1)
                data['humidity'] = int(self.bme.relative_humidity)
                data['pressure'] = int(self.bme.pressure)
                data['gas_resistance'] = int(self.bme.gas)
            except: pass
        
        p1, p25, p10 = self.read_pms_raw()
        if p25 is not None:
            data['pm1'], data['pm25'], data['pm10'] = p1, p25, p10
        return data

class AtmosEngine:
    def __init__(self, socket_server):
        self.io = socket_server 
        self.sensors = SensorManager()
        self.processor = IAQProcessor()
        self.trend_engine = AtmosTrend(buffer_size=120)
        self.insights_engine = AtmosInsights()
        
        self.latest_data = {
            'temperature': 0, 'humidity': 0, 'pressure': 0, 
            'pm1': 0, 'pm25': 0, 'pm10': 0, 'gas_resistance': 0,
            'aqi': 0, 'aqi_category': 'Unknown',
            'trend_analysis': {}, 'state': 'BOOT'
        }
        
        self.tunnel_process = None
        self.tunnel_url = ""
        self.tunnel_active = False
        
        self.config = {
            "telegram_token": "", "telegram_chat_id": "", 
            "alerts_enabled": False, "alert_threshold": 100,
            "latitude": "9.9312", "longitude": "76.2673"
        }
        self.load_config()
        self.last_alert_time = 0
        self.alert_history = []
        
        self.outdoor_data = {"temperature": None, "humidity": None, "pm25": None, "aqi": None, "last_sync": "Never"}
        
        if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
        
        # 10-Year Data Retention (3650 days)
        self.retention_days = 3650
        
        threading.Thread(target=self.auto_maintenance_loop, daemon=True).start()
        threading.Thread(target=self.outdoor_weather_loop, daemon=True).start()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: self.config.update(json.load(f))
            except Exception: pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f)
        except Exception: pass

    def log_alert(self, message, level="info"):
        now = datetime.now().strftime("%H:%M:%S")
        self.alert_history.insert(0, {"time": now, "message": message, "level": level})
        self.alert_history = self.alert_history[:10]  

    def start_tunnel(self):
        if self.tunnel_active: return self.tunnel_url
        try:
            self.tunnel_process = subprocess.Popen(["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            self.tunnel_active = True
            threading.Thread(target=self._monitor_tunnel_logs, daemon=True).start()
            return "Initializing..."
        except FileNotFoundError: return "Error"

    def stop_tunnel(self):
        if self.tunnel_process: self.tunnel_process.terminate()
        self.tunnel_process, self.tunnel_active, self.tunnel_url = None, False, ""

    def _monitor_tunnel_logs(self):
        url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        for line in iter(self.tunnel_process.stderr.readline, ''):
            if not line: break
            match = url_regex.search(line)
            if match: self.tunnel_url = match.group(0)

    # Open-Meteo API Background Fetcher
    def outdoor_weather_loop(self):
        while True:
            lat = self.config.get("latitude")
            lon = self.config.get("longitude")
            if lat and lon:
                try:
                    w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m"
                    a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,us_aqi"
                    w_res = requests.get(w_url, timeout=10).json()
                    a_res = requests.get(a_url, timeout=10).json()
                    
                    self.outdoor_data = {
                        "temperature": w_res.get("current", {}).get("temperature_2m"),
                        "humidity": w_res.get("current", {}).get("relative_humidity_2m"),
                        "pm25": a_res.get("current", {}).get("pm2_5"),
                        "aqi": a_res.get("current", {}).get("us_aqi"),
                        "last_sync": datetime.now().strftime("%H:%M")
                    }
                except Exception as e:
                    print(f"[WARN] Open-Meteo fetch failed: {e}")
            time.sleep(900) # Fetch every 15 minutes

    def compress_old_logs(self):
        if not os.path.exists(LOG_DIR): return
        now = datetime.now()
        for root, dirs, files in os.walk(LOG_DIR):
            for name in files:
                if name.endswith('.csv'):
                    if name == f"{now.strftime('%d')}.csv" and f"{now.strftime('%Y')}/{now.strftime('%m')}" in root.replace('\\', '/'): continue
                    filepath = os.path.join(root, name)
                    try:
                        with open(filepath, 'rb') as f_in, gzip.open(filepath + '.gz', 'wb') as f_out: shutil.copyfileobj(f_in, f_out)
                        os.remove(filepath)
                    except Exception: pass

    def cleanup_old_logs(self):
        if not os.path.exists(LOG_DIR): return
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for root, dirs, files in os.walk(LOG_DIR, topdown=False):
            for name in files:
                filepath = os.path.join(root, name)
                if (name.endswith('.csv') or name.endswith('.csv.gz')) and datetime.fromtimestamp(os.path.getmtime(filepath)) < cutoff:
                    try: os.remove(filepath)
                    except: pass
            for name in dirs:
                if not os.listdir(os.path.join(root, name)): 
                    try: os.rmdir(os.path.join(root, name))
                    except: pass

    def auto_maintenance_loop(self):
        while True:
            now = datetime.now()
            if now.hour == 2 and now.minute == 0:
                self.compress_old_logs(); self.cleanup_old_logs(); time.sleep(61) 
            time.sleep(30)
                
    def update_loop(self):
        while True:
            raw = self.sensors.read()
            processed = self.processor.process(raw)
            self.trend_engine.update(temperature=raw.get('temperature', 0), humidity=raw.get('humidity', 0), pm25=raw.get('pm25', 0), pm10=raw.get('pm10', 0), gas_resistance=raw.get('gas_resistance', 0))
            analysis = self.trend_engine.analyze()

            self.latest_data = {
                **raw, 'aqi': processed.get('aqi', 0), 'aqi_category': processed.get('aqi_category', 'Unknown'),
                'trend_analysis': analysis, 'state': analysis.get('fsm_state', 'NORMAL')
            }
            
            aqi_val = processed.get('aqi', 0)
            if self.config.get("alerts_enabled"):
                threshold = int(self.config.get("alert_threshold", 100))
                if aqi_val >= threshold and time.time() - self.last_alert_time > 3600:
                    msg = f"AQI reached {aqi_val}! Trend: {analysis.get('trend_direction', 'Unknown')}"
                    self.log_alert(msg, "critical")
                    self.last_alert_time = time.time()
            
            self.log_data(self.latest_data)
            
            d = self.latest_data
            live_payload = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "sensors": {"temperature": d.get('temperature', 0), "humidity": d.get('humidity', 0), "pressure": d.get('pressure', 0), "pm1": d.get('pm1', 0), "pm25": d.get('pm25', 0), "pm10": d.get('pm10', 0), "gas_resistance": d.get('gas_resistance', 0)},
                "aqi": { "value": int(d.get('aqi', 0)), "category": str(d.get('aqi_category', 'Unknown')) },
                "trend": d.get('trend_analysis', {}),
                "outdoor": self.outdoor_data,
                "system": { "state": str(d.get('state', 'NORMAL')), "tunnel": self.tunnel_url if self.tunnel_active else None }
            }
            self.io.emit('live_data', live_payload) 
            
            time.sleep(POLL_INTERVAL)

    def log_data(self, data):
        now = datetime.now()
        path = os.path.join(LOG_DIR, now.strftime('%Y'), now.strftime('%m'))
        os.makedirs(path, exist_ok=True)
        filename = os.path.join(path, f"{now.strftime('%d')}.csv")
        try:
            file_exists = os.path.isfile(filename)
            with open(filename, 'a', newline='') as f:
                if not file_exists: f.write("Time,IAQ,AQI,Temp,Humidity,Pressure,PM1.0,PM2.5,PM10\n")
                f.write(f"{now.strftime('%H:%M:%S')},{data.get('aqi_category', 'Unknown')},{data.get('aqi', 0)},{data.get('temperature', 0)},{data.get('humidity', 0)},{data.get('pressure', 0)},{data.get('pm1', 0)},{data.get('pm25', 0)},{data.get('pm10', 0)}\n")
        except Exception: pass


# --- FLASK & WEBSOCKET SETUP ---
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
engine = AtmosEngine(socketio)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def serve_landing():
    for f in ['landing.html', 'Landing.html', 'LANDING.html']:
        if os.path.exists(os.path.join(BASE_DIR, f)): 
            return app.send_static_file(f)
    return "landing.html missing", 404

@app.route('/dashboard')
def serve_dashboard():
    for f in ['Dashboard.html', 'dashboard.html', 'DASHBOARD.html']:
        if os.path.exists(os.path.join(BASE_DIR, f)): 
            return app.send_static_file(f)
    return "Dashboard.html missing", 404

@app.route('/api/status')
def get_status():
    d = engine.latest_data
    return jsonify({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "sensors": {"temperature": d.get('temperature', 0), "humidity": d.get('humidity', 0), "pressure": d.get('pressure', 0), "pm1": d.get('pm1', 0), "pm25": d.get('pm25', 0), "pm10": d.get('pm10', 0), "gas_resistance": d.get('gas_resistance', 0)},
        "aqi": { "value": int(d.get('aqi', 0)), "category": str(d.get('aqi_category', 'Unknown')) },
        "trend": d.get('trend_analysis', {}),
        "outdoor": engine.outdoor_data, 
        "system": { "state": str(d.get('state', 'NORMAL')), "tunnel": engine.tunnel_url if engine.tunnel_active else None }
    })

@app.route('/api/insight/refresh')
def refresh_insight():
    engine.insights_engine.set_tone(request.args.get('tone', 'professional'))
    insight_result = engine.insights_engine.generate({ **engine.latest_data, 'aqi': { 'value': int(engine.latest_data.get('aqi', 0)), 'category': str(engine.latest_data.get('aqi_category', 'Unknown')) } }, engine.latest_data.get('trend_analysis', {}))
    return jsonify({ "insight": str(insight_result.get('summary', 'Analysis complete.')), "recommendation": str(insight_result.get('recommendation', '')) })

@app.route('/api/system/info')
def get_system_info():
    mem = psutil.virtual_memory()
    ssid, signal = get_wifi_info()
    return jsonify({ "cpu": f"{psutil.cpu_percent()}%", "memory": f"{int(mem.used/1048576)}/{int(mem.total/1048576)} MB", "uptime": str(timedelta(seconds=int(time.time() - BOOT_TIME))), "ip": get_ip_address(), "ssid": ssid, "signal": signal, "version": "v8.1-OpenMeteo" })

@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    if request.method == 'POST':
        data = request.json
        if 'alerts_enabled' in data: engine.config['alerts_enabled'] = bool(data['alerts_enabled'])
        if 'alert_threshold' in data: engine.config['alert_threshold'] = int(data['alert_threshold'])
        if 'latitude' in data: engine.config['latitude'] = str(data['latitude'])
        if 'longitude' in data: engine.config['longitude'] = str(data['longitude'])
        engine.save_config()
        return jsonify({"status": "success", "config": engine.config})
    return jsonify(engine.config)

@app.route('/api/alerts')
def get_alerts():
    return jsonify(engine.alert_history)

@app.route('/api/control/test_alert', methods=['POST'])
def test_alert():
    engine.log_alert("Manual UI Alert System Test Triggered.", "info")
    return jsonify({"status": "success", "msg": "Alert logged internally"})

@app.route('/api/control/tunnel', methods=['POST'])
def control_tunnel():
    if request.json.get('action') == 'start': engine.start_tunnel()
    else: engine.stop_tunnel()
    return jsonify({"status": "success", "tunnel": engine.tunnel_active, "url": engine.tunnel_url})

@app.route('/api/logs/structure')
def get_log_structure():
    try:
        structure = {}
        if os.path.exists(LOG_DIR):
            for year in sorted(os.listdir(LOG_DIR)):
                year_path = os.path.join(LOG_DIR, year)
                if os.path.isdir(year_path):
                    structure[year] = {}
                    for month in sorted(os.listdir(year_path)):
                        month_path = os.path.join(year_path, month)
                        if os.path.isdir(month_path):
                            days_set = set()
                            for f in os.listdir(month_path):
                                if f.endswith('.csv'): days_set.add(f.replace('.csv', ''))
                                elif f.endswith('.csv.gz'): days_set.add(f.replace('.csv.gz', ''))
                            structure[year][month] = sorted(list(days_set))
        try:
            total, used, free = shutil.disk_usage(LOG_DIR if os.path.exists(LOG_DIR) else BASE_DIR)
            storage_info = { "total_gb": round(total / (2**30), 1), "used_gb": round(used / (2**30), 1), "free_gb": round(free / (2**30), 1), "percent": round((used / total) * 100, 1) }
        except Exception:
            storage_info = {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
            
        return jsonify({"structure": structure, "storage": storage_info})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs/view')
def view_log():
    try:
        year = request.args.get('year')
        month = request.args.get('month')
        day = request.args.get('day')
        if not (year and month and day): return jsonify({"error": "Missing parameters"}), 400
        
        filepath_csv = os.path.join(LOG_DIR, year, month, f"{day}.csv")
        filepath_gz = os.path.join(LOG_DIR, year, month, f"{day}.csv.gz")
        
        content = []
        if os.path.exists(filepath_gz): f = gzip.open(filepath_gz, 'rt')
        elif os.path.exists(filepath_csv): f = open(filepath_csv, 'r')
        else: return jsonify({"error": "File not found"}), 404
            
        reader = csv.reader(f)
        headers = next(reader, None)
        if headers:
            for row in reader:
                content.append({h.strip(): row[i] for i, h in enumerate(headers) if i < len(row)})
        f.close()
        return jsonify({"headers": headers, "data": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs/download')
def download_log():
    try:
        year = request.args.get('year')
        month = request.args.get('month')
        day = request.args.get('day')
        if not (year and month and day): return jsonify({"error": "Missing parameters"}), 400
        
        filepath_csv = os.path.join(LOG_DIR, year, month, f"{day}.csv")
        filepath_gz = os.path.join(LOG_DIR, year, month, f"{day}.csv.gz")
        
        if os.path.exists(filepath_gz): return send_file(filepath_gz, as_attachment=True, download_name=f"AtmosEye_Log_{year}_{month}_{day}.csv.gz")
        elif os.path.exists(filepath_csv): return send_file(filepath_csv, as_attachment=True, download_name=f"AtmosEye_Log_{year}_{month}_{day}.csv")
        else: return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs', methods=['DELETE'])
def delete_logs():
    try:
        count = 0
        data = request.json or {}
        for rel_path in data.get('files', []):
            if ".." in rel_path: continue
            base_path = os.path.join(LOG_DIR, rel_path.replace('.csv', ''))
            for ext in ['.csv', '.csv.gz']:
                if os.path.exists(base_path + ext):
                    try: 
                        os.remove(base_path + ext)
                        count += 1
                    except: pass
        return jsonify({"status": "success", "deleted": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    threading.Thread(target=engine.update_loop, daemon=True).start()
    
    telegram_process = None
    try:
        if os.path.exists(os.path.join(BASE_DIR, "telegram_bot.py")):
            telegram_process = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "telegram_bot.py")])
    except Exception: pass
    
    print(f"\n=============================================\n AtmosEye Engine Active (v8.1 - OpenMeteo)\n=============================================\n")
    local_ip = get_ip_address()
    print("[SYSTEM] Traffic routed through Flask-SocketIO")
    print(f" * Running on all addresses (0.0.0.0)")
    print(f" * Running on http://127.0.0.1:{PORT}")
    if local_ip != "127.0.0.1":
        print(f" * Running on http://{local_ip}:{PORT}")
    print("Press CTRL+C to quit\n")
    
    try:
        # Dev server wrapped with SocketIO threading mode is highly stable for Pi hardware logic
        socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt: 
        pass
    finally:
        if telegram_process: telegram_process.terminate()
