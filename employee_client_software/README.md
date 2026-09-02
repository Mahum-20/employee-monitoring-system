# Standalone Employee Laptop Monitoring Software

A desktop software application that records employee screen activity in 1-hour (or smaller) video segments and transmits them securely via REST API to your Django Employer Site.

---

## Software Features

- **1-Hour Video Segmenting**: Captures screen activity continuously in customizable 5, 15, 30, or **60-minute (1-hour)** clips.
- **Low-Bitrate Compression**: 1–2 FPS recording ensures a 1-hour screen video clip is only **~18 MB to 25 MB**, working perfectly within your server's 400 MB storage cap.
- **Desktop Control App (`main_gui.py`)**: GUI window allowing IT admin or employees to set connection credentials, test connection, start/stop recording, and inspect live transmission logs.
- **Auto-Cleanup**: Deletes local temporary files on the employee laptop immediately upon successful server receipt.

---

## Installation & Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Launch Desktop Software GUI:
   ```bash
   python main_gui.py
   ```

3. Enter Connection Settings:
   - **Django Server URL**: `http://YOUR-DJANGO-SERVER-IP:8000`
   - **Employee Code**: `EMP001` (Unique ID for laptop)
   - **Clip Duration**: Select `60 Minutes (1 Hour)`

4. Click **Start Monitoring** to begin capturing & streaming screen recordings to your Django Employer site.
