from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import Session, Student, RecurringSchedule, GlobalSettings, PrayerTime
from .forms import StudentForm, ManualSessionForm, GlobalSettingsForm
from .services import generate_sessions_for_student, generate_sessions_for_all_active_students, CAIRO_TZ, fetch_cairo_prayer_times

def get_revenue_metrics():
    """Calculate simple revenue metrics for the dashboard."""
    today = timezone.localdate(timezone=CAIRO_TZ)
    start_of_week = today - timedelta(days=today.weekday())
    
    today_sessions = Session.objects.filter(start_time__date=today, status__in=['attended', 'absent'])
    week_sessions = Session.objects.filter(start_time__date__gte=start_of_week, status__in=['attended', 'absent'])
    
    return {
        'today_earned': today_sessions.aggregate(Sum('price'))['price__sum'] or 0,
        'week_earned': week_sessions.aggregate(Sum('price'))['price__sum'] or 0,
    }

def dashboard(request):
    """The Command Center Main View."""
    today = timezone.localdate(timezone=CAIRO_TZ)
    # Today's sessions
    today_sessions = Session.objects.filter(start_time__date=today).order_by('start_time')
    
    # Upcoming sessions (Next 3 days)
    upcoming_sessions = Session.objects.filter(
        start_time__date__gt=today, 
        start_time__date__lte=today + timedelta(days=3),
        status='scheduled'
    ).order_by('start_time')

    metrics = get_revenue_metrics()
    
    student_form = StudentForm()
    session_form = ManualSessionForm()

    context = {
        'today': today,
        'sessions': today_sessions,
        'upcoming_sessions': upcoming_sessions,
        'metrics': metrics,
        'student_form': student_form,
        'session_form': session_form,
        'students': Student.objects.filter(is_active=True)
    }
    return render(request, 'scheduler/dashboard.html', context)

def student_list(request):
    """List of all students with quick stats."""
    students = Student.objects.all().order_by('-is_active', 'name')
    # Attach next session for each
    now = timezone.now()
    for student in students:
        student.next_session = student.sessions.filter(start_time__gte=now, status='scheduled').order_by('start_time').first()
        
    return render(request, 'scheduler/student_list.html', {
        'students': students,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
    })

def student_detail(request, pk):
    """Student Profile (Mini OS)"""
    student = get_object_or_404(Student, pk=pk)
    now = timezone.now()
    
    past_sessions = student.sessions.filter(start_time__lt=now).order_by('-start_time')
    upcoming_sessions = student.sessions.filter(start_time__gte=now).order_by('start_time')
    
    context = {
        'student': student,
        'past_sessions': past_sessions,
        'upcoming_sessions': upcoming_sessions,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/student_detail.html', context)

def update_student_notes(request, pk):
    """Quick endpoint to save notes via AJAX or simple POST."""
    if request.method == 'POST':
        student = get_object_or_404(Student, pk=pk)
        student.notes = request.POST.get('notes', '')
        student.save()
        messages.success(request, "Notes saved.")
    return redirect('scheduler:student_detail', pk=pk)

def add_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            i = 0
            while f'schedule_day_{i}' in request.POST:
                day = request.POST.get(f'schedule_day_{i}')
                time_val = request.POST.get(f'schedule_time_{i}')
                if day and time_val:
                    RecurringSchedule.objects.create(
                        student=student,
                        weekday=int(day),
                        start_time=time_val
                    )
                i += 1
            
            count, errors = generate_sessions_for_student(student, weeks=4)
            messages.success(request, f"Added {student.name} and generated {count} sessions.")
            if errors:
                for err in errors:
                    messages.warning(request, err)
        else:
            messages.error(request, "Failed to add student. Check form errors.")
    return redirect('scheduler:dashboard')

def add_session(request):
    if request.method == 'POST':
        form = ManualSessionForm(request.POST)
        if form.is_valid():
            from .services import validate_session
            start_dt = form.cleaned_data['start_time']
            duration = form.cleaned_data['duration']
            
            # If price was blank, fallback to student default
            if not form.cleaned_data.get('price'):
                form.instance.price = form.cleaned_data['student'].session_price
            
            # If duration was blank, fallback
            if not duration:
                duration = form.cleaned_data['student'].session_duration
                form.instance.duration = duration
                
            errors = validate_session(start_dt, duration)
            if not errors:
                form.save()
                messages.success(request, "Session added to calendar.")
            else:
                for err in errors:
                    messages.error(request, err)
        else:
            messages.error(request, "Invalid session data.")
    return redirect('scheduler:dashboard')

def update_session_status(request, pk):
    if request.method == 'POST':
        session = get_object_or_404(Session, pk=pk)
        new_status = request.POST.get('status')
        if new_status in dict(Session.STATUS_CHOICES):
            session.status = new_status
            session.save()
    next_url = request.POST.get('next', 'scheduler:dashboard')
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(next_url)

def delete_session(request, pk):
    if request.method == 'POST':
        session = get_object_or_404(Session, pk=pk)
        session.delete()
    next_url = request.POST.get('next', 'scheduler:dashboard')
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(next_url)

def generate_sessions_view(request):
    if request.method == 'POST':
        count, errors = generate_sessions_for_all_active_students(weeks=4)
        messages.success(request, f"Successfully generated {count} future sessions.")
        for err in errors:
            messages.warning(request, err)
    return redirect('scheduler:dashboard')

def settings_view(request):
    settings_obj = GlobalSettings.load()
    if request.method == 'POST':
        form = GlobalSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings updated.")
            return redirect('scheduler:settings')
    else:
        form = GlobalSettingsForm(instance=settings_obj)
    
    today = timezone.localdate(timezone=CAIRO_TZ)
    prayers = PrayerTime.objects.filter(date__gte=today, date__lte=today + timedelta(days=6)).order_by('date', 'adhan_time')
    
    return render(request, 'scheduler/settings.html', {
        'form': form, 
        'prayers': prayers,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    })

def fetch_prayers(request):
    """Hits the aladhan API to populate the next 7 days of prayer times."""
    if request.method == 'POST':
        today = timezone.localdate(timezone=CAIRO_TZ)
        total = 0
        for i in range(7):
            target = today + timedelta(days=i)
            try:
                count = fetch_cairo_prayer_times(target)
                total += count
            except Exception as e:
                messages.error(request, f"Failed to fetch for {target}: {str(e)}")
                break
        if total > 0:
            messages.success(request, f"Fetched and saved {total} prayer time blocks.")
        else:
            messages.info(request, "Prayer times are already up to date.")
    return redirect('scheduler:settings')
