from datetime import timedelta, datetime
from django.utils import timezone
from .models import Session, PrayerTime, RecurringSchedule
import pytz

# Tutor is based in Cairo
CAIRO_TZ = pytz.timezone('Africa/Cairo')

def to_cairo(dt):
    if timezone.is_naive(dt):
        dt = CAIRO_TZ.localize(dt)
    return dt.astimezone(CAIRO_TZ)

def ensure_aware(dt):
    if timezone.is_naive(dt):
        return CAIRO_TZ.localize(dt)
    return dt

def sessions_overlap(start1, end1, start2, end2):
    return start1 < end2 and start2 < end1

def validate_session(start_time, duration_minutes, exclude_session_id=None, student_id=None):
    """
    Validate if a session slot is available.
    Returns a list of error strings (empty list means valid).
    """
    from .models import Session, PrayerTime, GlobalSettings, RecurringSchedule
    errors = []
    start_time = ensure_aware(start_time)
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    d = to_cairo(start_time).date()
    settings = GlobalSettings.load()
    buffer_mins = settings.prayer_buffer_minutes

    # 1. Prayer Time Overlap Check
    prayers = PrayerTime.objects.filter(date=d)
    for p in prayers:
        # Prayer window starts at adhan + buffer, and lasts for p.duration minutes
        prayer_start = CAIRO_TZ.localize(datetime.combine(d, p.adhan_time)) + timedelta(minutes=buffer_mins)
        prayer_end = prayer_start + timedelta(minutes=p.duration)
        if sessions_overlap(start_time, end_time, prayer_start, prayer_end):
            errors.append(f"Overlaps with {p.get_prayer_display()} prayer block (Starts {prayer_start.strftime('%H:%M')}).")

    # 2. Existing Session Overlap Check
    conflicting_sessions = Session.objects.filter(
        start_time__lt=end_time
    ).exclude(
        start_time__gte=end_time  # Not strictly necessary but safe
    )
    
    if exclude_session_id:
        conflicting_sessions = conflicting_sessions.exclude(pk=exclude_session_id)

    for s in conflicting_sessions:
        if sessions_overlap(start_time, end_time, s.start_time, s.end_time):
            if s.status not in ['cancelled_by_teacher', 'excused']:
                # If they overlap, only allow it if it's the exact same student (e.g. updating a session)
                # But wait, even if it's the same student, double booking themselves is weird, but we handle it.
                if student_id and s.student.id == student_id:
                    pass # Same student overlap, maybe they are extending it. We should probably block it too.
                
                errors.append(f"This time slot is already reserved for another session ({s.student.name}).")
                break # Just show one conflict

    # 3. Recurring Schedule Protection (Strict)
    target_weekday = start_time.weekday()
    target_start_time_cairo = to_cairo(start_time).time()
    
    recurring_rules = RecurringSchedule.objects.filter(
        student__is_active=True,
        weekday=target_weekday
    )
    
    for rule in recurring_rules:
        # Skip if it's the same student's rule
        if student_id and rule.student.id == student_id:
            continue
            
        rule_start_dt = CAIRO_TZ.localize(datetime.combine(d, rule.start_time))
        rule_end_dt = rule_start_dt + timedelta(minutes=rule.student.session_duration)
        
        if sessions_overlap(start_time, end_time, rule_start_dt, rule_end_dt):
            errors.append(f"This time slot is protected by a recurring reservation ({rule.student.name}).")
            break

    return errors


def get_next_weekday(from_date, target_weekday):
    """Return the next date on or after `from_date` that falls on `target_weekday` (0=Mon)."""
    days_ahead = (target_weekday - from_date.weekday()) % 7
    return from_date + timedelta(days=days_ahead)


def generate_sessions_for_student(student, weeks=4):
    """
    Generate future sessions for a student based on their recurring schedule.
    Will only generate if the student is active.
    """
    if not student.is_active:
        return 0, []

    created_count = 0
    errors_log = []
    today = timezone.localdate(timezone=CAIRO_TZ)

    schedules = RecurringSchedule.objects.filter(student=student)
    
    for schedule in schedules:
        first_day = get_next_weekday(today, schedule.weekday)
        
        for week_offset in range(weeks):
            target_date = first_day + timedelta(weeks=week_offset)
            start_dt = CAIRO_TZ.localize(datetime.combine(target_date, schedule.start_time))
            
            # Skip if session already exists for this student at this exact time
            already_exists = Session.objects.filter(
                student=student,
                start_time=start_dt
            ).exists()
            
            if already_exists:
                continue

            # Validate slot
            errors = validate_session(start_dt, student.session_duration)
            if errors:
                errors_log.append(f"{start_dt.strftime('%Y-%m-%d %H:%M')}: {', '.join(errors)}")
                continue

            # Create session
            Session.objects.create(
                student=student,
                start_time=start_dt,
                duration=student.session_duration,
                price=student.session_price,
                status='scheduled'
            )
            created_count += 1

    return created_count, errors_log


def generate_sessions_for_all_active_students(weeks=4):
    """Generate sessions for all active students."""
    from .models import Student
    total_created = 0
    all_errors = []
    
    for student in Student.objects.filter(is_active=True):
        count, errs = generate_sessions_for_student(student, weeks)
        total_created += count
        all_errors.extend(errs)
        
    return total_created, all_errors


def auto_regenerate_empty_schedules():
    """
    Checks active students. If a student has ZERO future scheduled sessions,
    it automatically generates the next 4 weeks for them.
    This fulfills the requirement: 'If the student is still marked as active and all current 4 sessions are completed, automatically generate the next 4 sessions.'
    """
    from .models import Student, Session
    now = timezone.now()
    
    active_students = Student.objects.filter(is_active=True)
    for student in active_students:
        future_count = Session.objects.filter(
            student=student,
            status='scheduled',
            start_time__gte=now
        ).count()
        
        if future_count == 0:
            generate_sessions_for_student(student, weeks=4)


def purge_future_sessions_for_inactive_student(student):
    """If a student becomes inactive, remove their future scheduled sessions."""
    from .models import Session
    now = timezone.now()
    if not student.is_active:
        Session.objects.filter(
            student=student,
            start_time__gt=now,
            status='scheduled'
        ).delete()


import requests
import re
from datetime import time

PRAYER_TIME_FIELD_MAP = {
    'fajr': 'Fajr',
    'dhuhr': 'Dhuhr',
    'asr': 'Asr',
    'maghrib': 'Maghrib',
    'isha': 'Isha',
}

def _parse_api_time(value):
    if not value:
        return None
    match = re.search(r'(\d{1,2}):(\d{2})', str(value))
    if not match:
        return None
    hour, minute = map(int, match.groups())
    return time(hour=hour, minute=minute)

def fetch_cairo_prayer_times(target_date, method=5):
    """Fetch Cairo prayer times for a specific date and save them."""
    from .models import PrayerTime
    date_str = target_date.strftime('%d-%m-%Y')
    url = f'https://api.aladhan.com/v1/timingsByCity/{date_str}'
    
    # Hardcoded to Cairo, Egypt as per business rules
    response = requests.get(url, params={'city': 'Cairo', 'country': 'Egypt', 'method': method}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    timings = payload.get('data', {}).get('timings', {})

    created_count = 0
    for field_name, api_name in PRAYER_TIME_FIELD_MAP.items():
        adhan_t = _parse_api_time(timings.get(api_name))
        if adhan_t:
            obj, created = PrayerTime.objects.update_or_create(
                date=target_date,
                prayer=field_name,
                defaults={'adhan_time': adhan_t, 'duration': 30} # Default block duration
            )
            if created:
                created_count += 1
                
    return created_count
