"""
Views for TutorSys scheduler app.

Timezone convention:
  - All datetimes stored in UTC in the database.
  - Tutor local timezone: Africa/Cairo.
  - Student times shown in their own timezone additionally.
  - Forms accept Cairo time; SessionForm (edit) displays Cairo via __init__.
"""
import json
import pytz
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Student, Subscription, Session, RecurringSchedule, WorkingHours, ExceptionDay, PrayerTime, DEFAULT_HOURLY_RATE
from .forms import (
    StudentForm, SubscriptionForm, SessionForm, QuickSessionForm,
    RecurringScheduleForm, WorkingHoursForm, ExceptionDayForm, PrayerTimeForm,
    DateRangeForm, SessionStatusForm, COUNTRY_TIMEZONE_MAP,
)
from .services import (
    validate_session, suggest_next_slot, quick_reschedule,
    validate_makeup_session, get_occupancy_rate,
    to_cairo, to_student_tz, make_aware_cairo, ensure_aware, CAIRO_TZ,
    generate_sessions_from_schedule, preview_sessions_from_schedule,
    delete_future_recurring_sessions, regenerate_schedule,
)

COUNTRY_FLAGS = {
    'Egypt': '🇪🇬', 'Germany': '🇩🇪', 'France': '🇫🇷',
    'United Kingdom': '🇬🇧', 'United States': '🇺🇸', 'USA': '🇺🇸',
    'Saudi Arabia': '🇸🇦', 'UAE': '🇦🇪', 'Kuwait': '🇰🇼',
    'Lebanon': '🇱🇧', 'Jordan': '🇯🇴', 'Iraq': '🇮🇶',
    'Japan': '🇯🇵', 'China': '🇨🇳', 'India': '🇮🇳',
    'Australia': '🇦🇺', 'Canada': '🇨🇦',
}


def _session_tz_payload(session):
    cairo_start = to_cairo(session.start_time)
    cairo_end = to_cairo(session.end_time)
    student_start = to_student_tz(session.start_time, session.student)
    student_end = to_student_tz(session.end_time, session.student)
    student_tz_name = session.student.timezone or 'UTC'
    return {
        'cairo_start': cairo_start,
        'cairo_end': cairo_end,
        'student_start': student_start,
        'student_end': student_end,
        'student_tz': student_tz_name,
        'same_tz': student_tz_name == 'Africa/Cairo',
        'flag': COUNTRY_FLAGS.get(session.student.country, '🌍'),
    }


def dashboard(request):
    today = timezone.localdate()
    now = timezone.now()
    today_sessions = Session.objects.filter(start_time__date=today).select_related('student').order_by('start_time')
    upcoming = Session.objects.filter(start_time__gte=now, status='scheduled').select_related('student').order_by('start_time')[:5]
    today_earnings = sum(s.earnings for s in today_sessions.filter(status='completed'))
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_earnings = sum(s.earnings for s in Session.objects.filter(start_time__date__gte=week_start, start_time__date__lte=week_end, status='completed').select_related('student'))
    total_students = Student.objects.filter(is_active=True).count()
    scheduled_today = list(today_sessions.filter(status='scheduled'))
    conflicts = [(s1, s2) for i, s1 in enumerate(scheduled_today) for s2 in scheduled_today[i + 1:] if s1.start_time < s2.end_time and s2.start_time < s1.end_time]
    return render(request, 'scheduler/dashboard.html', {'today': today, 'today_sessions': today_sessions, 'upcoming': upcoming, 'today_earnings': today_earnings, 'week_earnings': week_earnings, 'total_students': total_students, 'total_sessions_today': today_sessions.count(), 'conflicts': conflicts})


def student_list(request):
    students = Student.objects.prefetch_related('subscriptions').all().order_by('name')
    return render(request, 'scheduler/student_list.html', {'students': students})


def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        sub_form = SubscriptionForm(request.POST)
        if form.is_valid() and sub_form.is_valid():
            student = form.save()
            sub = sub_form.save(commit=False)
            sub.student = student
            sub.save()
            messages.success(request, _('Student %(name)s created successfully.') % {'name': student.name})
            return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = StudentForm(initial={'timezone': 'Africa/Cairo'})
        sub_form = SubscriptionForm()
    return render(request, 'scheduler/student_form.html', {'form': form, 'sub_form': sub_form, 'title': _('Add New Student'), 'country_timezone_map_json': json.dumps(COUNTRY_TIMEZONE_MAP)})


def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    sessions = student.sessions.select_related('student', 'recurring_schedule').order_by('-start_time')[:20]
    schedules = student.recurring_schedules.filter(is_active=True).order_by('day_of_week', 'start_time')
    try:
        tz = pytz.timezone(student.timezone or 'UTC')
        tz_offset = datetime.now(tz).strftime('%z')
        tz_label = f"{student.timezone} (UTC{tz_offset[:3]}:{tz_offset[3:]})"
    except Exception:
        tz_label = student.timezone or 'UTC'
    return render(request, 'scheduler/student_detail.html', {'student': student, 'sessions': sessions, 'subscription': student.active_subscription, 'schedules': schedules, 'tz_label': tz_label, 'flag': COUNTRY_FLAGS.get(student.country, '🌍')})


def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, _('Student updated.'))
            return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = StudentForm(instance=student)
    return render(request, 'scheduler/student_form.html', {'form': form, 'title': _('Edit %(name)s') % {'name': student.name}, 'student': student, 'country_timezone_map_json': json.dumps(COUNTRY_TIMEZONE_MAP)})


def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete()
        messages.success(request, _('Student deleted.'))
        return redirect('scheduler:student_list')
    return render(request, 'scheduler/confirm_delete.html', {'object': student, 'object_type': _('Student')})


def subscription_edit(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    sub = student.subscriptions.filter(is_active=True).first()
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=sub)
        if form.is_valid():
            new_sub = form.save(commit=False)
            new_sub.student = student
            if sub and sub.pk:
                sub.is_active = False
                sub.save()
                new_sub.pk = None
            new_sub.is_active = True
            new_sub.save()
            messages.success(request, _('Subscription updated.'))
            return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = SubscriptionForm(instance=sub)
    return render(request, 'scheduler/subscription_form.html', {'form': form, 'student': student, 'default_hourly_rate': DEFAULT_HOURLY_RATE})


def recurring_schedule_create(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    subscription = student.active_subscription
    preview = None
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        form = RecurringScheduleForm(request.POST, student=student)
        if form.is_valid():
            if action == 'preview':
                temp = RecurringSchedule(student=student, subscription=subscription, day_of_week=form.cleaned_data['day_of_week'], start_time=form.cleaned_data['start_time'], duration=form.cleaned_data['duration'], is_active=form.cleaned_data['is_active'])
                weeks = form.cleaned_data.get('weeks_to_generate', 4)
                preview = preview_sessions_from_schedule(temp, weeks=weeks)
                return render(request, 'scheduler/recurring_schedule_form.html', {'form': form, 'student': student, 'subscription': subscription, 'preview': preview, 'title': _('Add Recurring Schedule')})
            schedule = form.save(commit=False)
            schedule.student = student
            schedule.subscription = subscription
            schedule.save()
            weeks = form.cleaned_data.get('weeks_to_generate', 4)
            created, skipped = generate_sessions_from_schedule(schedule, weeks=weeks)
            msg = _('Recurring schedule saved. %(count)s session(s) generated.') % {'count': created}
            if skipped:
                msg += ' ' + _('%(count)s slot(s) skipped due to conflicts.') % {'count': len(skipped)}
            messages.success(request, msg)
            return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = RecurringScheduleForm(student=student)
    return render(request, 'scheduler/recurring_schedule_form.html', {'form': form, 'student': student, 'subscription': subscription, 'preview': preview, 'title': _('Add Recurring Schedule')})


def recurring_schedule_edit(request, pk):
    schedule = get_object_or_404(RecurringSchedule, pk=pk)
    student = schedule.student
    subscription = student.active_subscription
    preview = None
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        form = RecurringScheduleForm(request.POST, instance=schedule, student=student)
        if form.is_valid():
            if action == 'preview':
                temp = RecurringSchedule(student=student, subscription=subscription, day_of_week=form.cleaned_data['day_of_week'], start_time=form.cleaned_data['start_time'], duration=form.cleaned_data['duration'], is_active=form.cleaned_data['is_active'])
                weeks = form.cleaned_data.get('weeks_to_generate', 4)
                preview = preview_sessions_from_schedule(temp, weeks=weeks)
                return render(request, 'scheduler/recurring_schedule_form.html', {'form': form, 'student': student, 'subscription': subscription, 'schedule': schedule, 'preview': preview, 'title': _('Edit Schedule')})
            regenerate = request.POST.get('regenerate') == '1'
            form.save()
            if regenerate:
                weeks = form.cleaned_data.get('weeks_to_generate', 4)
                created, skipped = regenerate_schedule(schedule, weeks=weeks)
                msg = _('Schedule updated and regenerated. %(count)s session(s) created.') % {'count': created}
                if skipped:
                    msg += ' ' + _('%(count)s slot(s) skipped.') % {'count': len(skipped)}
                messages.success(request, msg)
            else:
                messages.success(request, _('Schedule updated (existing sessions unchanged).'))
            return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = RecurringScheduleForm(instance=schedule, student=student)
    return render(request, 'scheduler/recurring_schedule_form.html', {'form': form, 'student': student, 'subscription': subscription, 'schedule': schedule, 'preview': preview, 'title': _('Edit Recurring Schedule')})


def recurring_schedule_delete(request, pk):
    schedule = get_object_or_404(RecurringSchedule, pk=pk)
    student = schedule.student
    if request.method == 'POST':
        delete_future = request.POST.get('delete_future') == '1'
        if delete_future:
            delete_future_recurring_sessions(schedule)
        schedule.is_active = False
        schedule.save()
        msg = _('Recurring schedule deactivated.')
        if delete_future:
            msg += ' ' + _('Future sessions deleted.')
        messages.success(request, msg)
        return redirect('scheduler:student_detail', pk=student.pk)
    future_count = Session.objects.filter(recurring_schedule=schedule, status='scheduled', is_override=False, start_time__gt=timezone.now()).count()
    return render(request, 'scheduler/recurring_schedule_confirm_delete.html', {'schedule': schedule, 'future_count': future_count})


def recurring_schedule_generate(request, pk):
    schedule = get_object_or_404(RecurringSchedule, pk=pk)
    if request.method == 'POST':
        weeks = int(request.POST.get('weeks', 4))
        created, skipped = generate_sessions_from_schedule(schedule, weeks=weeks)
        msg = _('%(count)s session(s) generated.') % {'count': created}
        if skipped:
            msg += ' ' + _('%(count)s slot(s) skipped.') % {'count': len(skipped)}
        messages.success(request, msg)
    return redirect('scheduler:student_detail', pk=schedule.student.pk)


def api_preview_schedule(request):
    try:
        day_of_week = int(request.GET.get('day_of_week', 6))
        start_time_str = request.GET.get('start_time', '17:00')
        duration = int(request.GET.get('duration', 60))
        weeks = int(request.GET.get('weeks', 4))
        from datetime import time as dt_time
        h, m = map(int, start_time_str.split(':'))
        start_time = dt_time(h, m)
    except (ValueError, TypeError):
        return JsonResponse({'error': _('Invalid parameters')}, status=400)
    temp = RecurringSchedule(student_id=None, day_of_week=day_of_week, start_time=start_time, duration=duration)
    preview = preview_sessions_from_schedule(temp, weeks=weeks)
    return JsonResponse([{'date': p['date'].strftime('%Y-%m-%d'), 'weekday': p['date'].strftime('%A'), 'start': p['start_dt'].strftime('%H:%M'), 'end': p['end_dt'].strftime('%H:%M'), 'valid': p['valid'], 'already_exists': p['already_exists'], 'errors': p['errors']} for p in preview], safe=False)


def calendar_view(request):
    return render(request, 'scheduler/calendar.html', {'students': Student.objects.filter(is_active=True), 'suggest_form': QuickSessionForm()})


def api_sessions(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    qs = Session.objects.select_related('student', 'recurring_schedule')
    if start:
        qs = qs.filter(end_time__gte=start)
    if end:
        qs = qs.filter(start_time__lte=end)
    STATUS_COLORS = {'scheduled': '#3b82f6', 'completed': '#10b981', 'cancelled': '#ef4444', 'missed': '#f59e0b'}
    events = []
    for s in qs:
        payload = _session_tz_payload(s)
        title = s.student.name
        if s.student.country:
            title = f"{payload['flag']} {title}"
        if s.is_makeup:
            title += ' [Makeup]'
        if s.is_override:
            title += ' ✏️'
        color = STATUS_COLORS.get(s.status, '#6366f1')
        border_color = '#7c3aed' if s.is_override else color
        events.append({'id': s.pk, 'title': title, 'start': s.start_time.isoformat(), 'end': s.end_time.isoformat(), 'color': color, 'borderColor': border_color, 'extendedProps': {'status': s.status, 'student': s.student.name, 'country': s.student.country or '', 'flag': payload['flag'], 'duration': s.duration_minutes, 'is_makeup': s.is_makeup, 'is_override': s.is_override, 'is_recurring': bool(s.recurring_schedule_id), 'session_id': s.pk, 'cairo_start': payload['cairo_start'].strftime('%H:%M'), 'cairo_end': payload['cairo_end'].strftime('%H:%M'), 'student_start': payload['student_start'].strftime('%H:%M'), 'student_end': payload['student_end'].strftime('%H:%M'), 'student_tz': payload['student_tz'], 'same_tz': payload['same_tz']}})
    return JsonResponse(events, safe=False)


def api_suggest_slot(request):
    duration = int(request.GET.get('duration', 60))
    from_dt = None
    from_dt_str = request.GET.get('from')
    if from_dt_str:
        try:
            from_dt = datetime.fromisoformat(from_dt_str)
            if timezone.is_naive(from_dt):
                from_dt = CAIRO_TZ.localize(from_dt)
        except (ValueError, AttributeError):
            pass
    slot = suggest_next_slot(duration, from_dt=from_dt)
    if slot:
        end = slot + timedelta(minutes=duration)
        return JsonResponse({'start': slot.strftime('%Y-%m-%dT%H:%M'), 'end': end.strftime('%Y-%m-%dT%H:%M'), 'display': f"{slot.strftime('%A, %B %-d · %H:%M')} – {end.strftime('%H:%M')} (Cairo)"})
    return JsonResponse({'error': _('No available slot found in the next 14 days.')}, status=404)


def session_list(request):
    sessions = Session.objects.select_related('student', 'recurring_schedule').order_by('-start_time')
    status_filter = request.GET.get('status', '')
    student_filter = request.GET.get('student', '')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    if student_filter:
        sessions = sessions.filter(student_id=student_filter)
    return render(request, 'scheduler/session_list.html', {'sessions': sessions[:50], 'students': Student.objects.filter(is_active=True).order_by('name'), 'status_filter': status_filter, 'student_filter': student_filter})


def session_create(request):
    if request.method == 'POST':
        form = QuickSessionForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data['date']
            t = form.cleaned_data['start_time']
            duration = int(form.cleaned_data['duration'])
            student = form.cleaned_data['student']
            start_dt = make_aware_cairo(d, t)
            end_dt = start_dt + timedelta(minutes=duration)
            errors = validate_session(start_dt, end_dt)
            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                Session.objects.create(student=student, start_time=start_dt, end_time=end_dt, is_recurring=form.cleaned_data.get('is_recurring', False), notes=form.cleaned_data.get('notes', ''))
                messages.success(request, _('Session created for %(name)s.') % {'name': student.name})
                return redirect('scheduler:calendar')
    else:
        initial = {}
        if request.GET.get('suggest') == '1':
            slot = suggest_next_slot(60)
            if slot:
                initial['date'] = slot.date()
                initial['start_time'] = slot.time()
        form = QuickSessionForm(initial=initial)
    return render(request, 'scheduler/session_form.html', {'form': form, 'title': _('New Session')})


def session_detail(request, pk):
    session = get_object_or_404(Session, pk=pk)
    return render(request, 'scheduler/session_detail.html', {'session': session, 'status_form': SessionStatusForm(instance=session), 'display': _session_tz_payload(session)})


def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            s = form.save(commit=False)
            s.start_time = ensure_aware(s.start_time)
            s.end_time = ensure_aware(s.end_time)
            errors = validate_session(s.start_time, s.end_time, exclude_session_id=session.pk)
            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                if session.recurring_schedule_id:
                    s.is_override = True
                s.save()
                messages.success(request, _('Session updated.'))
                return redirect('scheduler:session_detail', pk=session.pk)
    else:
        form = SessionForm(instance=session)
    return render(request, 'scheduler/session_form.html', {'form': form, 'title': _('Edit Session'), 'session': session})


def session_delete(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        session.delete()
        messages.success(request, _('Session deleted.'))
        return redirect('scheduler:session_list')
    return render(request, 'scheduler/confirm_delete.html', {'object': session, 'object_type': _('Session')})


def session_status_update(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionStatusForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, _('Session status updated.'))
        else:
            for error in form.errors.values():
                for item in error:
                    messages.error(request, item)
    return redirect('scheduler:session_detail', pk=session.pk)


def session_reschedule(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            s = form.save(commit=False)
            s.start_time = ensure_aware(s.start_time)
            s.end_time = ensure_aware(s.end_time)
            errors = validate_session(s.start_time, s.end_time, exclude_session_id=session.pk)
            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                if session.recurring_schedule_id:
                    s.is_override = True
                s.save()
                messages.success(request, _('Session rescheduled.'))
                return redirect('scheduler:session_detail', pk=session.pk)
    else:
        form = SessionForm(instance=session)
    return render(request, 'scheduler/session_form.html', {'form': form, 'title': _('Reschedule Session'), 'session': session})


def session_makeup(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = QuickSessionForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data['date']
            t = form.cleaned_data['start_time']
            duration = int(form.cleaned_data['duration'])
            start_dt = make_aware_cairo(d, t)
            end_dt = start_dt + timedelta(minutes=duration)
            errors = validate_makeup_session(start_dt, end_dt, student=session.student)
            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                Session.objects.create(
                    student=session.student,
                    start_time=start_dt,
                    end_time=end_dt,
                    is_makeup=True,
                    notes=form.cleaned_data.get('notes', ''),
                )
                messages.success(request, _('Makeup session created.'))
                return redirect('scheduler:session_list')
    else:
        form = QuickSessionForm(initial={'student': session.student})
    return render(request, 'scheduler/session_form.html', {'form': form, 'title': _('Makeup Session'), 'session': session})


def working_hours(request):
    hours = WorkingHours.objects.all().order_by('day_of_week')
    if request.method == 'POST':
        form = WorkingHoursForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Working hours saved.'))
            return redirect('scheduler:working_hours')
    else:
        form = WorkingHoursForm()
    return render(request, 'scheduler/working_hours.html', {'hours': hours, 'form': form})


def exception_days(request):
    exceptions = ExceptionDay.objects.all().order_by('-date')
    if request.method == 'POST':
        form = ExceptionDayForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Exception day added.'))
            return redirect('scheduler:exception_days')
    else:
        form = ExceptionDayForm()
    return render(request, 'scheduler/exception_days.html', {'exceptions': exceptions, 'form': form})


def exception_day_delete(request, pk):
    exception_day = get_object_or_404(ExceptionDay, pk=pk)
    if request.method == 'POST':
        exception_day.delete()
        messages.success(request, _('Exception day deleted.'))
        return redirect('scheduler:exception_days')
    return render(request, 'scheduler/confirm_delete.html', {'object': exception_day, 'object_type': _('Exception Day')})


def prayer_times(request):
    prayer_times_qs = PrayerTime.objects.all().order_by('name')
    if request.method == 'POST':
        form = PrayerTimeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Prayer time saved.'))
            return redirect('scheduler:prayer_times')
    else:
        form = PrayerTimeForm()
    return render(request, 'scheduler/prayer_times.html', {'prayer_times': prayer_times_qs, 'form': form})


def prayer_time_delete(request, pk):
    prayer_time = get_object_or_404(PrayerTime, pk=pk)
    if request.method == 'POST':
        prayer_time.delete()
        messages.success(request, _('Prayer time deleted.'))
        return redirect('scheduler:prayer_times')
    return render(request, 'scheduler/confirm_delete.html', {'object': prayer_time, 'object_type': _('Prayer Time')})


def reports(request):
    return render(request, 'scheduler/reports.html', {
        'students': Student.objects.filter(is_active=True).count(),
        'sessions': Session.objects.count(),
        'earnings': Session.objects.filter(status='completed').aggregate(total=models.Sum('earnings'))['total'] or 0,
    })


def analytics(request):
    return render(request, 'scheduler/analytics.html', {
        'occupancy': get_occupancy_rate(),
    })
