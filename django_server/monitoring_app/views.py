import os
import json
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Employee, Device, ScreenRecording
from .services import get_storage_usage, cleanup_expired_recordings

# =====================================================================
# EMPLOYER AUTHENTICATION VIEWS
# =====================================================================

def login_view(request):
    """
    Employer Login view.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password! (Default: admin / admin)")

    return render(request, 'login.html')


def logout_view(request):
    """
    Employer Logout view.
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


# =====================================================================
# EMPLOYER DASHBOARD VIEWS (REQUIRES LOGIN)
# =====================================================================

@login_required(login_url='/login/')
def dashboard_view(request):
    """
    Employer Dashboard view showing live server storage meter,
    online employees, and downloadable 24h recordings.
    """
    # Proactively clean up any expired recordings on dashboard load
    cleanup_result = cleanup_expired_recordings()
    
    # Filter recordings by employee if query param passed
    employee_id = request.GET.get('employee')
    recordings_qs = ScreenRecording.objects.select_related('employee', 'device').all()
    
    selected_employee = None
    if employee_id:
        recordings_qs = recordings_qs.filter(employee_id=employee_id)
        selected_employee = Employee.objects.filter(id=employee_id).first()

    employees = Employee.objects.all()
    storage = get_storage_usage()
    
    online_count = sum(1 for e in employees if e.is_online)
    total_recordings_count = recordings_qs.count()
    
    context = {
        'recordings': recordings_qs,
        'employees': employees,
        'selected_employee': selected_employee,
        'storage': storage,
        'online_count': online_count,
        'total_recordings_count': total_recordings_count,
        'cleanup_result': cleanup_result if cleanup_result['recordings_deleted'] > 0 else None,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='/login/')
def employee_list_view(request):
    """
    Employee management view.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        employee_code = request.POST.get('employee_code')
        department = request.POST.get('department', 'General')
        
        if name and email and employee_code:
            Employee.objects.create(
                name=name,
                email=email,
                employee_code=employee_code,
                department=department
            )
            messages.success(request, f"Employee '{name}' added successfully!")
            return redirect('employee_list')
        else:
            messages.error(request, "All fields are required!")

    employees = Employee.objects.all()
    return render(request, 'employee_list.html', {'employees': employees})


@login_required(login_url='/login/')
def trigger_cleanup_view(request):
    """
    Manual trigger button for employer to clean expired recordings immediately.
    """
    result = cleanup_expired_recordings()
    messages.success(
        request, 
        f"Cleanup executed! Deleted {result['recordings_deleted']} expired recordings ({result['freed_mb']} MB freed)."
    )
    return redirect('dashboard')


@login_required(login_url='/login/')
def download_recording_view(request, pk):
    """
    Download endpoint for employer to save recording file locally.
    """
    recording = get_object_or_404(ScreenRecording, pk=pk)
    if not recording.video_file or not os.path.exists(recording.video_file.path):
        raise Http404("Recording file has been deleted or expired.")
    
    filename = f"Recording_{recording.employee.employee_code}_{recording.recorded_at.strftime('%Y%m%d_%H%M%S')}.webm"
    return FileResponse(
        open(recording.video_file.path, 'rb'),
        as_attachment=True,
        filename=filename,
        content_type='video/webm'
    )


# =====================================================================
# REST API ENDPOINTS FOR CLIENT LAPTOP AGENT (PUBLIC API FOR LAPTOPS)
# =====================================================================

@csrf_exempt
def api_register_device(request):
    """
    Client agent registration endpoint.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
        employee_code = data.get('employee_code')
        name = data.get('employee_name', 'Employee ' + employee_code)
        email = data.get('employee_email', f"{employee_code}@company.local")
        hostname = data.get('hostname', 'Laptop')
        os_info = data.get('os_info', '')
        mac_address = data.get('mac_address', '')
        
        if not employee_code:
            return JsonResponse({'error': 'employee_code is required'}, status=400)
            
        employee, created = Employee.objects.get_or_create(
            employee_code=employee_code,
            defaults={
                'name': name,
                'email': email,
                'department': 'Operations'
            }
        )
        
        device, _ = Device.objects.get_or_create(
            employee=employee,
            hostname=hostname,
            defaults={
                'os_info': os_info,
                'mac_address': mac_address,
                'ip_address': request.META.get('REMOTE_ADDR')
            }
        )
        device.last_ping = timezone.now()
        device.save()
        
        return JsonResponse({
            'status': 'registered',
            'employee_id': employee.id,
            'employee_name': employee.name,
            'device_id': device.id,
            'server_storage': get_storage_usage()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def api_ping(request):
    """
    Client agent heartbeat endpoint.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    try:
        data = json.loads(request.body.decode('utf-8'))
        employee_code = data.get('employee_code')
        hostname = data.get('hostname', '')
        
        employee = Employee.objects.filter(employee_code=employee_code).first()
        if employee:
            device = Device.objects.filter(employee=employee, hostname=hostname).first()
            if not device:
                device = Device.objects.create(employee=employee, hostname=hostname)
            device.last_ping = timezone.now()
            device.save()
            
            return JsonResponse({'status': 'pong', 'is_online': True})
        return JsonResponse({'error': 'Employee not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def api_upload_chunk(request):
    """
    Client agent video chunk uploader endpoint.
    Receives screen recording file chunk (e.g. 1-hour WebM file).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    employee_code = request.POST.get('employee_code')
    duration_seconds = int(request.POST.get('duration_seconds', 3600))
    recorded_at_str = request.POST.get('recorded_at')
    video_file = request.FILES.get('video_chunk')

    if not employee_code or not video_file:
        return JsonResponse({'error': 'employee_code and video_chunk file are required'}, status=400)

    employee = Employee.objects.filter(employee_code=employee_code).first()
    if not employee:
        return JsonResponse({'error': f'Employee code {employee_code} not recognized'}, status=404)

    # Check server storage space before saving
    storage = get_storage_usage()
    if storage['used_mb'] >= 380:
        cleanup_expired_recordings()
        storage = get_storage_usage()

    if storage['used_mb'] >= 398:
        return JsonResponse({
            'error': 'Server storage full (400MB cap reached). Waiting for 24h auto-deletion.'
        }, status=507)

    if recorded_at_str:
        try:
            recorded_at = datetime.fromisoformat(recorded_at_str)
            if timezone.is_naive(recorded_at):
                recorded_at = timezone.make_aware(recorded_at)
        except ValueError:
            recorded_at = timezone.now()
    else:
        recorded_at = timezone.now()

    device = employee.devices.order_by('-last_ping').first()

    recording = ScreenRecording.objects.create(
        employee=employee,
        device=device,
        video_file=video_file,
        recorded_at=recorded_at,
        duration_seconds=duration_seconds,
        file_size_bytes=video_file.size
    )

    return JsonResponse({
        'status': 'uploaded',
        'recording_id': recording.id,
        'file_size_mb': recording.file_size_mb,
        'expires_at': recording.expires_at.isoformat(),
        'server_storage_used_mb': get_storage_usage()['used_mb']
    })
