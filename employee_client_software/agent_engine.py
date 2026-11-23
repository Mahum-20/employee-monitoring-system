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
        "chunk_duration_minutes": 15, # 15-minute segments for frequent updates
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
        self.upload_queue = []
        self.queue_lock = threading.Lock()
        self._scan_existing_temp_files()

    def default_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def reload_config(self):
        self.config = load_config()

    def _scan_existing_temp_files(self):
        """Queue any leftover video chunks found from previous runs or crashes."""
        if not os.path.exists(self.temp_dir):
            return
        for fname in os.listdir(self.temp_dir):
            if fname.endswith(('.webm', '.avi')):
                fpath = os.path.join(self.temp_dir, fname)
                try:
                    if os.path.getsize(fpath) > 1024:
                        mtime = os.path.getmtime(fpath)
                        iso_time = datetime.fromtimestamp(mtime).isoformat()
                        self.queue_upload(fpath, iso_time, int(self.config.get('chunk_duration_minutes', 15) * 60))
                except Exception:
                    pass

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

    def queue_upload(self, file_path, recorded_at_iso, duration_seconds):
        """Adds a completed video chunk to the resilient upload retry queue."""
        with self.queue_lock:
            for item in self.upload_queue:
                if item['file_path'] == file_path:
                    return
            self.upload_queue.append({
                'file_path': file_path,
                'recorded_at': recorded_at_iso,
                'duration_seconds': duration_seconds,
                'attempts': 0
            })
        self.log_callback(f"Queued recording segment for transmission ({len(self.upload_queue)} in queue).")

    def upload_recording_segment(self, file_path, recorded_at_iso, duration_seconds):
        """Alias for queue_upload."""
        self.queue_upload(file_path, recorded_at_iso, duration_seconds)

    def _attempt_upload(self, item):
        file_path = item['file_path']
        recorded_at_iso = item['recorded_at']
        duration_seconds = item['duration_seconds']
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/upload/"

        file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
        mins = max(1, duration_seconds // 60)
        self.log_callback(f"Uploading {mins}-min video segment ({file_size_mb} MB) [Queue size: {len(self.upload_queue)}]...")

        try:
            with open(file_path, 'rb') as f:
                files = {'video_chunk': (os.path.basename(file_path), f, 'video/webm')}
                data = {
                    'employee_code': self.config['employee_code'],
                    'recorded_at': recorded_at_iso,
                    'duration_seconds': duration_seconds
                }
                res = requests.post(endpoint, data=data, files=files, timeout=90)
                if res.status_code == 200:
                    resp_json = res.json()
                    self.log_callback(f"Upload Success! Server Storage: {resp_json.get('server_storage_used_mb')} MB / 400 MB")
                    return True
                else:
                    self.log_callback(f"Upload rejected (HTTP {res.status_code}): {res.text}. Kept in queue to retry.")
                    return False
        except Exception as e:
            self.log_callback(f"Network error during upload: {e}. Kept in queue to retry.")
            return False

    def _upload_worker(self):
        """Background thread worker that processes the upload queue with retry."""
        while self.is_running:
            item = None
            with self.queue_lock:
                if self.upload_queue:
                    item = self.upload_queue[0]

            if not item:
                time.sleep(3)
                continue

            file_path = item['file_path']
            if not os.path.exists(file_path):
                with self.queue_lock:
                    if item in self.upload_queue:
                        self.upload_queue.remove(item)
                continue

            success = self._attempt_upload(item)
            if success:
                with self.queue_lock:
                    if item in self.upload_queue:
                        self.upload_queue.remove(item)
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                time.sleep(1)
            else:
                item['attempts'] += 1
                # Wait 10 seconds before next retry attempt
                time.sleep(10)

    def start_recording_service(self):
        if self.is_running:
            return
        self.is_running = True
        self.reload_config()
        self.register_device()
        
        # Start heartbeat thread
        threading.Thread(target=self.send_heartbeat, daemon=True).start()

        # Start resilient upload retry queue worker
        threading.Thread(target=self._upload_worker, daemon=True).start()

        # Start recording loop thread
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop_recording_service(self):
        self.is_running = False
        self.log_callback("Stopping monitoring service...")

    def _record_loop(self):
        fps = max(1, min(5, int(self.config.get('fps', 2))))
        chunk_seconds = int(self.config.get('chunk_duration_minutes', 15) * 60)
        width = int(self.config.get('target_width', 1280))
        height = int(self.config.get('target_height', 720))

        self.log_callback(f"Recording loop active. Framerate: {fps} FPS, Segment Duration: {chunk_seconds//60} mins.")

        while self.is_running:
            try:
                with mss.mss() as sct:
                    if not sct.monitors or len(sct.monitors) < 2:
                        time.sleep(3)
                        continue
                    monitor = sct.monitors[1]

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

                            try:
                                sct_img = sct.grab(monitor)
                                frame = np.array(sct_img)
                                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                                frame_resized = cv2.resize(frame, (width, height))

                                out.write(frame_resized)
                                frames_captured += 1
                            except Exception:
                                # Display may be asleep or locked; pause briefly without crashing
                                time.sleep(2)
                                continue

                            elapsed = time.time() - loop_start
                            sleep_time = max(0.001, frame_interval - elapsed)
                            time.sleep(sleep_time)

                    except Exception as e:
                        self.log_callback(f"Recording error: {e}")
                    finally:
                        out.release()

                    actual_duration = int(time.time() - start_time)
                    if frames_captured > 0 and os.path.exists(output_filepath):
                        self.queue_upload(output_filepath, recorded_at_iso, actual_duration)
                    elif os.path.exists(output_filepath):
                        try:
                            os.remove(output_filepath)
                        except OSError:
                            pass

            except Exception as e:
                self.log_callback(f"Display capture exception (screen may be asleep/locked): {e}. Retrying in 5s...")
                time.sleep(5)

        self.log_callback("Recording service stopped.")
