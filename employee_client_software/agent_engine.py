import os
import sys
import time
import json
import socket
import platform
import threading
from datetime import datetime
import requests
import cv2
import numpy as np
import mss

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config():
    default_config = {
        "server_url": "http://127.0.0.1:8000",
        "employee_code": "EMP001",
        "employee_name": "Employee 1",
        "employee_email": "emp1@company.local",
        "fps": 2,
        "chunk_duration_minutes": 60, # Up to 1 hour clips
        "target_width": 1280,
        "target_height": 720,
        "auto_start": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception as e:
            print(f"Error loading config.json: {e}")
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config.json: {e}")
        return False


class EmployeeMonitorEngine:
    """
    Background recorder & API engine for Employee Laptop Client.
    Connects via REST API to Django server and uploads 1-hour (or custom) video clips.
    """
    def __init__(self, log_callback=None):
        self.config = load_config()
        self.log_callback = log_callback or self.default_log
        self.is_running = False
        self.hostname = socket.gethostname()
        self.os_info = f"{platform.system()} {platform.release()}"
        self.temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_recordings')
        os.makedirs(self.temp_dir, exist_ok=True)

    def default_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def reload_config(self):
        self.config = load_config()

    def test_connection(self):
        """Test API connection to Django server."""
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/ping/"
        try:
            res = requests.post(endpoint, json={"employee_code": self.config['employee_code'], "hostname": self.hostname}, timeout=5)
            if res.status_code in [200, 404]: # Server reached
                return True, "Successfully connected to Django server!"
            return False, f"Server returned status {res.status_code}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def register_device(self):
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/register/"
        payload = {
            "employee_code": self.config['employee_code'],
            "employee_name": self.config.get('employee_name', self.config['employee_code']),
            "employee_email": self.config.get('employee_email', f"{self.config['employee_code']}@company.local"),
            "hostname": self.hostname,
            "os_info": self.os_info
        }
        try:
            res = requests.post(endpoint, json=payload, timeout=10)
            if res.status_code == 200:
                self.log_callback(f"Connected to server. Registered laptop '{self.hostname}' for {self.config['employee_code']}.")
                return True
            else:
                self.log_callback(f"Registration note: {res.text}")
        except Exception as e:
            self.log_callback(f"Could not connect to server at {server_url}: {e}")
        return False

    def send_heartbeat(self):
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/ping/"
        payload = {"employee_code": self.config['employee_code'], "hostname": self.hostname}
        while self.is_running:
            try:
                requests.post(endpoint, json=payload, timeout=5)
            except Exception:
                pass
            time.sleep(60)

    def upload_recording_segment(self, file_path, recorded_at_iso, duration_seconds):
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/upload/"
        if not os.path.exists(file_path):
            return

        file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
        self.log_callback(f"Uploading {duration_seconds//60}-min video segment ({file_size_mb} MB) to Django server...")
        
        try:
            with open(file_path, 'rb') as f:
                files = {'video_chunk': (os.path.basename(file_path), f, 'video/webm')}
                data = {
                    'employee_code': self.config['employee_code'],
                    'recorded_at': recorded_at_iso,
                    'duration_seconds': duration_seconds
                }
                res = requests.post(endpoint, data=data, files=files, timeout=60)
                if res.status_code == 200:
                    resp_json = res.json()
                    self.log_callback(f"Upload Success! Server Storage Used: {resp_json.get('server_storage_used_mb')} MB / 400 MB")
                    # Delete local temp chunk file after successful transmission
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                else:
                    self.log_callback(f"Upload rejected ({res.status_code}): {res.text}")
        except Exception as e:
            self.log_callback(f"Network error during upload: {e}")

    def start_recording_service(self):
        if self.is_running:
            return
        self.is_running = True
        self.reload_config()
        self.register_device()
        
        # Start heartbeat thread
        threading.Thread(target=self.send_heartbeat, daemon=True).start()

        # Start recording loop thread
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop_recording_service(self):
        self.is_running = False
        self.log_callback("Stopping monitoring service...")

    def _record_loop(self):
        fps = max(1, min(5, int(self.config['fps'])))
        chunk_seconds = int(self.config['chunk_duration_minutes'] * 60) # up to 3600s (1 hour)
        width = int(self.config['target_width'])
        height = int(self.config['target_height'])

        self.log_callback(f"Recording loop active. Framerate: {fps} FPS, Segment Duration: {chunk_seconds//60} mins.")

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            
            while self.is_running:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                recorded_at_iso = datetime.now().isoformat()
                output_filename = f"segment_{self.config['employee_code']}_{timestamp_str}.webm"
                output_filepath = os.path.join(self.temp_dir, output_filename)

                fourcc = cv2.VideoWriter_fourcc(*'VP80')
                out = cv2.VideoWriter(output_filepath, fourcc, fps, (width, height))

                if not out.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    output_filename = output_filename.replace('.webm', '.avi')
                    output_filepath = os.path.join(self.temp_dir, output_filename)
                    out = cv2.VideoWriter(output_filepath, fourcc, fps, (width, height))

                start_time = time.time()
                frame_interval = 1.0 / fps
                frames_captured = 0

                try:
                    while (time.time() - start_time) < chunk_seconds and self.is_running:
                        loop_start = time.time()
                        
                        sct_img = sct.grab(monitor)
                        frame = np.array(sct_img)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        frame_resized = cv2.resize(frame, (width, height))

                        out.write(frame_resized)
                        frames_captured += 1

                        elapsed = time.time() - loop_start
                        sleep_time = max(0.001, frame_interval - elapsed)
                        time.sleep(sleep_time)

                except Exception as e:
                    self.log_callback(f"Recording error: {e}")
                finally:
                    out.release()

                actual_duration = int(time.time() - start_time)
                if frames_captured > 0 and os.path.exists(output_filepath):
                    # Launch upload thread asynchronously so recording loop continues without interruption
                    threading.Thread(
                        target=self.upload_recording_segment, 
                        args=(output_filepath, recorded_at_iso, actual_duration),
                        daemon=True
                    ).start()

        self.log_callback("Recording service stopped.")
