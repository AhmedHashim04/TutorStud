import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Student, Subscription, Session, WorkingHours, ExceptionDay, PrayerTime
from .forms import StudentForm, SubscriptionForm, SessionForm, QuickSessionForm, WorkingHoursForm, ExceptionDayForm, PrayerTimeForm, DateRangeForm, SessionStatusForm
from .services import validate_session, suggest_next_slot, quick_reschedule, validate_makeup_session, get_occupancy_rate, to_cairo, make_aware_cairo, to_student_tz, CAIRO_TZ
import pytz


def _session_display_payload(session):
    student_tz = pytz.timezone(session.student.timezone or 'UTC')
    cairo_start = to_cairo(session.start_time)
    cairo_end = to_cairo(session.end_time)
    student_start = to_student_tz(session.start_time, session.student)
    student_end = to_student_tz(session.end_time, session.student)
    offset_hours = int((student_start.utcoffset().total_seconds() if student_start.utcoffset() else 0) / 3600)
    return {
        'cairo_start': cairo_start,
        'cairo_end': cairo_end,
        'student_start': student_start,
        'student_end': student_end,
        'student_timezone': session.student.timezone,
        'student_country': session.student.country,
        'time_diff_hours': offset_hours,
        'student_flag': {'Egypt': '🇪🇬', 'Germany': '🇩🇪', 'United States': '🇺🇸', 'United Kingdom': '🇬🇧', 'Saudi Arabia': '🇸🇦', 'UAE': '🇦🇪', 'Japan': '🇯🇵'}.get(session.student.country, '🌍'),
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
    total_sessions_today = today_sessions.count()
    scheduled_today = list(today_sessions.filter(status='scheduled'))
    conflicts = []
    for i, s1 in enumerate(scheduled_today):
        for s2 in scheduled_today[i + 1:]:
            if s1.start_time < s2.end_time and s2.start_time < s1.end_time:
                conflicts.append((s1, s2))
    return render(request, 'scheduler/dashboard.html', {'today': today, 'today_sessions': today_sessions, 'upcoming': upcoming, 'today_earnings': today_earnings, 'week_earnings': week_earnings, 'total_students': total_students, 'total_sessions_today': total_sessions_today, 'conflicts': conflicts})


def student_list(request):
    return render(request, 'scheduler/student_list.html', {'students': Student.objects.prefetch_related('subscriptions').all()})


def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        sub_form = SubscriptionForm(request.POST)
        if form.is_valid() and sub_form.is_valid():
            student = form.save()
            sub = sub_form.save(commit=False)
            sub.student = student
            sub.save()
            messages.success(request, f"Student '{student.name}' created successfully.")
            return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = StudentForm(initial={'timezone': 'Africa/Cairo'})
        sub_form = SubscriptionForm()
    return render(request, 'scheduler/student_form.html', {'form': form, 'sub_form': sub_form, 'title': 'Add New Student'})


def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    sessions = student.sessions.select_related('student').order_by('-start_time')[:20]
    return render(request, 'scheduler/student_detail.html', {'student': student, 'sessions': sessions, 'subscription': student.active_subscription})


def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save(); messages.success(request, 'Student updated.'); return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = StudentForm(instance=student)
    return render(request, 'scheduler/student_form.html', {'form': form, 'title': f'Edit {student.name}', 'student': student})


def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete(); messages.success(request, 'Student deleted.'); return redirect('scheduler:student_list')
    return render(request, 'scheduler/confirm_delete.html', {'object': student, 'object_type': 'Student'})


def subscription_edit(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    sub = student.subscriptions.filter(is_active=True).first()
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=sub)
        if form.is_valid():
            new_sub = form.save(commit=False)
            new_sub.student = student
            if sub:
                sub.is_active = False; sub.save()
            new_sub.pk = None; new_sub.is_active = True; new_sub.save(); messages.success(request, 'Subscription updated.'); return redirect('scheduler:student_detail', pk=student.pk)
    else:
        form = SubscriptionForm(instance=sub)
    return render(request, 'scheduler/subscription_form.html', {'form': form, 'student': student})


def calendar_view(request):
    return render(request, 'scheduler/calendar.html', {'students': Student.objects.filter(is_active=True), 'suggest_form': QuickSessionForm()})


def api_sessions(request):
    start = request.GET.get('start'); end = request.GET.get('end')
    qs = Session.objects.select_related('student')
    if start: qs = qs.filter(end_time__gte=start)
    if end: qs = qs.filter(start_time__lte=end)
    STATUS_COLORS = {'scheduled': '#3b82f6', 'completed': '#10b981', 'cancelled': '#ef4444', 'missed': '#f59e0b'}
    events = []
    for s in qs:
        payload = _session_display_payload(s)
        events.append({'id': s.pk, 'title': f"{s.student.name} ({s.student.timezone})" + (" [Makeup]" if s.is_makeup else ""), 'start': s.start_time.isoformat(), 'end': s.end_time.isoformat(), 'color': STATUS_COLORS.get(s.status, '#6366f1'), 'extendedProps': {'status': s.status, 'student': s.student.name, 'duration': s.duration_minutes, 'is_makeup': s.is_makeup, 'session_id': s.pk, 'cairo_display': f"{payload['cairo_start'].strftime('%H:%M')} - {payload['cairo_end'].strftime('%H:%M')}", 'student_display': f"{payload['student_start'].strftime('%H:%M')} - {payload['student_end'].strftime('%H:%M')}", 'student_timezone': payload['student_timezone'], 'student_country': payload['student_country'], 'student_flag': payload['student_flag'], 'time_diff_hours': payload['time_diff_hours']}})
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
        except Exception:
            pass
    slot = suggest_next_slot(duration, from_dt=from_dt)
    if slot:
        end = slot + timedelta(minutes=duration)
        return JsonResponse({'start': slot.strftime('%Y-%m-%dT%H:%M'), 'end': end.strftime('%Y-%m-%dT%H:%M')})
    return JsonResponse({'error': 'No slot found in the next 14 days.'}, status=404)


def session_list(request):
    sessions = Session.objects.select_related('student').order_by('-start_time')
    status_filter = request.GET.get('status', ''); student_filter = request.GET.get('student', '')
    if status_filter: sessions = sessions.filter(status=status_filter)
    if student_filter: sessions = sessions.filter(student_id=student_filter)
    return render(request, 'scheduler/session_list.html', {'sessions': sessions[:50], 'students': Student.objects.filter(is_active=True), 'status_filter': status_filter, 'student_filter': student_filter})


def session_create(request):
    if request.method == 'POST':
        form = QuickSessionForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data['date']; t = form.cleaned_data['start_time']; duration = int(form.cleaned_data['duration']); student = form.cleaned_data['student']
            start_dt = make_aware_cairo(d, t); end_dt = start_dt + timedelta(minutes=duration)
            errors = validate_session(start_dt, end_dt)
            if errors:
                for e in errors: messages.error(request, e)
            else:
                Session.objects.create(student=student, start_time=start_dt.astimezone(timezone.utc), end_time=end_dt.astimezone(timezone.utc), is_recurring=form.cleaned_data.get('is_recurring', False), notes=form.cleaned_data.get('notes', ''))
                messages.success(request, f"Session created for {student.name}."); return redirect('scheduler:calendar')
    else:
        initial = {}; suggest = request.GET.get('suggest')
        if suggest == '1':
            slot = suggest_next_slot(60)
            if slot: initial['date'] = slot.date(); initial['start_time'] = slot.time()
        form = QuickSessionForm(initial=initial)
    return render(request, 'scheduler/session_form.html', {'form': form, 'title': 'New Session'})


def session_detail(request, pk):
    session = get_object_or_404(Session, pk=pk)
    return render(request, 'scheduler/session_detail.html', {'session': session, 'status_form': SessionStatusForm(instance=session), 'display': _session_display_payload(session)})


def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            s = form.save(commit=False)
            errors = validate_session(s.start_time, s.end_time, exclude_session_id=session.pk)
            if errors:
                for e in errors: messages.error(request, e)
            else:
                s.save(); messages.success(request, 'Session updated.'); return redirect('scheduler:session_detail', pk=session.pk)
    else:
        form = SessionForm(instance=session)
    return render(request, 'scheduler/session_form.html', {'form': form, 'title': 'Edit Session', 'session': session})


def session_delete(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        session.delete(); messages.success(request, 'Session deleted.'); return redirect('scheduler:session_list')
    return render(request, 'scheduler/confirm_delete.html', {'object': session, 'object_type': 'Session'})


def session_status_update(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionStatusForm(request.POST, instance=session)
        if form.is_valid():
            form.save(); messages.success(request, f"Session status updated to '{session.status}'.")
    return redirect('scheduler:session_detail', pk=pk)


def session_reschedule(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        new_start, new_end = quick_reschedule(session)
        if new_start:
            session.start_time = new_start.astimezone(timezone.utc); session.end_time = new_end.astimezone(timezone.utc); session.save(); messages.success(request, f"Session rescheduled to {new_start.strftime('%Y-%m-%d %H:%M')}.")
        else:
            messages.error(request, 'No available slot found in the next 14 days.')
    return redirect('scheduler:session_detail', pk=pk)


def session_makeup(request, pk):
    original = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = QuickSessionForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data['date']; t = form.cleaned_data['start_time']; duration = int(form.cleaned_data['duration']); student = form.cleaned_data['student']
            start_dt = make_aware_cairo(d, t); end_dt = start_dt + timedelta(minutes=duration)
            errors = validate_makeup_session(original, start_dt, end_dt)
            if errors:
                for e in errors: messages.error(request, e)
            else:
                Session.objects.create(student=student, start_time=start_dt.astimezone(timezone.utc), end_time=end_dt.astimezone(timezone.utc), is_makeup=True, original_session=original, notes=f"Makeup for session on {original.start_time.strftime('%Y-%m-%d')}")
                original.status = 'missed'; original.save(); messages.success(request, 'Make-up session created.'); return redirect('scheduler:session_detail', pk=original.pk)
    else:
        sub = original.student.active_subscription
        form = QuickSessionForm(initial={'student': original.student, 'duration': sub.session_duration if sub else 60})
    return render(request, 'scheduler/session_makeup.html', {'form': form, 'original': original})


def working_hours(request):
    instances = {wh.weekday: wh for wh in WorkingHours.objects.all()}
    if request.method == 'POST':
        for weekday, _ in WorkingHours._meta.get_field('weekday').choices:
            wh = instances.get(weekday); prefix = f'day_{weekday}'; is_working = request.POST.get(f'{prefix}_is_working') == 'on'; start = request.POST.get(f'{prefix}_start'); end = request.POST.get(f'{prefix}_end')
            if start and end:
                if wh:
                    wh.is_working = is_working; wh.start_time = start; wh.end_time = end; wh.save()
                else:
                    WorkingHours.objects.create(weekday=weekday, start_time=start, end_time=end, is_working=is_working)
        messages.success(request, 'Working hours updated.'); return redirect('scheduler:working_hours')
    days = [{'weekday': weekday, 'name': name, 'wh': instances.get(weekday)} for weekday, name in WorkingHours._meta.get_field('weekday').choices]
    return render(request, 'scheduler/working_hours.html', {'days': days})


def exception_days(request):
    exceptions = ExceptionDay.objects.all().order_by('date'); form = ExceptionDayForm()
    if request.method == 'POST':
        form = ExceptionDayForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, 'Exception day added.'); return redirect('scheduler:exception_days')
    return render(request, 'scheduler/exception_days.html', {'form': form, 'exceptions': exceptions})


def exception_day_delete(request, pk):
    exc = get_object_or_404(ExceptionDay, pk=pk)
    if request.method == 'POST': exc.delete(); messages.success(request, 'Exception day removed.')
    return redirect('scheduler:exception_days')


def prayer_times(request):
    prayers = PrayerTime.objects.order_by('-date', 'adhan_time')[:30]; form = PrayerTimeForm()
    if request.method == 'POST':
        form = PrayerTimeForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, 'Prayer time saved.'); return redirect('scheduler:prayer_times')
    return render(request, 'scheduler/prayer_times.html', {'form': form, 'prayers': prayers})


def prayer_time_delete(request, pk):
    pt = get_object_or_404(PrayerTime, pk=pk)
    if request.method == 'POST': pt.delete(); messages.success(request, 'Prayer time deleted.')
    return redirect('scheduler:prayer_times')


def reports(request):
    today = timezone.localdate(); form = DateRangeForm(request.GET or None); start_date = today.replace(day=1); end_date = today; student_filter = None
    if form.is_valid(): start_date = form.cleaned_data.get('start_date') or start_date; end_date = form.cleaned_data.get('end_date') or end_date; student_filter = form.cleaned_data.get('student')
    sessions_qs = Session.objects.filter(start_time__date__gte=start_date, start_time__date__lte=end_date).select_related('student')
    if student_filter: sessions_qs = sessions_qs.filter(student=student_filter)
    completed = sessions_qs.filter(status='completed'); cancelled = sessions_qs.filter(status='cancelled'); missed = sessions_qs.filter(status='missed')
    total_income = sum(s.earnings for s in completed); completed_count = completed.count(); cancelled_count = cancelled.count(); missed_count = missed.count(); total_sessions = sessions_qs.count()
    student_breakdown = []
    for student in Student.objects.filter(is_active=True):
        qs = completed.filter(student=student); count = qs.count()
        if count > 0: student_breakdown.append({'student': student, 'sessions': count, 'income': sum(s.earnings for s in qs)})
    student_breakdown.sort(key=lambda x: x['income'], reverse=True)
    daily_data = {}
    for s in completed:
        day = to_cairo(s.start_time).strftime('%Y-%m-%d'); daily_data[day] = float(daily_data.get(day, 0)) + float(s.earnings)
    occupancy = get_occupancy_rate(start_date, end_date)
    country_data = {}
    for s in sessions_qs:
        country = s.student.country or 'Unknown'
        country_data[country] = country_data.get(country, 0) + 1
    return render(request, 'scheduler/reports.html', {'form': form, 'start_date': start_date, 'end_date': end_date, 'total_income': total_income, 'completed_count': completed_count, 'cancelled_count': cancelled_count, 'missed_count': missed_count, 'total_sessions': total_sessions, 'student_breakdown': student_breakdown, 'daily_data_json': json.dumps(daily_data), 'occupancy': occupancy, 'country_data_json': json.dumps(country_data)})


def analytics(request):
    today = timezone.localdate(); thirty_days_ago = today - timedelta(days=30)
    sessions = Session.objects.filter(start_time__date__gte=thirty_days_ago).select_related('student')
    completed = sessions.filter(status='completed'); total = sessions.count(); cancellation_rate = round((sessions.filter(status='cancelled').count() / total * 100), 1) if total else 0
    student_stats = []
    for student in Student.objects.filter(is_active=True):
        stu_sessions = sessions.filter(student=student); total_s = stu_sessions.count()
        if total_s == 0: continue
        completed_s = stu_sessions.filter(status='completed').count(); cancelled_s = stu_sessions.filter(status='cancelled').count(); student_stats.append({'student': student, 'total': total_s, 'completed': completed_s, 'cancelled': cancelled_s, 'rate': round(completed_s / total_s * 100, 1), 'country': student.country or 'Unknown'})
    student_stats.sort(key=lambda x: x['rate'], reverse=True)
    hour_data = {}
    for s in completed: hour = to_cairo(s.start_time).hour; hour_data[hour] = hour_data.get(hour, 0) + 1
    weekly_data = {}
    for i in range(7, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * i); week_end = week_start + timedelta(days=6); label = week_start.strftime('%b %d'); weekly_data[label] = Session.objects.filter(start_time__date__gte=week_start, start_time__date__lte=week_end, status='completed').count()
    occupancy = get_occupancy_rate(thirty_days_ago, today)
    status_dist = {'Completed': completed.count(), 'Cancelled': sessions.filter(status='cancelled').count(), 'Missed': sessions.filter(status='missed').count(), 'Scheduled': sessions.filter(status='scheduled').count()}
    country_dist = {}
    for s in sessions:
        country = s.student.country or 'Unknown'
        country_dist[country] = country_dist.get(country, 0) + 1
    return render(request, 'scheduler/analytics.html', {'cancellation_rate': cancellation_rate, 'occupancy': occupancy, 'student_stats': student_stats[:10], 'hour_data_json': json.dumps(hour_data), 'weekly_data_json': json.dumps(weekly_data), 'status_dist_json': json.dumps(status_dist), 'country_data_json': json.dumps(country_dist), 'total_sessions': total, 'completed_sessions': completed.count()})
