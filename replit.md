# TutorSys — Smart Tutor Management System

A production-ready Django web application for a private tutor to manage students, subscriptions, and sessions with an advanced smart scheduling engine.

## Tech Stack

- **Backend**: Django 5.2 + SQLite
- **Frontend**: Django Templates + Bootstrap 5 + Chart.js + FullCalendar 6
- **Timezone**: Africa/Cairo (pytz)
- **Packages**: django, pytz, requests, Pillow, django-crispy-forms, crispy-bootstrap5, whitenoise

## Project Structure

```
tutor_system/       # Django project settings, URLs, WSGI
scheduler/          # Main app
  models.py         # Data models: Student, Subscription, Session, WorkingHours, ExceptionDay, PrayerTime
  views.py          # All views: dashboard, students, calendar, sessions, reports, analytics, settings
  services.py       # Scheduling engine: overlap detection, prayer blocking, slot suggestion
  forms.py          # All form classes
  urls.py           # URL routing
  admin.py          # Django admin registrations
  management/
    commands/
      seed_data.py  # Sample data seeder
templates/          # HTML templates
  base.html         # Base layout with sidebar + topbar
  scheduler/        # All page templates
static/css/main.css # Custom styling
```

## Features

1. **Dashboard** — Today's sessions, earnings, upcoming sessions, quick actions, conflict alerts
2. **Student Management** — Cards with subscription info, weekly/monthly earnings calculated automatically
3. **Smart Calendar** — FullCalendar week/day/month view with color-coded sessions; click to view details
4. **Session Management** — List, filter, create, edit, delete sessions with status tracking
5. **Smart Scheduling Engine** (`scheduler/services.py`):
   - Strict overlap prevention
   - Working hours validation
   - Exception day blocking
   - Prayer time blocking (adhan+10min → adhan+25min is blocked, Cairo Egypt)
   - Auto-suggest next available slot
   - Quick reschedule (move to nearest valid slot)
6. **Attendance** — Statuses: scheduled / completed / cancelled / missed
7. **Make-up Sessions** — Link to original missed session, validated within 7-day window
8. **Financial Reports** — Income by date range/student, daily earnings chart, occupancy rate
9. **Analytics** — Weekly trend, best working hours, student commitment rates, status distribution
10. **Settings** — Working hours per weekday, exception days, prayer times management

## Running the App

```bash
python3 manage.py runserver 0.0.0.0:5000
```

## Seeding Sample Data

```bash
python3 manage.py seed_data
```

## Admin Panel

URL: `/admin/`  
Username: `admin`  
Password: `admin123`

## Key Design Decisions

- All datetime operations use Africa/Cairo timezone (pytz)
- Prayer blocking: 10–25 minutes after each adhan
- Make-up sessions must be within `MAKEUP_SESSION_WINDOW_DAYS = 7` days
- In-memory SQLite for simplicity; easily swappable with PostgreSQL
- No user authentication on the tutor-facing UI (single-tutor app)
