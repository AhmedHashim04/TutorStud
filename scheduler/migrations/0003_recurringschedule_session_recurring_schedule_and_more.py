from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0002_student_country_student_timezone'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecurringSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('start_time', models.TimeField(help_text='Cairo time (Africa/Cairo)')),
                ('duration', models.IntegerField(choices=[(30, '30 minutes'), (45, '45 minutes'), (60, '60 minutes'), (90, '90 minutes')], default=60, help_text='Duration in minutes')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recurring_schedules', to='scheduler.student')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_schedules', to='scheduler.subscription')),
            ],
            options={
                'ordering': ['day_of_week', 'start_time'],
            },
        ),
        migrations.AddField(
            model_name='session',
            name='recurring_schedule',
            field=models.ForeignKey(blank=True, help_text='The recurring pattern this session was generated from.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='scheduler.recurringschedule'),
        ),
        migrations.AddField(
            model_name='session',
            name='is_override',
            field=models.BooleanField(default=False, help_text='True when this session has been individually modified from its recurring pattern.'),
        ),
    ]
