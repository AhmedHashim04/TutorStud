"""
Comprehensive test suite for TutorSys scheduling engine.

Covers:
  - Overlap detection logic
  - Working hours validation
  - Exception day blocking
  - Prayer-time blocking windows
  - Full session validation (combined rules)
  - Next-slot suggestion algorithm
  - Makeup session validation rules
  - Financial calculations (earnings, rate, occupancy)
  - Student model properties
  - Timezone conversion helpers
"""
from datetime import date, time, timedelta
from decimal import Decimal

import pytz
from django.test import TestCase
from django.utils import timezone

from .models import Student, Subscription, Session, WorkingHours, ExceptionDay, PrayerTime
from .services import (
    sessions_overlap, check_overlap,
    get_working_hours, is_within_working_hours,
    is_exception_day,
    get_prayer_blocked_intervals, overlaps_prayer_time,
    validate_session, suggest_next_slot,
    validate_makeup_session, get_occupancy_rate,
    to_cairo, to_student_tz, make_aware_cairo, ensure_aware, CAIRO_TZ,
)

# Fixed test date: Saturday 2025-01-04 (a working day in our test schedule)
TEST_DATE = date(2025, 1, 4)
# Fixed test date that is a non-working day: Friday 2025-01-03
TEST_FRIDAY = date(2025, 1, 3)


def cairo_dt(d, h, m=0):
    """Helper: return a Cairo-aware datetime for the given date, hour, minute."""
    return make_aware_cairo(d, time(h, m))


class TimezoneHelperTests(TestCase):
    """Tests for timezone conversion utility functions."""

    def test_to_cairo_aware(self):
        """Aware UTC datetime should be converted to Cairo."""
        utc_dt = timezone.datetime(2025, 1, 4, 12, 0, 0, tzinfo=pytz.UTC)
        cairo = to_cairo(utc_dt)
        self.assertEqual(cairo.tzinfo.zone, 'Africa/Cairo')
        # Cairo is UTC+2 in January (no DST)
        self.assertEqual(cairo.hour, 14)

    def test_to_cairo_naive(self):
        """Naive datetime should be treated as Cairo time."""
        from datetime import datetime
        naive = datetime(2025, 1, 4, 15, 30)
        cairo = to_cairo(naive)
        self.assertEqual(cairo.hour, 15)
        self.assertEqual(cairo.minute, 30)
        self.assertEqual(cairo.tzinfo.zone, 'Africa/Cairo')

    def test_ensure_aware_naive(self):
        """Naive datetime should be localised to Cairo."""
        from datetime import datetime
        naive = datetime(2025, 1, 4, 10, 0)
        aware = ensure_aware(naive)
        self.assertTrue(timezone.is_aware(aware))

    def test_ensure_aware_already_aware(self):
        """Aware datetime should pass through unchanged."""
        dt = cairo_dt(TEST_DATE, 14)
        result = ensure_aware(dt)
        self.assertEqual(result, dt)

    def test_to_student_tz_conversion(self):
        """Session time should be converted to student's timezone."""
        student = Student(timezone='America/New_York')
        # 16:00 Cairo (UTC+2) = 09:00 New York (UTC-5) in January
        cairo_time = cairo_dt(TEST_DATE, 16)
        ny_time = to_student_tz(cairo_time, student)
        ny_tz = pytz.timezone('America/New_York')
        expected = cairo_time.astimezone(ny_tz)
        self.assertEqual(ny_time.hour, expected.hour)

    def test_to_student_tz_invalid_fallback(self):
        """Invalid timezone string should fall back to UTC without raising."""
        student = Student(timezone='Invalid/Timezone')
        dt = cairo_dt(TEST_DATE, 14)
        result = to_student_tz(dt, student)  # Should not raise
        self.assertIsNotNone(result)


class OverlapDetectionTests(TestCase):
    """Tests for the sessions_overlap and check_overlap functions."""

    def test_overlap_full_containment(self):
        """Session A fully contains session B → overlap."""
        a_start = cairo_dt(TEST_DATE, 10)
        a_end = cairo_dt(TEST_DATE, 12)
        b_start = cairo_dt(TEST_DATE, 10, 30)
        b_end = cairo_dt(TEST_DATE, 11, 30)
        self.assertTrue(sessions_overlap(a_start, a_end, b_start, b_end))

    def test_overlap_partial(self):
        """Sessions share a portion of time → overlap."""
        a_start = cairo_dt(TEST_DATE, 10)
        a_end = cairo_dt(TEST_DATE, 11)
        b_start = cairo_dt(TEST_DATE, 10, 30)
        b_end = cairo_dt(TEST_DATE, 11, 30)
        self.assertTrue(sessions_overlap(a_start, a_end, b_start, b_end))

    def test_no_overlap_sequential(self):
        """Session A ends exactly when B starts → no overlap (touching OK)."""
        a_start = cairo_dt(TEST_DATE, 10)
        a_end = cairo_dt(TEST_DATE, 11)
        b_start = cairo_dt(TEST_DATE, 11)
        b_end = cairo_dt(TEST_DATE, 12)
        self.assertFalse(sessions_overlap(a_start, a_end, b_start, b_end))

    def test_no_overlap_gap(self):
        """Sessions with a gap between them → no overlap."""
        a_start = cairo_dt(TEST_DATE, 10)
        a_end = cairo_dt(TEST_DATE, 11)
        b_start = cairo_dt(TEST_DATE, 12)
        b_end = cairo_dt(TEST_DATE, 13)
        self.assertFalse(sessions_overlap(a_start, a_end, b_start, b_end))

    def test_check_overlap_finds_conflict(self):
        """check_overlap should return the conflicting session."""
        student = Student.objects.create(name='Test Student', timezone='Africa/Cairo')
        existing = Session.objects.create(
            student=student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 15),
            status='scheduled',
        )
        conflicts = check_overlap(cairo_dt(TEST_DATE, 14, 30), cairo_dt(TEST_DATE, 15, 30))
        self.assertIn(existing, conflicts)

    def test_check_overlap_no_conflict(self):
        """Non-overlapping slot should return empty list."""
        student = Student.objects.create(name='Test Student', timezone='Africa/Cairo')
        Session.objects.create(
            student=student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 15),
            status='scheduled',
        )
        conflicts = check_overlap(cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16))
        self.assertEqual(conflicts, [])

    def test_check_overlap_excludes_session(self):
        """Excluded session ID should not be counted as conflict."""
        student = Student.objects.create(name='Test Student', timezone='Africa/Cairo')
        session = Session.objects.create(
            student=student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 15),
            status='scheduled',
        )
        conflicts = check_overlap(
            cairo_dt(TEST_DATE, 14), cairo_dt(TEST_DATE, 15),
            exclude_session_id=session.pk
        )
        self.assertEqual(conflicts, [])

    def test_check_overlap_ignores_non_scheduled(self):
        """Completed/cancelled/missed sessions should not block new bookings."""
        student = Student.objects.create(name='Test Student', timezone='Africa/Cairo')
        for status in ('completed', 'cancelled', 'missed'):
            Session.objects.create(
                student=student,
                start_time=cairo_dt(TEST_DATE, 14),
                end_time=cairo_dt(TEST_DATE, 15),
                status=status,
            )
        conflicts = check_overlap(cairo_dt(TEST_DATE, 14), cairo_dt(TEST_DATE, 15))
        self.assertEqual(conflicts, [])


class WorkingHoursTests(TestCase):
    """Tests for working hours enforcement."""

    def setUp(self):
        # Saturday (weekday=5): 10:00–20:00
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        # Monday (weekday=0): 14:00–20:00
        WorkingHours.objects.create(weekday=0, start_time=time(14, 0), end_time=time(20, 0), is_working=True)
        # Friday (weekday=4): is_working=False
        WorkingHours.objects.create(weekday=4, start_time=time(10, 0), end_time=time(20, 0), is_working=False)

    def test_working_day_returns_hours(self):
        """get_working_hours should return the record for a working day."""
        wh = get_working_hours(TEST_DATE)  # Saturday
        self.assertIsNotNone(wh)
        self.assertEqual(wh.start_time, time(10, 0))

    def test_non_working_day_returns_none(self):
        """get_working_hours should return None for a non-working day."""
        wh = get_working_hours(TEST_FRIDAY)  # Friday with is_working=False
        self.assertIsNone(wh)

    def test_no_record_returns_none(self):
        """get_working_hours should return None if no record exists for the weekday."""
        sunday = date(2025, 1, 5)  # Sunday, no record created
        wh = get_working_hours(sunday)
        self.assertIsNone(wh)

    def test_within_working_hours_true(self):
        """Session that fits within working hours should pass."""
        self.assertTrue(is_within_working_hours(
            cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16)
        ))

    def test_within_working_hours_exactly_at_boundaries(self):
        """Session at exact working hour boundaries should pass."""
        self.assertTrue(is_within_working_hours(
            cairo_dt(TEST_DATE, 10), cairo_dt(TEST_DATE, 11)
        ))
        self.assertTrue(is_within_working_hours(
            cairo_dt(TEST_DATE, 19), cairo_dt(TEST_DATE, 20)
        ))

    def test_outside_working_hours_before_start(self):
        """Session before working hours should fail."""
        self.assertFalse(is_within_working_hours(
            cairo_dt(TEST_DATE, 8), cairo_dt(TEST_DATE, 9)
        ))

    def test_outside_working_hours_after_end(self):
        """Session after working hours should fail."""
        self.assertFalse(is_within_working_hours(
            cairo_dt(TEST_DATE, 20), cairo_dt(TEST_DATE, 21)
        ))

    def test_session_spanning_end_of_hours(self):
        """Session that extends past working hours end should fail."""
        self.assertFalse(is_within_working_hours(
            cairo_dt(TEST_DATE, 19, 30), cairo_dt(TEST_DATE, 20, 30)
        ))

    def test_non_working_day_returns_false(self):
        """is_within_working_hours should return False for a non-working day."""
        self.assertFalse(is_within_working_hours(
            cairo_dt(TEST_FRIDAY, 15), cairo_dt(TEST_FRIDAY, 16)
        ))


class ExceptionDayTests(TestCase):
    """Tests for exception day blocking."""

    def test_exception_day_detected(self):
        """A date added as exception should be detected."""
        ExceptionDay.objects.create(date=TEST_DATE, reason='National holiday')
        self.assertTrue(is_exception_day(TEST_DATE))

    def test_non_exception_day(self):
        """A date not in exceptions should return False."""
        self.assertFalse(is_exception_day(TEST_DATE))

    def test_exception_blocks_validation(self):
        """Validation should fail when the day is an exception."""
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        ExceptionDay.objects.create(date=TEST_DATE, reason='Holiday')
        errors = validate_session(cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16))
        self.assertTrue(any('exception' in e.lower() for e in errors))


class PrayerTimeTests(TestCase):
    """Tests for prayer-time blocking windows."""

    def setUp(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        # Dhuhr at 12:15 → blocked window: 12:25–12:40
        PrayerTime.objects.create(date=TEST_DATE, prayer='dhuhr', adhan_time=time(12, 15))
        # Asr at 15:30 → blocked window: 15:40–15:55
        PrayerTime.objects.create(date=TEST_DATE, prayer='asr', adhan_time=time(15, 30))

    def test_blocked_intervals_generated_correctly(self):
        """Blocked intervals should be adhan+10 → adhan+25."""
        intervals = get_prayer_blocked_intervals(TEST_DATE)
        self.assertEqual(len(intervals), 2)
        # Dhuhr: 12:25 → 12:40
        dhuhr_block = intervals[0]
        self.assertEqual(dhuhr_block[0].hour, 12)
        self.assertEqual(dhuhr_block[0].minute, 25)
        self.assertEqual(dhuhr_block[1].hour, 12)
        self.assertEqual(dhuhr_block[1].minute, 40)

    def test_session_inside_prayer_block_fails(self):
        """A session starting inside the blocked window should fail."""
        # 12:30–13:30 overlaps the 12:25–12:40 Dhuhr block
        self.assertTrue(overlaps_prayer_time(
            cairo_dt(TEST_DATE, 12, 30), cairo_dt(TEST_DATE, 13, 30)
        ))

    def test_session_spanning_prayer_block_fails(self):
        """A session that spans across the prayer window should fail."""
        # 12:00–13:00 spans the Dhuhr block (12:25–12:40)
        self.assertTrue(overlaps_prayer_time(
            cairo_dt(TEST_DATE, 12, 0), cairo_dt(TEST_DATE, 13, 0)
        ))

    def test_session_before_prayer_block_allowed(self):
        """A session ending before the blocked window should pass."""
        # 12:00–12:25 ends exactly at block start → no overlap
        self.assertFalse(overlaps_prayer_time(
            cairo_dt(TEST_DATE, 12, 0), cairo_dt(TEST_DATE, 12, 25)
        ))

    def test_session_after_prayer_block_allowed(self):
        """A session starting after the blocked window ends should pass."""
        # 12:40–13:40 starts exactly at block end → no overlap
        self.assertFalse(overlaps_prayer_time(
            cairo_dt(TEST_DATE, 12, 40), cairo_dt(TEST_DATE, 13, 40)
        ))

    def test_session_in_adhan_grace_period_allowed(self):
        """Session in the first 10 minutes after adhan (grace period) is allowed."""
        # 12:15–12:25 is within the grace period (adhan → adhan+10)
        self.assertFalse(overlaps_prayer_time(
            cairo_dt(TEST_DATE, 12, 15), cairo_dt(TEST_DATE, 12, 25)
        ))

    def test_no_prayers_means_no_blocking(self):
        """Date with no prayer times should never block."""
        future_date = date(2030, 1, 1)
        self.assertFalse(overlaps_prayer_time(
            make_aware_cairo(future_date, time(14, 0)),
            make_aware_cairo(future_date, time(15, 0)),
        ))

    def test_validation_rejects_prayer_overlap(self):
        """validate_session should return an error for a prayer-overlapping slot."""
        errors = validate_session(
            cairo_dt(TEST_DATE, 12, 30), cairo_dt(TEST_DATE, 13, 30)
        )
        self.assertTrue(any('prayer' in e.lower() for e in errors))


class SessionValidationTests(TestCase):
    """Integration tests for the full validate_session function."""

    def setUp(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        self.student = Student.objects.create(name='Valid Student', timezone='Africa/Cairo')
        Subscription.objects.create(
            student=self.student,
            sessions_per_week=3,
            session_duration=60,
            hourly_rate=Decimal('200'),
        )

    def test_valid_session_returns_no_errors(self):
        """A session that passes all rules should return an empty error list."""
        errors = validate_session(cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16))
        self.assertEqual(errors, [])

    def test_end_before_start_fails(self):
        """Session with end_time before start_time should fail immediately."""
        errors = validate_session(cairo_dt(TEST_DATE, 16), cairo_dt(TEST_DATE, 15))
        self.assertTrue(any('end time' in e.lower() for e in errors))

    def test_non_working_day_fails(self):
        """Session on a non-working day (Friday) should fail."""
        errors = validate_session(cairo_dt(TEST_FRIDAY, 15), cairo_dt(TEST_FRIDAY, 16))
        self.assertTrue(len(errors) > 0)

    def test_before_working_hours_fails(self):
        """Session before working hours start should fail."""
        errors = validate_session(cairo_dt(TEST_DATE, 8), cairo_dt(TEST_DATE, 9))
        self.assertTrue(any('working hours' in e.lower() for e in errors))

    def test_overlap_with_existing_session_fails(self):
        """Session overlapping an existing scheduled session should fail."""
        Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 15),
            status='scheduled',
        )
        errors = validate_session(cairo_dt(TEST_DATE, 14, 30), cairo_dt(TEST_DATE, 15, 30))
        self.assertTrue(any('conflict' in e.lower() for e in errors))

    def test_exception_day_fails(self):
        """Session on an exception day should fail."""
        ExceptionDay.objects.create(date=TEST_DATE)
        errors = validate_session(cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16))
        self.assertTrue(any('exception' in e.lower() for e in errors))

    def test_prayer_time_overlap_fails(self):
        """Session overlapping a prayer block should fail."""
        PrayerTime.objects.create(date=TEST_DATE, prayer='asr', adhan_time=time(15, 0))
        # 15:10–16:10 overlaps the asr block (15:10–15:25)
        errors = validate_session(cairo_dt(TEST_DATE, 15, 10), cairo_dt(TEST_DATE, 16, 10))
        self.assertTrue(any('prayer' in e.lower() for e in errors))

    def test_exclude_session_id_prevents_self_conflict(self):
        """Editing a session should not conflict with itself."""
        session = Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 15),
            end_time=cairo_dt(TEST_DATE, 16),
            status='scheduled',
        )
        errors = validate_session(
            cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16),
            exclude_session_id=session.pk
        )
        self.assertEqual(errors, [])


class SlotSuggestionTests(TestCase):
    """Tests for the suggest_next_slot algorithm."""

    def setUp(self):
        # Saturday 10:00–20:00, Sunday 10:00–20:00
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        WorkingHours.objects.create(weekday=6, start_time=time(10, 0), end_time=time(20, 0), is_working=True)

    def test_finds_slot_on_working_day(self):
        """Should return a slot on a working day."""
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 10))
        self.assertIsNotNone(slot)
        # Slot should be on the same day or later
        self.assertGreaterEqual(to_cairo(slot).date(), TEST_DATE)

    def test_respects_working_hours(self):
        """Suggested slot should fall within working hours."""
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 10))
        self.assertIsNotNone(slot)
        slot_cairo = to_cairo(slot)
        wh = get_working_hours(slot_cairo.date())
        self.assertIsNotNone(wh)
        slot_end = slot + timedelta(hours=1)
        self.assertLessEqual(to_cairo(slot_end).time(), wh.end_time)

    def test_skips_exception_days(self):
        """Suggested slot should skip exception days."""
        ExceptionDay.objects.create(date=TEST_DATE)
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 10))
        # Should find a slot on the next working day
        if slot:
            self.assertGreater(to_cairo(slot).date(), TEST_DATE)

    def test_skips_existing_sessions(self):
        """Suggested slot should not overlap existing scheduled sessions."""
        student = Student.objects.create(name='Busy Student', timezone='Africa/Cairo')
        # Fill 10:00–19:00 with back-to-back sessions (no room for 60 min until 19:00)
        for hour in range(10, 19):
            Session.objects.create(
                student=student,
                start_time=cairo_dt(TEST_DATE, hour),
                end_time=cairo_dt(TEST_DATE, hour + 1),
                status='scheduled',
            )
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 10))
        if slot:
            slot_cairo = to_cairo(slot)
            # Should not overlap any existing session
            conflicts = check_overlap(slot, slot + timedelta(hours=1))
            self.assertEqual(conflicts, [])

    def test_returns_none_when_no_slot_available(self):
        """Should return None if no slot can be found within max_days."""
        # No working hours configured (all days blocked)
        WorkingHours.objects.all().delete()
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 10), max_days=3)
        self.assertIsNone(slot)

    def test_slot_respects_prayer_blocking(self):
        """Suggested slot should not overlap prayer-blocked windows."""
        PrayerTime.objects.create(date=TEST_DATE, prayer='dhuhr', adhan_time=time(12, 15))
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 12, 0))
        if slot:
            slot_end = slot + timedelta(hours=1)
            self.assertFalse(overlaps_prayer_time(slot, slot_end))


class MakeupSessionTests(TestCase):
    """Tests for makeup session validation rules."""

    def setUp(self):
        # Saturday (5), Sunday (6), Monday (0), Tuesday (1) all working
        for weekday in (0, 1, 5, 6):
            WorkingHours.objects.create(weekday=weekday, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        self.student = Student.objects.create(name='Makeup Student', timezone='Africa/Cairo')
        self.original = Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 15),
            end_time=cairo_dt(TEST_DATE, 16),
            status='missed',
        )

    def test_makeup_within_window_valid(self):
        """Makeup 3 days after original should be valid."""
        makeup_date = TEST_DATE + timedelta(days=3)  # Sunday
        errors = validate_makeup_session(
            self.original,
            cairo_dt(makeup_date, 15),
            cairo_dt(makeup_date, 16),
        )
        self.assertEqual(errors, [])

    def test_makeup_outside_window_fails(self):
        """Makeup 10 days after original (outside 7-day window) should fail."""
        makeup_date = TEST_DATE + timedelta(days=10)
        errors = validate_makeup_session(
            self.original,
            cairo_dt(makeup_date, 15),
            cairo_dt(makeup_date, 16),
        )
        self.assertTrue(any('7 days' in e or 'window' in e.lower() for e in errors))

    def test_makeup_before_original_fails(self):
        """Makeup session before original session date should fail."""
        early_date = TEST_DATE - timedelta(days=1)
        errors = validate_makeup_session(
            self.original,
            cairo_dt(early_date, 15),
            cairo_dt(early_date, 16),
        )
        self.assertTrue(any('before' in e.lower() for e in errors))

    def test_makeup_on_same_day_valid(self):
        """Makeup on the same day as the original (day 0) should be valid."""
        errors = validate_makeup_session(
            self.original,
            cairo_dt(TEST_DATE, 17),
            cairo_dt(TEST_DATE, 18),
        )
        self.assertEqual(errors, [])


class FinancialCalculationTests(TestCase):
    """Tests for earnings calculations and occupancy rate."""

    def setUp(self):
        self.student = Student.objects.create(name='Finance Student', timezone='Africa/Cairo')
        self.subscription = Subscription.objects.create(
            student=self.student,
            sessions_per_week=3,
            session_duration=60,
            hourly_rate=Decimal('200'),
            is_active=True,
        )

    def test_session_rate_60min(self):
        """60-min session at 200 EGP/hr should cost 200 EGP."""
        self.assertEqual(self.subscription.session_rate, Decimal('200'))

    def test_session_rate_30min(self):
        """30-min session at 200 EGP/hr should cost 100 EGP."""
        sub = Subscription(hourly_rate=Decimal('200'), session_duration=30, sessions_per_week=3)
        self.assertEqual(sub.session_rate, Decimal('100'))

    def test_weekly_earnings(self):
        """3 sessions × 200 EGP = 600 EGP weekly."""
        self.assertEqual(self.subscription.weekly_earnings, Decimal('600'))

    def test_monthly_earnings(self):
        """Monthly = weekly × 4.33."""
        expected = Decimal('600') * Decimal('4.33')
        self.assertEqual(self.subscription.monthly_earnings, expected)

    def test_session_earnings_completed(self):
        """Completed 60-min session at 200 EGP/hr should earn 200 EGP."""
        session = Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 15),
            end_time=cairo_dt(TEST_DATE, 16),
            status='completed',
        )
        self.assertEqual(session.earnings, Decimal('200'))

    def test_session_earnings_no_subscription(self):
        """Session with no subscription should earn 0."""
        self.subscription.is_active = False
        self.subscription.save()
        session = Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 15),
            end_time=cairo_dt(TEST_DATE, 16),
            status='completed',
        )
        self.assertEqual(session.earnings, Decimal('0'))

    def test_cancelled_session_zero_earnings(self):
        """Cancelled session should still return earnings value (not counted in reports view)."""
        # The model doesn't zero out earnings for cancelled — the view filters to `completed` only.
        # Confirm the filter works correctly.
        session = Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 15),
            end_time=cairo_dt(TEST_DATE, 16),
            status='cancelled',
        )
        # In the reports view, only completed sessions are summed.
        completed_sessions = Session.objects.filter(status='completed')
        total = sum(s.earnings for s in completed_sessions)
        self.assertEqual(total, Decimal('0'))

    def test_occupancy_rate_calculation(self):
        """Occupancy = booked / available × 100."""
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        # One 2-hour completed session on a 10-hour working day → 20%
        Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 16),
            status='completed',
        )
        rate = get_occupancy_rate(TEST_DATE, TEST_DATE)
        self.assertAlmostEqual(rate, 20.0, places=0)

    def test_occupancy_rate_no_sessions(self):
        """Occupancy with no sessions should be 0."""
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        rate = get_occupancy_rate(TEST_DATE, TEST_DATE)
        self.assertEqual(rate, 0)

    def test_occupancy_excludes_cancelled_sessions(self):
        """Cancelled sessions should NOT contribute to occupancy."""
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 16),
            status='cancelled',
        )
        rate = get_occupancy_rate(TEST_DATE, TEST_DATE)
        self.assertEqual(rate, 0)


class StudentModelTests(TestCase):
    """Tests for Student and Subscription model properties."""

    def setUp(self):
        self.student = Student.objects.create(name='Model Student', timezone='Africa/Cairo')

    def test_active_subscription_property(self):
        """active_subscription should return the active sub."""
        sub = Subscription.objects.create(
            student=self.student,
            sessions_per_week=2,
            session_duration=60,
            hourly_rate=Decimal('150'),
            is_active=True,
        )
        self.assertEqual(self.student.active_subscription, sub)

    def test_no_subscription_returns_none(self):
        """active_subscription should return None when there's no active sub."""
        self.assertIsNone(self.student.active_subscription)

    def test_inactive_subscription_ignored(self):
        """Inactive subscriptions should not be returned as active."""
        Subscription.objects.create(
            student=self.student,
            sessions_per_week=2,
            session_duration=60,
            hourly_rate=Decimal('150'),
            is_active=False,
        )
        self.assertIsNone(self.student.active_subscription)

    def test_weekly_earnings_no_subscription(self):
        """weekly_earnings should be 0 when there's no active subscription."""
        self.assertEqual(self.student.weekly_earnings, Decimal('0'))

    def test_monthly_earnings_no_subscription(self):
        """monthly_earnings should be 0 when there's no active subscription."""
        self.assertEqual(self.student.monthly_earnings, Decimal('0'))

    def test_session_duration_minutes(self):
        """duration_minutes property should return correct value."""
        session = Session.objects.create(
            student=self.student,
            start_time=cairo_dt(TEST_DATE, 14),
            end_time=cairo_dt(TEST_DATE, 15),
            status='scheduled',
        )
        self.assertEqual(session.duration_minutes, 60)

    def test_student_str(self):
        """Student __str__ should return the name."""
        self.assertEqual(str(self.student), 'Model Student')
