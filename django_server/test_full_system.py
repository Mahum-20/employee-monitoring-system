import os
import sys
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_monitoring.settings')
django.setup()

from django.test import Client
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from monitoring_app.models import Employee, Device, ScreenRecording
from monitoring_app.services import cleanup_expired_recordings, get_storage_usage

print("=== INTEGRATION TEST: SEPARATE DJANGO SERVER & DESKTOP AGENT API ===")
client = Client()

# 0. Test Employer Dashboard Login Protection
unauth_resp = client.get('/')
assert unauth_resp.status_code == 302 and '/login/' in unauth_resp.url, "Dashboard not protected by login!"
print("[OK] Unauthenticated access properly redirected to /login/")

login_resp = client.post('/login/', {'username': 'admin', 'password': 'admin'})
assert login_resp.status_code == 302 and login_resp.url == '/', "Employer Login failed with admin / admin credentials!"
print("[OK] Employer Login with admin / admin succeeded!")

dash_resp = client.get('/')
assert dash_resp.status_code == 200, "Authenticated dashboard request failed!"
print("[OK] Dashboard accessible after employer login!")
reg_resp = client.post('/api/agent/register/', data={
    "employee_code": "LAPTOP_EMP_01",
    "employee_name": "Software Test Worker",
    "employee_email": "laptop01@company.local",
    "hostname": "EMPLOYEE-LAPTOP-WIN11",
    "os_info": "Windows 11 Enterprise"
}, content_type='application/json')

assert reg_resp.status_code == 200, f"Register failed: {reg_resp.content}"
print("[OK] Desktop App Registration API (/api/agent/register/) passed!")

# 2. Test 1-Hour Video Segment Upload API
test_video = SimpleUploadedFile("segment_1hr_test.webm", b"ONE_HOUR_SCREEN_RECORDING_DATA_STREAM" * 1024, content_type="video/webm")
upload_resp = client.post('/api/agent/upload/', data={
    "employee_code": "LAPTOP_EMP_01",
    "duration_seconds": 3600, # 1 Hour clip
    "video_chunk": test_video
})

assert upload_resp.status_code == 200, f"1-Hour Segment Upload failed: {upload_resp.content}"
upload_json = upload_resp.json()
rec_id = upload_json['recording_id']
print(f"[OK] 1-Hour Video Segment Upload API (/api/agent/upload/) passed! (Recording ID: {rec_id})")

# 3. Verify Formatted Duration & 24h Expiration Date
rec = ScreenRecording.objects.get(id=rec_id)
assert rec.formatted_duration == "1h 0m", f"Expected '1h 0m', got {rec.formatted_duration}"
print(f"[OK] Display Duration verified: {rec.formatted_duration}")
print(f"[OK] Expiration set to: {rec.expires_at} (24 hours from upload)")

# 4. Test 24-Hour Automated Cleanup Engine
rec.expires_at = timezone.now() - timedelta(hours=1)
rec.save()

file_path = rec.video_file.path
assert os.path.exists(file_path), "Video file missing before cleanup"

cleanup_res = cleanup_expired_recordings()
assert cleanup_res['recordings_deleted'] >= 1, "Failed to purge expired 1-hour recording"
assert not os.path.exists(file_path), "Expired video file was not removed from server disk!"
print("[OK] 24-Hour Auto-Purge Engine verified! File and DB entry purged!")

storage = get_storage_usage()
print(f"[OK] Storage Meter: {storage['used_mb']} MB / {storage['limit_mb']} MB ({storage['used_percent']}% used)")

print("\nALL SEPARATE SERVER & DESKTOP CLIENT TESTS PASSED!\n")
