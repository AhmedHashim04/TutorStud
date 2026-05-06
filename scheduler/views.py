from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import Session, Student, RecurringSchedule, GlobalSettings, PrayerTime
from .forms import StudentForm, ManualSessionForm, GlobalSettingsForm
from .services import generate_sessions_for_student, generate_sessions_for_all_active_students, CAIRO_TZ, fetch_cairo_prayer_times
from datetime import datetime
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
    # Hook: Auto-regenerate schedules for active students who ran out of sessions
    from .services import auto_regenerate_empty_schedules
    auto_regenerate_empty_schedules()
    
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
            student = form.cleaned_data['student']
            
            # If price was blank, fallback to student default
            if not form.cleaned_data.get('price'):
                form.instance.price = student.session_price
            
            # If duration was blank, fallback
            if not duration:
                duration = student.session_duration
                form.instance.duration = duration
                
            errors = validate_session(start_dt, duration, student_id=student.id)
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

from django.http import JsonResponse

def calendar_view(request):
    """Renders the FullCalendar JS page."""
    context = {
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/calendar.html', context)

def api_calendar_events(request):
    """Returns JSON array of events for FullCalendar."""
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    events = []
    
    if start_str and end_str:
        # Filter sessions within the range
        try:
            from django.utils.dateparse import parse_datetime
            start_dt = parse_datetime(start_str)
            end_dt = parse_datetime(end_str)
            
            # If parse_datetime returns a naive datetime, make it aware (UTC)
            if start_dt and timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt, timezone.utc)
            if end_dt and timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt, timezone.utc)
                
            sessions = Session.objects.filter(start_time__gte=start_dt, start_time__lt=end_dt)
        except Exception:
            sessions = Session.objects.all()
    else:
        sessions = Session.objects.all()
        
    for s in sessions:
        # Determine color based on status
        color = '#6c757d' # scheduled (secondary)
        if s.status == 'attended':
            color = '#198754' # success
        elif s.status == 'absent':
            color = '#dc3545' # danger
        elif s.status == 'excused':
            color = '#ffc107' # warning
            
        tutor_time_str = s.tutor_time.strftime("%I:%M %p")
        student_time_str = s.student_time.strftime("%I:%M %p")
        country_code = dict(s.student._meta.get_field('country').choices).get(s.student.country, s.student.country)[:2]
            
        events.append({
            'id': s.id,
            'title': s.student.name,
            'start': s.start_time.isoformat(),
            'end': s.end_time.isoformat(),
            'color': color,
            'extendedProps': {
                'status': s.get_status_display(),
                'duration': s.duration,
                'tutorTime': f"🇪🇬 {tutor_time_str}",
                'studentTime': f"{country_code} {student_time_str}"
            }
        })
        
    return JsonResponse(events, safe=False)

def analytics_dashboard(request):
    """Renders the Analytics SPA dashboard."""
    context = {
        'students': Student.objects.all().order_by('name'),
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
    }
    return render(request, 'scheduler/analytics.html', context)

def api_analytics(request):
    """Returns JSON analytics data based on filters."""
    from .analytics import get_analytics_data
    from django.utils.dateparse import parse_datetime
    
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    student_id = request.GET.get('student_id')
    
    start_dt = None
    end_dt = None
    
    if start_str:
        start_dt = parse_datetime(start_str + "T00:00:00")
        if start_dt and timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, CAIRO_TZ)
            
    if end_str:
        end_dt = parse_datetime(end_str + "T23:59:59")
        if end_dt and timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt, CAIRO_TZ)
            
    # Default to last 30 days if no dates provided
    if not start_dt:
        end_dt = timezone.now()
        start_dt = end_dt - timedelta(days=30)
        
    data = get_analytics_data(
        start_date=start_dt,
        end_date=end_dt,
        student_id=student_id if student_id else None
    )
    
    return JsonResponse(data)


# ============================================================================
# SCHEDULE MANAGEMENT (NEW - PHASE 3)
# ============================================================================

def student_schedules(request, student_id):
    """View and manage recurring schedules for a student."""
    student = get_object_or_404(Student, pk=student_id)
    schedules = student.schedules.all().order_by('weekday', 'start_time')
    
    context = {
        'student': student,
        'schedules': schedules,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/student_schedules.html', context)


def edit_schedule(request, pk):
    """Edit a recurring schedule rule."""
    from .forms import RecurringScheduleForm
    schedule = get_object_or_404(RecurringSchedule, pk=pk)
    student = schedule.student
    
    if request.method == 'POST':
        form = RecurringScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "Schedule updated successfully.")
            # Regenerate sessions after changing schedule
            from .services import generate_sessions_for_student
            count, errors = generate_sessions_for_student(student, weeks=4)
            if count > 0:
                messages.info(request, f"Generated {count} new sessions based on updated schedule.")
            if errors:
                for err in errors:
                    messages.warning(request, err)
            return redirect('scheduler:student_schedules', student_id=student.id)
    else:
        form = RecurringScheduleForm(instance=schedule)
    
    context = {
        'form': form,
        'schedule': schedule,
        'student': student,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/schedule_form.html', context)


def delete_schedule(request, pk):
    """Delete a recurring schedule rule."""
    schedule = get_object_or_404(RecurringSchedule, pk=pk)
    student = schedule.student
    
    if request.method == 'POST':
        # When deleting a schedule, optionally delete its exceptions too
        from .models import ScheduleException
        ScheduleException.objects.filter(schedule=schedule).delete()
        
        schedule.delete()
        messages.success(request, "Schedule deleted successfully.")
    
    return redirect('scheduler:student_schedules', student_id=student.id)


# ============================================================================
# SCHEDULE EXCEPTIONS (NEW - PHASE 4)
# ============================================================================

def manage_exceptions(request, student_id):
    """View and manage schedule exceptions for a student."""
    from .models import ScheduleException
    
    student = get_object_or_404(Student, pk=student_id)
    schedules = student.schedules.filter(is_active=True)
    
    # Get all exceptions grouped by schedule
    exceptions_by_schedule = {}
    for schedule in schedules:
        exceptions_by_schedule[schedule] = schedule.exceptions.all().order_by('-week_start_date')
    
    context = {
        'student': student,
        'schedules': schedules,
        'exceptions_by_schedule': exceptions_by_schedule,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/schedule_exceptions.html', context)


def create_exception(request, schedule_id):
    """Create a new schedule exception."""
    from .forms import ScheduleExceptionForm
    
    schedule = get_object_or_404(RecurringSchedule, pk=schedule_id)
    student = schedule.student
    
    if request.method == 'POST':
        form = ScheduleExceptionForm(request.POST)
        if form.is_valid():
            exception = form.save(commit=False)
            exception.schedule = schedule
            exception.created_by = str(request.user) if request.user.is_authenticated else 'System'
            exception.save()
            
            messages.success(request, f"Exception created: {exception.get_detailed_description()}")
            
            # Regenerate sessions to apply the exception
            from .services import generate_sessions_for_student
            count, errors = generate_sessions_for_student(student, weeks=4)
            if count > 0:
                messages.info(request, f"Regenerated {count} sessions with new exception applied.")
            if errors:
                for err in errors:
                    messages.warning(request, err)
            
            return redirect('scheduler:manage_exceptions', student_id=student.id)
    else:
        form = ScheduleExceptionForm()
    
    context = {
        'form': form,
        'schedule': schedule,
        'student': student,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/exception_form.html', context)


def edit_exception(request, pk):
    """Edit an existing schedule exception."""
    from .forms import ScheduleExceptionForm
    from .models import ScheduleException
    
    exception = get_object_or_404(ScheduleException, pk=pk)
    schedule = exception.schedule
    student = schedule.student
    
    if request.method == 'POST':
        form = ScheduleExceptionForm(request.POST, instance=exception)
        if form.is_valid():
            form.save()
            messages.success(request, "Exception updated successfully.")
            
            # Regenerate sessions
            from .services import generate_sessions_for_student
            count, errors = generate_sessions_for_student(student, weeks=4)
            if count > 0:
                messages.info(request, f"Regenerated {count} sessions with updated exception.")
            
            return redirect('scheduler:manage_exceptions', student_id=student.id)
    else:
        form = ScheduleExceptionForm(instance=exception)
    
    context = {
        'form': form,
        'exception': exception,
        'schedule': schedule,
        'student': student,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        'students': Student.objects.filter(is_active=True),
    }
    return render(request, 'scheduler/exception_form.html', context)


def delete_exception(request, pk):
    """Delete a schedule exception."""
    from .models import ScheduleException
    
    exception = get_object_or_404(ScheduleException, pk=pk)
    schedule = exception.schedule
    student = schedule.student
    
    if request.method == 'POST':
        exception.delete()
        messages.success(request, "Exception deleted successfully.")
        
        # Regenerate to remove the exception's effects
        from .services import generate_sessions_for_student
        generate_sessions_for_student(student, weeks=4)
    
    return redirect('scheduler:manage_exceptions', student_id=student.id)
