from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def backfill_enrollment_fields(apps, schema_editor):
    StudentEnrollment = apps.get_model('scheduler', 'StudentEnrollment')
    Student = apps.get_model('scheduler', 'Student')
    Session = apps.get_model('scheduler', 'Session')
    GlobalConfig = apps.get_model('scheduler', 'GlobalConfig')

    config, _ = GlobalConfig.objects.get_or_create(
        id=1,
        defaults={
            'default_session_price': Decimal('200.00'),
            'default_session_duration': 60,
            'cancellation_window_hours': 2,
            'allow_makeup_sessions': True,
            'allow_extra_sessions': True,
        },
    )

    for enrollment in StudentEnrollment.objects.all():
        if enrollment.session_price in (None, Decimal('0')):
            enrollment.session_price = (getattr(enrollment, 'hourly_rate', Decimal('200.00')) * Decimal(enrollment.session_duration)) / Decimal('60')
        if not enrollment.config_snapshot:
            enrollment.config_snapshot = {
                'default_session_price': str(config.default_session_price),
                'default_session_duration': config.default_session_duration,
                'cancellation_window_hours': config.cancellation_window_hours,
                'allow_makeup_sessions': config.allow_makeup_sessions,
                'allow_extra_sessions': config.allow_extra_sessions,
            }
        enrollment.cancellation_window_hours = enrollment.cancellation_window_hours or config.cancellation_window_hours
        enrollment.allow_makeup_sessions = enrollment.allow_makeup_sessions if enrollment.allow_makeup_sessions is not None else config.allow_makeup_sessions
        enrollment.allow_extra_sessions = enrollment.allow_extra_sessions if enrollment.allow_extra_sessions is not None else config.allow_extra_sessions
        enrollment.save()

    for session in Session.objects.select_related('student').all():
        if session.enrollment_id:
            continue
        enrollment = StudentEnrollment.objects.filter(student=session.student, is_active=True).order_by('-start_date', '-created_at').first()
        if enrollment:
            session.enrollment = enrollment
            if not session.recurring_schedule_id and enrollment.recurring_schedule_id:
                session.recurring_schedule_id = enrollment.recurring_schedule_id
            session.save(update_fields=['enrollment', 'recurring_schedule'])


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0002_remove_student_phone'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Subscription',
            new_name='StudentEnrollment',
        ),
        migrations.CreateModel(
            name='GlobalConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_session_price', models.DecimalField(decimal_places=2, default=Decimal('200'), max_digits=10)),
                ('default_session_duration', models.IntegerField(default=60)),
                ('cancellation_window_hours', models.IntegerField(default=2)),
                ('allow_makeup_sessions', models.BooleanField(default=True)),
                ('allow_extra_sessions', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Global Configuration',
                'verbose_name_plural': 'Global Configuration',
            },
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='session_price',
            field=models.DecimalField(decimal_places=2, default=Decimal('200.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='cancellation_window_hours',
            field=models.IntegerField(default=2),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='allow_makeup_sessions',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='allow_extra_sessions',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='config_snapshot',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='session',
            name='enrollment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='scheduler.studentenrollment'),
        ),
        migrations.RunPython(backfill_enrollment_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='studentenrollment',
            name='sessions_per_week',
        ),
        migrations.RemoveField(
            model_name='studentenrollment',
            name='hourly_rate',
        ),
        migrations.AlterField(
            model_name='recurringschedule',
            name='subscription',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_schedules', to='scheduler.studentenrollment'),
        ),
        migrations.AddField(
            model_name='session',
            name='session_type',
            field=models.CharField(choices=[('regular', 'Regular'), ('extra', 'Extra'), ('makeup', 'Makeup')], default='regular', max_length=20),
        ),
        migrations.AddField(
            model_name='session',
            name='cancelled_by',
            field=models.CharField(blank=True, choices=[('student', 'Student'), ('teacher', 'Teacher')], max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='session',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='session',
            name='cancellation_reason',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='SessionAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance_status', models.CharField(blank=True, choices=[('present', 'Present'), ('absence', 'Absence'), ('late', 'Late')], max_length=10, null=True)),
                ('marked_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='attendance', to='scheduler.session')),
            ],
        ),
        migrations.CreateModel(
            name='SessionPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('override_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('final_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('rule_applied', models.CharField(max_length=100)),
                ('is_paid', models.BooleanField(default=False)),
                ('calculated_at', models.DateTimeField(auto_now_add=True)),
                ('reason', models.TextField(blank=True)),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment', to='scheduler.session')),
            ],
        ),
    ]