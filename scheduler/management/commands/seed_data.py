"""
Management command to seed sample data for demo/testing purposes.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta, datetime
from decimal import Decimal
import pytz

CAIRO_TZ = pytz.timezone('Africa/Cairo')


class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **options):
        from scheduler.models import (
            Student, Subscription, WorkingHours, ExceptionDay,
            PrayerTime, Session, GlobalConfig
        )

        self.stdout.write('🌱 Seeding sample data...')

        # Working hours
        working_schedule = [
            (5, time(10, 0), time(20, 0)),  # Saturday
            (6, time(10, 0), time(20, 0)),  # Sunday
            (0, time(14, 0), time(20, 0)),  # Monday
            (1, time(14, 0), time(20, 0)),  # Tuesday
            (2, time(14, 0), time(20, 0)),  # Wednesday
            (3, time(14, 0), time(20, 0)),  # Thursday
        ]
        for weekday, start, end in working_schedule:
            WorkingHours.objects.get_or_create(
                weekday=weekday,
                defaults={'start_time': start, 'end_time': end, 'is_working': True}
            )
        self.stdout.write('  ✓ Working hours created')

        # Prayer times for today and the next 3 days
        today = timezone.localdate()
        prayer_schedule = [
            ('fajr',    time(4, 30)),
            ('dhuhr',   time(12, 15)),
            ('asr',     time(15, 45)),
            ('maghrib', time(18, 30)),
            ('isha',    time(20, 0)),
        ]
        for i in range(4):
            d = today + timedelta(days=i)
            for prayer, t in prayer_schedule:
                PrayerTime.objects.get_or_create(
                    date=d, prayer=prayer,
                    defaults={'adhan_time': t}
                )
        self.stdout.write('  ✓ Prayer times created')

        # Students + enrollments
        GlobalConfig.objects.get_or_create(
            id=1,
            defaults={
                'default_session_price': Decimal('200'),
                'default_session_duration': 60,
                'cancellation_window_hours': 2,
                'allow_makeup_sessions': True,
                'allow_extra_sessions': True,
            },
        )
        students_data = [
            ('Ahmed Hassan',     200, 60),
            ('Sara Mohamed',     180, 60),
            ('Omar Ali',         150, 30),
            ('Nour Ibrahim',     200, 60),
            ('Youssef Khaled',   170, 60),
        ]
        students = []
        for name, price, dur in students_data:
            student, _ = Student.objects.get_or_create(
                name=name,
                defaults={'is_active': True}
            )
            Subscription.objects.get_or_create(
                student=student,
                is_active=True,
                defaults={
                    'session_price': Decimal(price),
                    'session_duration': dur,
                    'cancellation_window_hours': 2,
                    'allow_makeup_sessions': True,
                    'allow_extra_sessions': True,
                    'start_date': today,
                }
            )
            students.append(student)
        self.stdout.write(f'  ✓ {len(students)} students created')

        # Sessions over the past 2 weeks + upcoming
        now = timezone.now().astimezone(CAIRO_TZ)
        session_configs = [
            # (days_offset, hour, minute, student_idx, status, duration)
            (-14, 15, 0,  0, 'completed', 60),
            (-14, 16, 30, 1, 'completed', 60),
            (-13, 10, 0,  2, 'completed', 30),
            (-13, 14, 0,  3, 'completed', 60),
            (-12, 15, 0,  4, 'completed', 60),
            (-12, 17, 0,  0, 'completed', 60),
            (-11, 14, 0,  1, 'missed',    60),
            (-11, 16, 0,  2, 'completed', 30),
            (-10, 10, 30, 3, 'completed', 60),
            (-10, 14, 0,  4, 'cancelled', 60),
            (-9,  15, 0,  0, 'completed', 60),
            (-9,  16, 30, 1, 'completed', 60),
            (-8,  10, 0,  2, 'completed', 30),
            (-8,  14, 0,  3, 'cancelled', 60),
            (-7,  15, 0,  4, 'completed', 60),
            (-6,  14, 0,  0, 'completed', 60),
            (-5,  16, 0,  1, 'completed', 60),
            (-4,  10, 0,  2, 'missed',    30),
            (-3,  15, 0,  3, 'completed', 60),
            (-2,  14, 0,  4, 'completed', 60),
            (-1,  16, 0,  0, 'completed', 60),
            (0,   14, 0,  1, 'scheduled', 60),   # today
            (0,   16, 0,  2, 'scheduled', 30),   # today
            (0,   17, 0,  3, 'scheduled', 60),   # today
            (1,   15, 0,  4, 'scheduled', 60),
            (1,   17, 0,  0, 'scheduled', 60),
            (2,   14, 0,  1, 'scheduled', 60),
            (3,   15, 0,  2, 'scheduled', 30),
            (3,   16, 30, 3, 'scheduled', 60),
            (4,   14, 0,  4, 'scheduled', 60),
        ]

        created = 0
        for days_off, hour, minute, student_idx, status, duration in session_configs:
            d = today + timedelta(days=days_off)
            naive_start = datetime.combine(d, time(hour, minute))
            start_dt = CAIRO_TZ.localize(naive_start)
            end_dt = start_dt + timedelta(minutes=duration)
            student = students[student_idx]
            enrollment = student.active_subscription
            _, made = Session.objects.get_or_create(
                student=student,
                start_time=start_dt,
                defaults={'enrollment': enrollment, 'end_time': end_dt, 'status': status, 'session_type': 'regular', 'is_recurring': status == 'scheduled'}
            )
            if made:
                created += 1

        # One makeup session
        missed = Session.objects.filter(status='missed').first()
        if missed:
            makeup_start = CAIRO_TZ.localize(datetime.combine(
                today + timedelta(days=2), time(19, 0)
            ))
            Session.objects.get_or_create(
                student=missed.student,
                start_time=makeup_start,
                defaults={
                    'enrollment': missed.enrollment or missed.student.active_subscription,
                    'end_time': makeup_start + timedelta(minutes=missed.duration_minutes),
                    'status': 'scheduled',
                    'session_type': 'makeup',
                    'is_makeup': True,
                    'original_session': missed,
                    'notes': f'Makeup for missed session on {missed.start_time.date()}',
                }
            )

        self.stdout.write(f'  ✓ {created} sessions created')
        self.stdout.write(self.style.SUCCESS('✅ Sample data seeded successfully!'))
