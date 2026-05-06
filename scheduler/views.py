from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import Session, Student, RecurringSchedule, GlobalSettings
from .forms import StudentForm, ManualSessionForm, GlobalSettingsForm
from .services import generate_sessions_for_student, generate_sessions_for_all_active_students, CAIRO_TZ

def get_revenue_metrics():
    """Calculate simple revenue metrics for the dashboard."""
    today = timezone.localdate(timezone=CAIRO_TZ)
    # Start of current week (assuming Monday is 0)
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
    today_sessions = Session.objects.filter(start_time__date=today).order_by('start_time')
    
    metrics = get_revenue_metrics()
    
    # Pre-load forms for modals
    student_form = StudentForm()
    session_form = ManualSessionForm()

    context = {
        'today': today,
        'sessions': today_sessions,
        'metrics': metrics,
        'student_form': student_form,
        'session_form': session_form,
        'students': Student.objects.filter(is_active=True)
    }
    return render(request, 'scheduler/dashboard.html', context)


def add_student(request):
    """Handles adding a student and their recurring schedule in one go."""
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            
            # Simple custom schedule parsing from POST data
            # Assuming frontend sends: schedule_day_0, schedule_time_0, etc.
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
            
            # Generate sessions immediately
            count, errors = generate_sessions_for_student(student, weeks=4)
            messages.success(request, f"Added {student.name} and generated {count} sessions.")
            if errors:
                for err in errors:
                    messages.warning(request, err)
        else:
            messages.error(request, "Failed to add student. Check form errors.")
            
    return redirect('scheduler:dashboard')


def add_session(request):
    """Handles adding a single manual session."""
    if request.method == 'POST':
        form = ManualSessionForm(request.POST)
        if form.is_valid():
            from .services import validate_session
            
            start_dt = form.cleaned_data['start_time']
            duration = form.cleaned_data['duration']
            
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
    """1-Click status update."""
    if request.method == 'POST':
        session = get_object_or_404(Session, pk=pk)
        new_status = request.POST.get('status')
        if new_status in dict(Session.STATUS_CHOICES):
            session.status = new_status
            session.save()
            # If doing HTMX, could return just the session card or a success bit.
            # For simplicity, redirecting to dashboard.
    return redirect('scheduler:dashboard')


def delete_session(request, pk):
    """Quick delete."""
    if request.method == 'POST':
        session = get_object_or_404(Session, pk=pk)
        session.delete()
    return redirect('scheduler:dashboard')


def generate_sessions_view(request):
    """Trigger background generation."""
    if request.method == 'POST':
        count, errors = generate_sessions_for_all_active_students(weeks=4)
        messages.success(request, f"Successfully generated {count} future sessions.")
        for err in errors:
            messages.warning(request, err)
    return redirect('scheduler:dashboard')


def settings_view(request):
    """Simple global settings view."""
    settings_obj = GlobalSettings.load()
    if request.method == 'POST':
        form = GlobalSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings updated.")
            return redirect('scheduler:dashboard')
    else:
        form = GlobalSettingsForm(instance=settings_obj)
    
    return render(request, 'scheduler/settings.html', {'form': form})
