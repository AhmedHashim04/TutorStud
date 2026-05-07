from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, FloatField, Value, Case, When
from django.core.paginator import Paginator

from datetime import timedelta
from .models import Session, Student, RecurringSchedule, GlobalSettings, PrayerTime, COUNTRY_CHOICES
from .forms import StudentForm, ManualSessionForm, GlobalSettingsForm, SessionRescheduleForm
from .services import generate_sessions_for_student, generate_sessions_for_all_active_students, sync_future_sessions_for_student, CAIRO_TZ, fetch_cairo_prayer_times, get_prayer_block_minutes
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
    today_sessions = Session.objects.filter(start_time__date=today,student__is_active=True).order_by('start_time')
    
    # Upcoming sessions (Next 3 days)
    upcoming_sessions = Session.objects.filter(
        start_time__date__gt=today, 
        start_time__date__lte=today + timedelta(days=3),
        status='scheduled',
        student__is_active=True
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
    """List of all students with advanced filtering and quick stats."""
    # Base queryset
    qs = Student.objects.all()

    # --- Annotations for reusable filters ---
    now = timezone.now()
    next_week = now + timedelta(days=7)
    first_of_month = timezone.localdate(timezone=CAIRO_TZ).replace(day=1)

    qs = qs.annotate(
        upcoming_sessions=Count('sessions', filter=Q(sessions__start_time__gte=now, sessions__status='scheduled')),
        weekly_sessions=Count('sessions', filter=Q(sessions__start_time__gte=now, sessions__start_time__lt=next_week, sessions__status='scheduled')),
        monthly_revenue_calc=Sum('sessions__price', filter=Q(sessions__start_time__date__gte=first_of_month, sessions__status__in=['attended', 'absent']))
    )
    # attendance_rate annotation (percentage)
    qs = qs.annotate(
        attended_sessions=Count('sessions', filter=Q(sessions__start_time__lt=now, sessions__status='attended')),
        total_sessions=Count('sessions', filter=Q(sessions__start_time__lt=now) & ~Q(sessions__status__in=['scheduled', 'cancelled_by_teacher']))
    ).annotate(attendance_rate_calc=Case(
        When(total_sessions=0, then=Value(0)),
        default=ExpressionWrapper(100.0 * F('attended_sessions') / F('total_sessions'), output_field=FloatField()),
        output_field=FloatField()
    ))

    # --- Parse GET parameters ---
    name = request.GET.get('name', '').strip()
    if name:
        qs = qs.filter(name__icontains=name)

    active = request.GET.get('active')
    if active == 'active':
        qs = qs.filter(is_active=True)
    elif active == 'inactive':
        qs = qs.filter(is_active=False)

    country = request.GET.get('country')
    if country:
        qs = qs.filter(country=country)

    weekly = request.GET.get('weekly')
    if weekly:
        if weekly == '1':
            qs = qs.filter(weekly_sessions=1)
        elif weekly == '2':
            qs = qs.filter(weekly_sessions=2)
        elif weekly == '3plus':
            qs = qs.filter(weekly_sessions__gte=3)

    if request.GET.get('has_upcoming'):
        qs = qs.filter(upcoming_sessions__gt=0)
    if request.GET.get('no_future'):
        qs = qs.filter(upcoming_sessions=0)

    recent_days = request.GET.get('recent_days')
    if recent_days and recent_days.isdigit():
        cutoff = timezone.now().date() - timedelta(days=int(recent_days))
        qs = qs.filter(created_at__date__gte=cutoff)

    rev_min = request.GET.get('rev_min')
    rev_max = request.GET.get('rev_max')
    if rev_min:
        qs = qs.filter(monthly_revenue_calc__gte=rev_min)
    if rev_max:
        qs = qs.filter(monthly_revenue_calc__lte=rev_max)

    att_min = request.GET.get('att_min')
    att_max = request.GET.get('att_max')
    if att_min:
        qs = qs.filter(attendance_rate_calc__gte=att_min)
    if att_max:
        qs = qs.filter(attendance_rate_calc__lte=att_max)

    # Preserve ordering and pagination if needed (simple ordering for now)
    qs = qs.order_by('-is_active', 'name')

    # Attach next session for display (still needed for card)
    now = timezone.now()
    for student in qs:
        student.next_session = student.sessions.filter(start_time__gte=now, status='scheduled').order_by('start_time').first()

    context = {
        'students': qs,
        'student_form': StudentForm(),
        'session_form': ManualSessionForm(),
        # Preserve the current GET params for the UI to repopulate fields
        'filters': request.GET,
        'country_choices': COUNTRY_CHOICES,
    }
    return render(request, 'scheduler/student_list.html', context)

def student_detail(request, pk):
    """Student Profile (Mini OS)"""
    student = get_object_or_404(Student, pk=pk)
    now = timezone.now()
    
    past_sessions = student.sessions.filter(start_time__lt=now).order_by('-start_time')
    
    # Filter past sessions
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status_filter:
        past_sessions = past_sessions.filter(status=status_filter)
    if date_from:
        try:
            from django.utils.dateparse import parse_date
            date_start = parse_date(date_from)
            if date_start:
                past_sessions = past_sessions.filter(start_time__date__gte=date_start)
        except:
            pass
    if date_to:
        try:
            from django.utils.dateparse import parse_date
            date_end = parse_date(date_to)
            if date_end:
                past_sessions = past_sessions.filter(start_time__date__lte=date_end)
        except:
            pass
    
    # Pagination for past sessions
    page_num = request.GET.get('page', 1)
    paginator = Paginator(past_sessions, 10)  # 10 sessions per page
    past_sessions_page = paginator.get_page(page_num)
    
    upcoming_sessions = student.sessions.filter(start_time__gte=now, status='scheduled').order_by('start_time')
    
    context = {
        'student': student,
        'past_sessions': past_sessions_page,
        'upcoming_sessions': upcoming_sessions,
        'paginator': paginator,
        'status_choices': Session.STATUS_CHOICES,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
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


def toggle_student_status(request, pk):
    """Activate or deactivate a student."""
    from django.http import JsonResponse
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        old_status = student.is_active
        student.is_active = not student.is_active
        student.save()
        
        # If inactivating, purge future sessions
        if old_status and not student.is_active:
            from .services import purge_future_sessions_for_inactive_student
            purge_future_sessions_for_inactive_student(student)
            messages.info(request, f"✓ {student.name} marked inactive. Future sessions removed.")
        elif not old_status and student.is_active:
            messages.success(request, f"✓ {student.name} marked active.")
        
        # If AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'is_active': student.is_active,
                'message': f"{student.name} is now {' Active' if student.is_active else 'Inactive'}"
            })
    
    next_url = request.POST.get('next', 'scheduler:student_list')
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(next_url)


def add_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()

            # Collect schedule inputs and validate uniqueness + count
            schedule_days = []
            schedule_rows = []
            i = 0
            while f'schedule_day_{i}' in request.POST:
                day = request.POST.get(f'schedule_day_{i}')
                time_val = request.POST.get(f'schedule_time_{i}')
                if day and time_val:
                    schedule_rows.append((int(day), time_val))
                    schedule_days.append(int(day))
                i += 1

            errors_found = False
            if len(set(schedule_days)) != len(schedule_days):
                messages.error(request, "Duplicate days selected in schedule. Please pick unique weekdays.")
                errors_found = True
            if len(set(schedule_days)) > 7:
                messages.error(request, "You cannot select more than 7 unique days.")
                errors_found = True

            if errors_found:
                # rollback created student to avoid orphan
                student.delete()
                return redirect('scheduler:dashboard')

            # Create schedules
            for day, time_val in schedule_rows:
                RecurringSchedule.objects.create(
                    student=student,
                    weekday=day,
                    start_time=time_val
                )

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
                request.session['manual_session_form_data'] = request.POST.dict()
                request.session['manual_session_form_errors'] = errors
                messages.error(request, "Please fix the highlighted session conflicts and try again.")
        else:
            request.session['manual_session_form_data'] = request.POST.dict()
            request.session['manual_session_form_errors'] = [
                error for field_errors in form.errors.values() for error in field_errors
            ]
            messages.error(request, "Invalid session data.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'scheduler:dashboard'
    return redirect(next_url)

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


def reschedule_session(request, pk):
    """Move an upcoming scheduled session to a new date/time."""
    session = get_object_or_404(Session, pk=pk)

    if request.method == 'POST':
        if session.status != 'scheduled':
            messages.error(request, "Only scheduled sessions can be rescheduled.")
        else:
            form = SessionRescheduleForm(request.POST)
            if form.is_valid():
                from .services import ensure_aware, validate_session

                new_start = ensure_aware(form.cleaned_data['start_time'])
                errors = validate_session(
                    new_start,
                    session.duration,
                    exclude_session_id=session.id,
                    student_id=session.student_id,
                )

                if errors:
                    for err in errors:
                        messages.error(request, err)
                else:
                    session.start_time = new_start
                    session.save(update_fields=['start_time'])
                    messages.success(request, f"Session moved to {session.tutor_time.strftime('%Y-%m-%d %H:%M')} (Cairo).")
            else:
                for field_errors in form.errors.values():
                    for error in field_errors:
                        messages.error(request, error)

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
    prayer_qs = PrayerTime.objects.filter(date__gte=today, date__lte=today + timedelta(days=6)).order_by('date', 'adhan_time')
    prayers = []
    for prayer in prayer_qs:
        prayers.append({
            'obj': prayer,
            'block_minutes': get_prayer_block_minutes(prayer, settings_obj=settings_obj),
            'iqama_delay': settings_obj.get_iqama_delay(prayer.prayer),
        })
    
    return render(request, 'scheduler/settings.html', {
        'form': form, 
        'prayers': prayers,
        'settings_obj': settings_obj,
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
                
            sessions = Session.objects.filter(start_time__gte=start_dt, start_time__lt=end_dt,student__is_active=True)
        except Exception:
            sessions = Session.objects.filter(student__is_active=True) 
    else:
        sessions = Session.objects.filter(student__is_active=True) 
        
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
            count, errors = sync_future_sessions_for_student(student, weeks=4)
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
            count, errors = sync_future_sessions_for_student(student, weeks=4)
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
            count, errors = sync_future_sessions_for_student(student, weeks=4)
            if count > 0:
                messages.info(request, f"Regenerated {count} sessions with updated exception.")
            if errors:
                for err in errors:
                    messages.warning(request, err)
            
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
        count, errors = sync_future_sessions_for_student(student, weeks=4)
        if count > 0:
            messages.info(request, f"Regenerated {count} sessions after deleting exception.")
        if errors:
            for err in errors:
                messages.warning(request, err)
    
    return redirect('scheduler:manage_exceptions', student_id=student.id)


def recommend_session_time(request):
    """AJAX endpoint to recommend the next available time slot without conflicts."""
    from django.http import JsonResponse
    from django.utils.dateparse import parse_datetime
    from .services import validate_session, ensure_aware, to_cairo, CAIRO_TZ
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        student_id = int(request.POST.get('student_id'))
        start_time_str = request.POST.get('start_time')  # e.g., "2026-05-07T15:00"
        duration = int(request.POST.get('duration') or 60)
        
        student = get_object_or_404(Student, id=student_id)
        
        # Parse the start time
        start_dt = parse_datetime(start_time_str)
        if not start_dt:
            return JsonResponse({'error': 'Invalid start time format'}, status=400)
        
        start_dt = ensure_aware(start_dt)
        
        # Search for the next available slot within the next 7 days
        max_days = 7
        slot_duration = 15  # Check in 15-minute increments
        
        for day_offset in range(max_days):
            current_date = to_cairo(start_dt).date() + timedelta(days=day_offset)
            
            # Start searching from 8:00 AM to 8:00 PM each day
            search_start_time = datetime.min.time().replace(hour=0)
            search_end_time = datetime.min.time().replace(hour=24)
            
            search_start = CAIRO_TZ.localize(datetime.combine(current_date, search_start_time))
            search_end = CAIRO_TZ.localize(datetime.combine(current_date, search_end_time))
            
            # If it's the first day, start from the originally requested time or 8 AM, whichever is later
            if day_offset == 0:
                original_time = to_cairo(start_dt).time()
                if original_time >= search_start_time and original_time <= search_end_time:
                    current_slot = start_dt
                else:
                    current_slot = search_start
            else:
                current_slot = search_start
            
            while current_slot + timedelta(minutes=duration) <= search_end:
                errors = validate_session(current_slot, duration, student_id=student_id)
                if not errors:
                    # Found a free slot!
                    return JsonResponse({
                        'success': True,
                        'recommended_time': current_slot.isoformat(),
                        'message': f"Found available slot on {current_slot.strftime('%A, %B %d at %H:%M')}"
                    })
                
                # Move to next 15-minute slot
                current_slot += timedelta(minutes=slot_duration)
        
        return JsonResponse({
            'success': False,
            'message': f"No available slots found in the next {max_days} days during working hours (8 AM - 8 PM)"
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
