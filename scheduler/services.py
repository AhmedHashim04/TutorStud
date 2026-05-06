"""
Scheduling engine for TutorSys.

Responsibilities:
  - Timezone conversion utilities (UTC ↔ Cairo ↔ student local)
  - Overlap detection between sessions
  - Working hours & exception day enforcement
  - Prayer-time blocking window calculation
  - Full session validation (combines all rules above)
  - Smart next-slot suggestion
  - Quick reschedule
  - Makeup session validation
  - Occupancy rate analytics
  - Recurring schedule generation

All datetimes are stored in UTC in the database.
All scheduling logic operates in Africa/Cairo (the tutor's local time).
Student display times are converted to the student's own timezone on the fly.

Prayer-time blocking rule:
  - Adhan → adhan+PRAYER_BUFFER_START minutes  : ALLOWED (preparing)
  - Adhan+PRAYER_BUFFER_START → adhan+PRAYER_BUFFER_END : BLOCKED
  (Default: 10 min grace, then 15-min blocked window → until adhan+25)
"""
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
import pytz
import re
import requests

# Tutor is always based in Cairo
CAIRO_TZ = pytz.timezone('Africa/Cairo')

PRAYER_TIME_FIELD_MAP = {
    'fajr': 'Fajr',
    'dhuhr': 'Dhuhr',
    'asr': 'Asr',
    'maghrib': 'Maghrib',
    'isha': 'Isha',
}


# ─── Timezone Helpers ────────────────────────────────────────────────────────

def to_cairo(dt):
    """Convert any datetime (naive or aware) to a Cairo-aware datetime."""
    if timezone.is_naive(dt):
        dt = CAIRO_TZ.localize(dt)
    return dt.astimezone(CAIRO_TZ)


def make_aware_cairo(d, t):
    """Combine a date and a time into a Cairo-aware datetime."""
    return CAIRO_TZ.localize(datetime.combine(d, t))


def to_student_tz(dt, student):
    """Convert a datetime to the student's local timezone."""
    try:
        tz = pytz.timezone(student.timezone or 'UTC')
    except Exception:
        tz = pytz.UTC
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.astimezone(tz)


def ensure_aware(dt, default_tz=CAIRO_TZ):
    """Return an aware datetime; treat naive datetimes as Cairo local time."""
    if timezone.is_naive(dt):
        return default_tz.localize(dt)
    return dt


def _parse_api_time(value):
    if not value:
        return None
    match = re.search(r'(\d{1,2}):(\d{2})', str(value))
    if not match:
        return None
    hour, minute = map(int, match.groups())
    return time(hour=hour, minute=minute)


def fetch_prayer_times_for_date(target_date, city='Cairo', country='Egypt', method=5):
    """Fetch Cairo prayer times for a specific date and normalize them to time objects."""
    date_str = target_date.strftime('%d-%m-%Y')
    url = f'https://api.aladhan.com/v1/timingsByCity/{date_str}'
    response = requests.get(url, params={'city': city, 'country': country, 'method': method}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    timings = payload.get('data', {}).get('timings', {})

    prayer_times = {}
    for field_name, api_name in PRAYER_TIME_FIELD_MAP.items():
        prayer_times[field_name] = _parse_api_time(timings.get(api_name))
    return prayer_times


# ─── Overlap Detection ───────────────────────────────────────────────────────

def sessions_overlap(start1, end1, start2, end2):
    """
    Return True if two half-open intervals [start1, end1) and [start2, end2)
    overlap. Touching boundaries (end1 == start2) do NOT overlap.
    """
    return start1 < end2 and start2 < end1


def check_overlap(start_time, end_time, exclude_session_id=None):
    """
    Return a list of scheduled Session objects that overlap [start_time, end_time).
    Completed/cancelled/missed sessions are intentionally ignored — they are
    historical records and no longer occupy the slot.
    """
    from .models import Session
    start_time = ensure_aware(start_time)
    end_time = ensure_aware(end_time)

    qs = Session.objects.filter(
        status='scheduled',
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).select_related('student')

    if exclude_session_id:
        qs = qs.exclude(pk=exclude_session_id)
    return list(qs)


# ─── Working Hours ────────────────────────────────────────────────────────────

def get_working_hours(d):
    """
    Return the WorkingHours record for the given date, or None if the tutor
    is not working on that weekday (or is_working=False).
    """
    from .models import WorkingHours
    try:
        return WorkingHours.objects.get(weekday=d.weekday(), is_working=True)
    except WorkingHours.DoesNotExist:
        return None


def get_working_intervals(d):
    """
    Return a list of (start_dt, end_dt) Cairo-aware intervals for the given date.
    Supports multiple ranges per day; falls back to the legacy single range.
    """
    wh = get_working_hours(d)
    if not wh:
        return []

    ranges = list(wh.ranges.all())
    if not ranges:
        return [(make_aware_cairo(d, wh.start_time), make_aware_cairo(d, wh.end_time))]

    return [(make_aware_cairo(d, r.start_time), make_aware_cairo(d, r.end_time)) for r in ranges]


def is_within_working_hours(start_time, end_time):
    """
    Return True if [start_time, end_time) fits entirely within the tutor's
    working hours for that Cairo day.
    """
    d = to_cairo(start_time).date()
    start_time = ensure_aware(start_time)
    end_time = ensure_aware(end_time)

    for work_start, work_end in get_working_intervals(d):
        if start_time >= work_start and end_time <= work_end:
            return True
    return False


# ─── Exception Days ───────────────────────────────────────────────────────────

def is_exception_day(d):
    """Return True if the given date is marked as an exception (tutor unavailable)."""
    from .models import ExceptionDay
    return ExceptionDay.objects.filter(date=d).exists()


# ─── Prayer-Time Blocking ─────────────────────────────────────────────────────

def get_prayer_blocked_intervals(d):
    """
    Return a list of (block_start, block_end) aware datetimes for the given
    Cairo date.  Each interval represents the period during which no session
    may be held (adhan+BUFFER_START → adhan+BUFFER_END).
    """
    from .models import PrayerTime
    buf_start = getattr(settings, 'PRAYER_BUFFER_START', 10)
    buf_end = getattr(settings, 'PRAYER_BUFFER_END', 25)
    intervals = []
    for p in PrayerTime.objects.filter(date=d):
        adhan_dt = make_aware_cairo(d, p.adhan_time)
        intervals.append((
            adhan_dt + timedelta(minutes=buf_start),
            adhan_dt + timedelta(minutes=buf_end),
        ))
    return intervals


def overlaps_prayer_time(start_time, end_time):
    """Return True if [start_time, end_time) overlaps any prayer-blocked interval."""
    d = to_cairo(start_time).date()
    for block_start, block_end in get_prayer_blocked_intervals(d):
        if sessions_overlap(
            ensure_aware(start_time), ensure_aware(end_time),
            block_start, block_end
        ):
            return True
    return False


# ─── Full Session Validation ─────────────────────────────────────────────────

def validate_session(start_time, end_time, exclude_session_id=None, skip_working_hours=False):
    """
    Validate a proposed session slot against all business rules.
    Returns a list of human-readable error strings (empty list = valid).

    Rules checked (in order):
      1. start_time must be before end_time
      2. The date must not be an exception day
      3. The slot must fall within working hours (unless skip_working_hours=True)
      4. The slot must not overlap any prayer-blocked window
      5. The slot must not overlap any other scheduled session
    """
    errors = []

    start_time = to_cairo(ensure_aware(start_time))
    end_time = to_cairo(ensure_aware(end_time))

    if start_time >= end_time:
        errors.append("Session end time must be after start time.")
        return errors

    d = start_time.date()

    if is_exception_day(d):
        errors.append(f"{d.strftime('%A, %B %-d')} is marked as an exception day (tutor unavailable).")

    if not skip_working_hours and not is_within_working_hours(start_time, end_time):
        intervals = get_working_intervals(d)
        if intervals:
            windows = ', '.join(
                f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
                for start_dt, end_dt in intervals
            )
            errors.append(
                f"Session must be within working hours "
                f"({windows} Cairo time)."
            )
        else:
            errors.append(f"Tutor is not working on {d.strftime('%A')}.")

    if overlaps_prayer_time(start_time, end_time):
        errors.append(
            "Session overlaps a prayer-time blocked window "
            f"(adhan +{getattr(settings, 'PRAYER_BUFFER_START', 10)} "
            f"→ +{getattr(settings, 'PRAYER_BUFFER_END', 25)} minutes)."
        )

    conflicts = check_overlap(start_time, end_time, exclude_session_id)
    if conflicts:
        names = ', '.join(s.student.name for s in conflicts)
        errors.append(f"Time slot conflicts with existing session(s): {names}.")

    return errors


# ─── Recurring Schedule Generation ───────────────────────────────────────────

def _next_weekday(from_date, target_weekday):
    """Return the next date on or after `from_date` that falls on `target_weekday` (0=Mon)."""
    days_ahead = (target_weekday - from_date.weekday()) % 7
    return from_date + timedelta(days=days_ahead)


def generate_sessions_from_schedule(schedule, weeks=4, from_date=None):
    """
    Generate Session records from a RecurringSchedule for the next `weeks` weeks.

    - Skips slots that fail validation (exception day, prayer block, overlap, etc.)
    - Does NOT generate a session if one already exists for that schedule on that date.
    - Returns a tuple: (created_count, skipped_reasons_list)
    """
    from .models import Session

    if from_date is None:
        from_date = timezone.localdate()

    created = 0
    skipped = []

    # Find the first occurrence of the target weekday on or after from_date
    first_day = _next_weekday(from_date, schedule.day_of_week)
    duration = timedelta(minutes=schedule.duration)

    for week_offset in range(weeks):
        target_date = first_day + timedelta(weeks=week_offset)
        start_dt = make_aware_cairo(target_date, schedule.start_time)
        end_dt = start_dt + duration

        # Skip if a session already exists for this schedule on this date
        already_exists = Session.objects.filter(
            recurring_schedule=schedule,
            start_time__date=target_date,
        ).exists()
        if already_exists:
            continue

        # Validate
        errors = validate_session(start_dt, end_dt)
        if errors:
            skipped.append({'date': target_date, 'errors': errors})
            continue

        Session.objects.create(
            student=schedule.student,
            enrollment=schedule.subscription,
            start_time=start_dt,
            end_time=end_dt,
            status='scheduled',
            recurring_schedule=schedule,
            is_override=False,
            is_recurring=True,
        )
        created += 1

    return created, skipped


def preview_sessions_from_schedule(schedule, weeks=4, from_date=None):
    """
    Return a list of preview dicts (date, start_dt, end_dt, valid, errors)
    without creating any actual Session records.
    """
    if from_date is None:
        from_date = timezone.localdate()

    from .models import Session
    preview = []
    first_day = _next_weekday(from_date, schedule.day_of_week)
    duration = timedelta(minutes=schedule.duration)

    for week_offset in range(weeks):
        target_date = first_day + timedelta(weeks=week_offset)
        start_dt = make_aware_cairo(target_date, schedule.start_time)
        end_dt = start_dt + duration

        already_exists = Session.objects.filter(
            recurring_schedule=schedule,
            start_time__date=target_date,
        ).exists()

        errors = validate_session(start_dt, end_dt)
        preview.append({
            'date': target_date,
            'start_dt': start_dt,
            'end_dt': end_dt,
            'valid': len(errors) == 0 and not already_exists,
            'already_exists': already_exists,
            'errors': errors,
        })

    return preview


def delete_future_recurring_sessions(schedule):
    """
    Delete all future 'scheduled' sessions generated from this RecurringSchedule
    that have NOT been individually overridden.
    Overridden sessions are preserved.
    """
    from .models import Session
    now = timezone.now()
    Session.objects.filter(
        recurring_schedule=schedule,
        status='scheduled',
        is_override=False,
        start_time__gt=now,
    ).delete()


def regenerate_schedule(schedule, weeks=4):
    """Delete future non-override sessions and regenerate."""
    delete_future_recurring_sessions(schedule)
    return generate_sessions_from_schedule(schedule, weeks=weeks)


# ─── Next Available Slot Suggestion ──────────────────────────────────────────

def suggest_next_slot(duration_minutes, from_dt=None, max_days=14):
    """
    Find and return the earliest available Cairo-aware slot of the given
    duration, starting from `from_dt` (defaults to now).
    """
    if from_dt is None:
        from_dt = timezone.now()
    current = to_cairo(from_dt).replace(second=0, microsecond=0)

    rem = current.minute % 15
    if rem:
        current += timedelta(minutes=15 - rem)

    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=15)
    deadline = current + timedelta(days=max_days)

    while current < deadline:
        d = current.date()

        if is_exception_day(d):
            current = make_aware_cairo(d + timedelta(days=1), time(0, 0))
            continue

        intervals = get_working_intervals(d)
        if not intervals:
            current = make_aware_cairo(d + timedelta(days=1), time(0, 0))
            continue

        # Jump to the next interval start when current is outside all intervals.
        in_any_interval = False
        for interval_start, interval_end in intervals:
            if interval_start <= current < interval_end:
                in_any_interval = True
                break
            if current < interval_start:
                current = interval_start
                in_any_interval = True
                break

        if not in_any_interval:
            current = make_aware_cairo(d + timedelta(days=1), time(0, 0))
            continue

        slot_end = current + duration
        if not is_within_working_hours(current, slot_end):
            current += step
            continue

        prayer_jumped = False
        for block_start, block_end in get_prayer_blocked_intervals(d):
            if sessions_overlap(current, slot_end, block_start, block_end):
                current = block_end
                prayer_jumped = True
                break
        if prayer_jumped:
            continue

        conflicts = check_overlap(current, slot_end)
        if conflicts:
            current = to_cairo(max(s.end_time for s in conflicts))
            rem = current.minute % 15
            if rem:
                current += timedelta(minutes=15 - rem)
            continue

        return current

    return None


# ─── Quick Reschedule ─────────────────────────────────────────────────────────

def quick_reschedule(session):
    """
    Move session to the nearest available valid slot from now.
    Returns (new_start, new_end) as Cairo-aware datetimes, or (None, None).
    """
    new_start = suggest_next_slot(session.duration_minutes, from_dt=timezone.now())
    if new_start:
        return new_start, new_start + timedelta(minutes=session.duration_minutes)
    return None, None


# ─── Makeup Session Validation ───────────────────────────────────────────────

def validate_makeup_session(original_session, new_start, new_end):
    """
    Validate a makeup session.  The makeup must:
      - Be on or after the original session's date
      - Be within MAKEUP_SESSION_WINDOW_DAYS of the original session
      - Pass all normal session validation rules

    Returns a list of error strings.
    """
    window_days = getattr(settings, 'MAKEUP_SESSION_WINDOW_DAYS', 7)
    orig_date = to_cairo(original_session.start_time).date()
    new_date = to_cairo(ensure_aware(new_start)).date()
    delta = (new_date - orig_date).days

    errors = []
    if delta < 0:
        errors.append("Make-up session cannot be scheduled before the original session date.")
    elif delta > window_days:
        errors.append(
            f"Make-up session must be within {window_days} days of the original session "
            f"(original was on {orig_date.strftime('%B %-d')})."
        )

    errors += validate_session(new_start, new_end)
    return errors


# ─── Occupancy Rate ───────────────────────────────────────────────────────────

def get_occupancy_rate(start_date, end_date):
    """
    Calculate the tutor's occupancy rate over a date range:
      occupancy = total_booked_hours / total_available_hours × 100

    Only completed sessions count as booked.
    Returns a float percentage (0–100), or 0 if no available hours.
    """
    from .models import Session

    total_available = timedelta()
    total_booked = timedelta()

    current = start_date
    while current <= end_date:
        if not is_exception_day(current):
            intervals = get_working_intervals(current)
            for start_dt, end_dt in intervals:
                total_available += timedelta(
                    hours=end_dt.hour - start_dt.hour,
                    minutes=end_dt.minute - start_dt.minute,
                )
        current += timedelta(days=1)

    sessions = Session.objects.filter(
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        status='completed',
    )
    for s in sessions:
        total_booked += s.end_time - s.start_time

    if total_available.total_seconds() == 0:
        return 0
    return round(total_booked.total_seconds() / total_available.total_seconds() * 100, 1)


class PaymentService:
    @staticmethod
    def calculate_session_payment(session):
        """Return a payment decision for a single session."""
        price = Decimal('0')
        if session.enrollment:
            price = session.enrollment.session_price
        else:
            active = getattr(session.student, 'active_subscription', None)
            if active:
                price = active.session_price

        if session.status == 'cancelled':
            if session.cancelled_by == 'teacher':
                return {'is_paid': False, 'amount': Decimal('0'), 'rule': 'cancelled_by_teacher'}
            if session.cancelled_by == 'student' and session.can_be_cancelled_free():
                return {'is_paid': False, 'amount': Decimal('0'), 'rule': 'cancelled_on_time'}
            if session.cancelled_by == 'student':
                return {'is_paid': True, 'amount': price, 'rule': 'cancelled_late'}

        if session.status == 'rescheduled':
            return {'is_paid': False, 'amount': Decimal('0'), 'rule': 'rescheduled'}

        if session.status == 'completed':
            return {'is_paid': True, 'amount': price, 'rule': 'attended_or_absent'}

        return {'is_paid': False, 'amount': Decimal('0'), 'rule': 'pending'}

    @staticmethod
    def apply_payment(session):
        from .models import SessionPayment

        decision = PaymentService.calculate_session_payment(session)
        payment, _ = SessionPayment.objects.get_or_create(
            session=session,
            defaults={'base_amount': decision['amount'], 'final_amount': decision['amount'], 'rule_applied': decision['rule'], 'is_paid': decision['is_paid']},
        )
        payment.base_amount = decision['amount']
        payment.final_amount = decision['amount']
        payment.rule_applied = decision['rule']
        payment.is_paid = decision['is_paid']
        payment.save()
        return payment


class AnalyticsService:
    @staticmethod
    def get_dashboard_metrics(start_date, end_date):
        from .models import Session

        sessions = Session.objects.filter(start_time__date__gte=start_date, start_time__date__lte=end_date).select_related('student', 'enrollment')
        completed = sessions.filter(status='completed')
        cancelled = sessions.filter(status='cancelled')

        revenue = Decimal('0')
        expected = Decimal('0')
        lost = Decimal('0')
        no_shows = 0
        total = sessions.count()

        for session in sessions:
            payment = PaymentService.calculate_session_payment(session)
            expected += session.earnings
            if payment['is_paid']:
                revenue += payment['amount']
            else:
                lost += session.earnings if session.status == 'cancelled' else Decimal('0')
            if session.status == 'completed':
                no_shows += 1 if session.attendance and session.attendance.attendance_status == 'absence' else 0

        attendance_rate = 0
        if completed.count():
            attendance_rate = round((completed.filter(attendance__attendance_status='present').count() / completed.count()) * 100, 1)

        return {
            'actual_revenue': revenue,
            'expected_revenue': expected,
            'lost_revenue': lost,
            'no_show_rate': round((no_shows / total) * 100, 1) if total else 0,
            'attendance_rate': attendance_rate,
            'total_sessions': total,
            'cancelled_sessions': cancelled.count(),
        }

    @staticmethod
    def get_smart_insights(start_date, end_date):
        from .models import Session

        sessions = Session.objects.filter(start_time__date__gte=start_date, start_time__date__lte=end_date).select_related('student')
        no_show_students = []
        for student in {s.student for s in sessions}:
            student_sessions = sessions.filter(student=student)
            absences = student_sessions.filter(attendance__attendance_status='absence').count()
            if absences >= 3:
                no_show_students.append({'student': student.name, 'absences': absences})

        profitable_days = {}
        for session in sessions.filter(status='completed'):
            day = session.start_time.strftime('%A')
            profitable_days.setdefault(day, Decimal('0'))
            profitable_days[day] += session.earnings

        return {
            'frequent_no_shows': no_show_students,
            'profitable_days': sorted(profitable_days.items(), key=lambda item: item[1], reverse=True),
        }


class SessionGenerationService:
    @staticmethod
    def generate_for_enrollment(enrollment, weeks=4):
        if not enrollment or not enrollment.recurring_schedule:
            return 0, []
        return generate_sessions_from_schedule(enrollment.recurring_schedule, weeks=weeks)
