from django.db.models import Sum, Count, F, Q
from django.db.models.functions import TruncDay, TruncWeek, ExtractWeekDay
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Session, Student, CAIRO_TZ

def get_analytics_data(start_date=None, end_date=None, student_id=None, country=None):
    """
    Computes all metrics for the Analytics Dashboard based on filters.
    """
    now = timezone.now()
    
    # 1. Base Queryset Filter
    sessions = Session.objects.all()
    
    if start_date:
        sessions = sessions.filter(start_time__gte=start_date)
    if end_date:
        sessions = sessions.filter(start_time__lte=end_date)
    if student_id:
        sessions = sessions.filter(student_id=student_id)
    if country:
        sessions = sessions.filter(student__country=country)

    # Exclude scheduled (future) from historical performance metrics if we only want past data
    # But user might want projected revenue.
    # Let's separate Past (Completed) and Future (Scheduled)
    past_sessions = sessions.filter(start_time__lt=now)
    future_sessions = sessions.filter(start_time__gte=now, status='scheduled')

    # --- HERO METRICS ---
    # Revenue (Earned = Attended + Absent/No-Show)
    earned_revenue = past_sessions.filter(status__in=['attended', 'absent']).aggregate(total=Sum('price'))['total'] or Decimal('0.00')
    projected_revenue = future_sessions.aggregate(total=Sum('price'))['total'] or Decimal('0.00')
    
    total_past_sessions = past_sessions.exclude(status='scheduled').count()
    attended_count = past_sessions.filter(status='attended').count()
    attendance_rate = round((attended_count / total_past_sessions * 100) if total_past_sessions > 0 else 0)
    
    # --- TREND CHART (Revenue over time) ---
    # Group by Day if range is <= 31 days, else Week
    day_diff = (end_date - start_date).days if start_date and end_date else 30
    if day_diff <= 31:
        trunc_func = TruncDay('start_time', tzinfo=CAIRO_TZ)
    else:
        trunc_func = TruncWeek('start_time', tzinfo=CAIRO_TZ)
        
    revenue_trend_raw = past_sessions.filter(status__in=['attended', 'absent']).annotate(
        period=trunc_func
    ).values('period').annotate(
        revenue=Sum('price')
    ).order_by('period')
    
    # Format trend for Chart.js
    trend_labels = []
    trend_data = []
    for item in revenue_trend_raw:
        if item['period']:
            trend_labels.append(item['period'].strftime('%b %d, %Y'))
            trend_data.append(float(item['revenue']))

    # --- SESSION HEALTH (Doughnut Chart) ---
    health_raw = past_sessions.exclude(status='scheduled').values('status').annotate(count=Count('id'))
    health_data = {
        'attended': 0,
        'absent': 0,
        'excused': 0,
        'cancelled_by_teacher': 0
    }
    for item in health_raw:
        if item['status'] in health_data:
            health_data[item['status']] = item['count']

    # --- WORKLOAD (Busiest Days) ---
    # ExtractWeekDay returns 1=Sunday, 2=Monday, ..., 7=Saturday
    workload_raw = sessions.annotate(
        weekday=ExtractWeekDay('start_time', tzinfo=CAIRO_TZ)
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')
    
    workload_map = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0} # Sun-Sat
    for item in workload_raw:
        if item['weekday']:
            workload_map[item['weekday']] = item['count']
            
    # Reorder to match standard Mon-Sun or Sat-Fri. Let's do Mon-Sun (2,3,4,5,6,7,1)
    workload_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    workload_data = [
        workload_map[2], workload_map[3], workload_map[4], 
        workload_map[5], workload_map[6], workload_map[7], workload_map[1]
    ]

    # --- TOP STUDENTS LEADERBOARD ---
    # Rank by revenue generated in the selected period
    top_students_raw = past_sessions.filter(status__in=['attended', 'absent']).values(
        'student__id', 'student__name', 'student__country'
    ).annotate(
        total_revenue=Sum('price'),
        total_sessions=Count('id')
    ).order_by('-total_revenue')[:5]
    
    leaderboard = []
    for item in top_students_raw:
        leaderboard.append({
            'id': item['student__id'],
            'name': item['student__name'],
            'country': dict(Student._meta.get_field('country').choices).get(item['student__country'], item['student__country'])[:2],
            'revenue': float(item['total_revenue']),
            'sessions': item['total_sessions']
        })

    return {
        'hero': {
            'earned_revenue': float(earned_revenue),
            'projected_revenue': float(projected_revenue),
            'attendance_rate': attendance_rate,
            'total_past_sessions': total_past_sessions
        },
        'charts': {
            'trend': {
                'labels': trend_labels,
                'data': trend_data
            },
            'health': [
                health_data['attended'],
                health_data['absent'],
                health_data['excused'],
                health_data['cancelled_by_teacher']
            ],
            'workload': {
                'labels': workload_labels,
                'data': workload_data
            }
        },
        'leaderboard': leaderboard
    }
