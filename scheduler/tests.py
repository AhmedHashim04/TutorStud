from datetime import date, time, timedelta
from decimal import Decimal

import pytz
from django.test import TestCase
from django.utils import timezone

from .models import Student, Subscription, Session, WorkingHours, ExceptionDay, PrayerTime, DEFAULT_HOURLY_RATE
from .services import (
    sessions_overlap, check_overlap,
    get_working_hours, is_within_working_hours,
    is_exception_day,
    get_prayer_blocked_intervals, overlaps_prayer_time,
    validate_session, suggest_next_slot,
    validate_makeup_session, get_occupancy_rate,
    to_cairo, to_student_tz, make_aware_cairo, ensure_aware,
)
from .forms import StudentForm, COUNTRY_TIMEZONE_MAP

TEST_DATE = date(2025, 1, 4)
TEST_FRIDAY = date(2025, 1, 3)


def cairo_dt(d, h, m=0):
    return make_aware_cairo(d, time(h, m))


class FormAndPricingTests(TestCase):
    def test_country_timezone_mapping(self):
        self.assertEqual(COUNTRY_TIMEZONE_MAP['Egypt'], 'Africa/Cairo')

    def test_student_form_auto_timezone(self):
        form = StudentForm(data={
            'name': 'A',
            'phone': '',
            'country': 'Germany',
            'timezone': '',
            'notes': '',
            'is_active': True,
        })
        self.assertTrue(form.is_valid())
        student = form.save()
        self.assertEqual(student.timezone, 'Europe/Berlin')

    def test_default_hourly_rate_defined(self):
        self.assertGreater(DEFAULT_HOURLY_RATE, Decimal('0'))

    def test_subscription_snapshot_rate(self):
        student = Student.objects.create(name='S', country='Egypt', timezone='Africa/Cairo')
        sub = Subscription.objects.create(student=student, hourly_rate=Decimal('200'))
        self.assertEqual(sub.hourly_rate, Decimal('200'))


class TimezoneHelperTests(TestCase):
    def test_to_cairo_aware(self):
        utc_dt = timezone.datetime(2025, 1, 4, 12, 0, 0, tzinfo=pytz.UTC)
        cairo = to_cairo(utc_dt)
        self.assertEqual(cairo.tzinfo.zone, 'Africa/Cairo')
        self.assertEqual(cairo.hour, 14)

    def test_to_cairo_naive(self):
        from datetime import datetime
        naive = datetime(2025, 1, 4, 15, 30)
        cairo = to_cairo(naive)
        self.assertEqual(cairo.hour, 15)
        self.assertEqual(cairo.minute, 30)

    def test_ensure_aware_naive(self):
        from datetime import datetime
        naive = datetime(2025, 1, 4, 10, 0)
        aware = ensure_aware(naive)
        self.assertTrue(timezone.is_aware(aware))

    def test_to_student_tz_conversion(self):
        student = Student(timezone='America/New_York')
        cairo_time = cairo_dt(TEST_DATE, 16)
        ny_time = to_student_tz(cairo_time, student)
        self.assertIsNotNone(ny_time)


class OverlapDetectionTests(TestCase):
    def test_no_overlap_sequential(self):
        self.assertFalse(sessions_overlap(cairo_dt(TEST_DATE, 10), cairo_dt(TEST_DATE, 11), cairo_dt(TEST_DATE, 11), cairo_dt(TEST_DATE, 12)))

    def test_check_overlap_finds_conflict(self):
        student = Student.objects.create(name='Test Student', timezone='Africa/Cairo')
        existing = Session.objects.create(student=student, start_time=cairo_dt(TEST_DATE, 14), end_time=cairo_dt(TEST_DATE, 15), status='scheduled')
        conflicts = check_overlap(cairo_dt(TEST_DATE, 14, 30), cairo_dt(TEST_DATE, 15, 30))
        self.assertIn(existing, conflicts)


class WorkingHoursTests(TestCase):
    def setUp(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)

    def test_working_day_returns_hours(self):
        self.assertIsNotNone(get_working_hours(TEST_DATE))

    def test_within_working_hours_true(self):
        self.assertTrue(is_within_working_hours(cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16)))


class ExceptionDayTests(TestCase):
    def test_exception_day_detected(self):
        ExceptionDay.objects.create(date=TEST_DATE, reason='Holiday')
        self.assertTrue(is_exception_day(TEST_DATE))


class PrayerTimeTests(TestCase):
    def setUp(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        PrayerTime.objects.create(date=TEST_DATE, prayer='dhuhr', adhan_time=time(12, 15))

    def test_blocked_intervals_generated_correctly(self):
        intervals = get_prayer_blocked_intervals(TEST_DATE)
        self.assertEqual(len(intervals), 1)

    def test_session_inside_prayer_block_fails(self):
        self.assertTrue(overlaps_prayer_time(cairo_dt(TEST_DATE, 12, 30), cairo_dt(TEST_DATE, 13, 30)))


class SessionValidationTests(TestCase):
    def setUp(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        self.student = Student.objects.create(name='Valid Student', country='Egypt', timezone='Africa/Cairo')
        Subscription.objects.create(student=self.student, sessions_per_week=3, session_duration=60, hourly_rate=Decimal('200'))

    def test_valid_session_returns_no_errors(self):
        self.assertEqual(validate_session(cairo_dt(TEST_DATE, 15), cairo_dt(TEST_DATE, 16)), [])


class SlotSuggestionTests(TestCase):
    def setUp(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)

    def test_finds_slot_on_working_day(self):
        slot = suggest_next_slot(60, from_dt=cairo_dt(TEST_DATE, 10))
        self.assertIsNotNone(slot)


class MakeupSessionTests(TestCase):
    def setUp(self):
        for weekday in (0, 1, 5, 6):
            WorkingHours.objects.create(weekday=weekday, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        self.student = Student.objects.create(name='Makeup Student', country='Egypt', timezone='Africa/Cairo')
        self.original = Session.objects.create(student=self.student, start_time=cairo_dt(TEST_DATE, 15), end_time=cairo_dt(TEST_DATE, 16), status='missed')

    def test_makeup_within_window_valid(self):
        makeup_date = TEST_DATE + timedelta(days=3)
        errors = validate_makeup_session(self.original, cairo_dt(makeup_date, 15), cairo_dt(makeup_date, 16))
        self.assertEqual(errors, [])


class FinancialCalculationTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(name='Finance Student', country='Egypt', timezone='Africa/Cairo')
        self.subscription = Subscription.objects.create(student=self.student, sessions_per_week=3, session_duration=60, hourly_rate=Decimal('200'), is_active=True)

    def test_session_rate_60min(self):
        self.assertEqual(self.subscription.session_rate, Decimal('200'))

    def test_earnings_use_snapshot_rate(self):
        self.subscription.hourly_rate = Decimal('500')
        self.subscription.save()
        session = Session.objects.create(student=self.student, start_time=cairo_dt(TEST_DATE, 15), end_time=cairo_dt(TEST_DATE, 16), status='completed')
        self.assertEqual(session.earnings, Decimal('500'))

    def test_occupancy_rate_no_sessions(self):
        WorkingHours.objects.create(weekday=5, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
        self.assertEqual(get_occupancy_rate(TEST_DATE, TEST_DATE), 0)


class StudentModelTests(TestCase):
    def test_student_str(self):
        self.assertEqual(str(Student.objects.create(name='Model Student', timezone='Africa/Cairo')), 'Model Student')
