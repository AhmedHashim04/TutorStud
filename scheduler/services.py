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

def validate_session(start_time, duration_minutes, exclude_session_id=None):
    """
    Validate if a session slot is available.
    Returns a list of error strings (empty list means valid).
    """
    errors = []
    start_time = ensure_aware(start_time)
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    d = to_cairo(start_time).date()

    # 1. Prayer Time Overlap Check
    prayers = PrayerTime.objects.filter(date=d)
    for p in prayers:
        prayer_start = CAIRO_TZ.localize(datetime.combine(d, p.adhan_time))
        prayer_end = prayer_start + timedelta(minutes=p.duration)
        if sessions_overlap(start_time, end_time, prayer_start, prayer_end):
            errors.append(f"Overlaps with {p.get_prayer_display()} prayer time ({p.adhan_time.strftime('%H:%M')}).")

    # 2. Existing Session Overlap Check
    conflicting_sessions = Session.objects.filter(
        start_time__lt=end_time
    ).exclude(
        start_time__gte=end_time  # Not strictly necessary but safe
    )
    
    if exclude_session_id:
        conflicting_sessions = conflicting_sessions.exclude(pk=exclude_session_id)

    # We have to do a programmatic check to ensure we use the end_time property correctly
    for s in conflicting_sessions:
        if sessions_overlap(start_time, end_time, s.start_time, s.end_time):
            if s.status != 'cancelled_by_teacher' and s.status != 'excused':
                errors.append(f"Conflicts with {s.student.name}'s session at {s.start_time.strftime('%H:%M')}.")
                break # Just show one conflict

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


def purge_future_sessions_for_inactive_student(student):
    """If a student becomes inactive, remove their future scheduled sessions."""
    now = timezone.now()
    if not student.is_active:
        Session.objects.filter(
            student=student,
            start_time__gt=now,
            status='scheduled'
        ).delete()
