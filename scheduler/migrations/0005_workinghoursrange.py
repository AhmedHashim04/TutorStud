from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0004_alter_subscription_hourly_rate'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkingHoursRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('working_hours', models.ForeignKey(on_delete=models.CASCADE, related_name='ranges', to='scheduler.workinghours')),
            ],
            options={
                'ordering': ['start_time'],
            },
        ),
    ]
