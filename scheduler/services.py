"""
Scheduling engine: overlap detection, prayer time blocking,
working hours validation, and next-slot suggestion.
"""
from datetime import datetime, timedelta, date, time
from django.utils import timezone
from django.conf import settings
import pytz

CAIRO_TZ = pytz.timezone('Africa/Cairo')


# ─── Helpers ─────────────────────────────────────────────────────────────────

def to_cairo(dt):
    """Convert aware datetime to Cairo timezone."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, CAIRO_TZ)
    return dt.astimezone(CAIRO_TZ)


def make_aware_cairo(d, t):
    """Combine date + time into an aware Cairo datetime."""
    naive = datetime.combine(d, t)
    return CAIRO_TZ.localize(naive)


# ─── Overlap Detection ────────────────────────────────────────────────────────

def sessions_overlap(start1, end1, start2, end2):
    """Return True if two intervals overlap (strict: touching is OK)."""
    return start1 < end2 and start2 < end1


def check_overlap(start_time, end_time, exclude_session_id=None):
    """
    Check whether a proposed [start_time, end_time] overlaps with any
    existing session. Returns list of conflicting Session objects.
    """
    from .models import Session
    qs = Session.objects.filter(
        status__in=['scheduled'],
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_session_id:
        qs = qs.exclude(pk=exclude_session_id)
    return list(qs)


# ─── Working Hours ────────────────────────────────────────────────────────────

def get_working_hours(d):
    """Return WorkingHours object for a given date, or None if not working."""
    from .models import WorkingHours
    weekday = d.weekday()  # 0=Monday
    try:
        wh = WorkingHours.objects.get(weekday=weekday, is_working=True)
        return wh
    except WorkingHours.DoesNotExist:
        return None


def is_within_working_hours(start_time, end_time):
    """Return True if the session falls entirely within working hours."""
    d = to_cairo(start_time).date()
    wh = get_working_hours(d)
    if not wh:
        return False
    work_start = make_aware_cairo(d, wh.start_time)
    work_end = make_aware_cairo(d, wh.end_time)
    return start_time >= work_start and end_time <= work_end


# ─── Exception Days ───────────────────────────────────────────────────────────

def is_exception_day(d):
    """Return True if the given date is an exception (tutor unavailable)."""
    from .models import ExceptionDay
    return ExceptionDay.objects.filter(date=d).exists()


# ─── Prayer Time Blocking ─────────────────────────────────────────────────────

def get_prayer_blocked_intervals(d):
    """
    Return list of (block_start, block_end) aware datetimes for a given date.
    Blocked window: adhan+PRAYER_BUFFER_START → adhan+PRAYER_BUFFER_END
    """
    from .models import PrayerTime
    buf_start = getattr(settings, 'PRAYER_BUFFER_START', 10)
    buf_end = getattr(settings, 'PRAYER_BUFFER_END', 25)
    prayers = PrayerTime.objects.filter(date=d)
    intervals = []
    for p in prayers:
        adhan_dt = make_aware_cairo(d, p.adhan_time)
        block_start = adhan_dt + timedelta(minutes=buf_start)
        block_end = adhan_dt + timedelta(minutes=buf_end)
        intervals.append((block_start, block_end))
    return intervals


def overlaps_prayer_time(start_time, end_time):
    """Return True if the session overlaps any prayer blocked interval."""
    d = to_cairo(start_time).date()
    for block_start, block_end in get_prayer_blocked_intervals(d):
        if sessions_overlap(start_time, end_time, block_start, block_end):
            return True
    return False


# ─── Full Validation ──────────────────────────────────────────────────────────

def validate_session(start_time, end_time, exclude_session_id=None):
    """
    Validate a session slot. Returns list of error strings (empty = valid).
    """
    errors = []
    local_start = to_cairo(start_time)
    d = local_start.date()

    if is_exception_day(d):
        errors.append(f"{d} is marked as an exception day (tutor unavailable).")

    if not is_within_working_hours(start_time, end_time):
        wh = get_working_hours(d)
        if wh:
            errors.append(
                f"Session must be within working hours ({wh.start_time} - {wh.end_time})."
            )
        else:
            errors.append("Tutor is not working on this day.")

    if overlaps_prayer_time(start_time, end_time):
        errors.append("Session overlaps a prayer time blocked interval.")

    conflicts = check_overlap(start_time, end_time, exclude_session_id)
    if conflicts:
        names = ', '.join(s.student.name for s in conflicts)
        errors.append(f"Time slot conflicts with existing session(s): {names}.")

    return errors


# ─── Next Available Slot Suggestion ──────────────────────────────────────────

def suggest_next_slot(duration_minutes, from_dt=None, max_days=14):
    """
    Find the next available slot of `duration_minutes` length,
    starting from `from_dt` (defaults to now).
    Returns an aware datetime (start) or None.
    """
    from .models import Session, WorkingHours
    if from_dt is None:
        from_dt = timezone.now()
    from_dt = to_cairo(from_dt)

    step = timedelta(minutes=15)
    duration = timedelta(minutes=duration_minutes)
    deadline = from_dt + timedelta(days=max_days)

    current = from_dt.replace(second=0, microsecond=0)
    # Round up to nearest 15-min block
    minutes = current.minute
    remainder = minutes % 15
    if remainder:
        current += timedelta(minutes=(15 - remainder))

    while current < deadline:
        local = to_cairo(current)
        d = local.date()

        if is_exception_day(d):
            current = make_aware_cairo(d + timedelta(days=1), time(0, 0))
            continue

        wh = get_working_hours(d)
        if not wh:
            current = make_aware_cairo(d + timedelta(days=1), time(0, 0))
            continue

        work_start = make_aware_cairo(d, wh.start_time)
        work_end = make_aware_cairo(d, wh.end_time)

        if current < work_start:
            current = work_start
            continue
        if current + duration > work_end:
            current = make_aware_cairo(d + timedelta(days=1), time(0, 0))
            continue

        slot_end = current + duration

        # Check prayer blocking
        prayer_ok = True
        for block_start, block_end in get_prayer_blocked_intervals(d):
            if sessions_overlap(current, slot_end, block_start, block_end):
                current = block_end
                prayer_ok = False
                break
        if not prayer_ok:
            continue

        # Check overlap with existing sessions
        conflicts = check_overlap(current, slot_end)
        if conflicts:
            latest_end = max(s.end_time for s in conflicts)
            current = to_cairo(latest_end)
            continue

        return current

    return None


# ─── Quick Reschedule ────────────────────────────────────────────────────────

def quick_reschedule(session):
    """
    Move session to the nearest available valid slot.
    Returns (new_start, new_end) or (None, None) if not found.
    """
    duration = session.duration_minutes
    from_dt = timezone.now()
    new_start = suggest_next_slot(duration, from_dt=from_dt)
    if new_start:
        new_end = new_start + timedelta(minutes=duration)
        return new_start, new_end
    return None, None


# ─── Makeup Session Validation ────────────────────────────────────────────────

def validate_makeup_session(original_session, new_start, new_end):
    """
    Validate that a makeup session is within the allowed window.
    Returns list of error strings.
    """
    window_days = getattr(settings, 'MAKEUP_SESSION_WINDOW_DAYS', 7)
    orig_date = to_cairo(original_session.start_time).date()
    new_date = to_cairo(new_start).date()
    delta = (new_date - orig_date).days
    errors = []
    if delta < 0:
        errors.append("Make-up session cannot be before the original session.")
    if delta > window_days:
        errors.append(f"Make-up session must be within {window_days} days of the original.")
    errors += validate_session(new_start, new_end)
    return errors


# ─── Analytics Helpers ───────────────────────────────────────────────────────

def get_occupancy_rate(start_date, end_date):
    """Calculate occupancy rate = booked hours / available working hours."""
    from .models import Session, WorkingHours, ExceptionDay
    from decimal import Decimal

    total_available = timedelta()
    total_booked = timedelta()

    current = start_date
    while current <= end_date:
        if not is_exception_day(current):
            wh = get_working_hours(current)
            if wh:
                avail = timedelta(
                    hours=wh.end_time.hour - wh.start_time.hour,
                    minutes=wh.end_time.minute - wh.start_time.minute,
                )
                total_available += avail
        current += timedelta(days=1)

    sessions = Session.objects.filter(
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        status='completed',
    )
    for s in sessions:
        total_booked += (s.end_time - s.start_time)

    if total_available.total_seconds() == 0:
        return 0
    return round((total_booked.total_seconds() / total_available.total_seconds()) * 100, 1)
