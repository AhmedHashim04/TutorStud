# TutorSys — Smart Tutor Management System

A production-ready web application built for private tutors managing students, subscriptions, and sessions — with smart scheduling, prayer-aware time blocking, international timezone support, and full financial reporting.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [How It Works — Step-by-Step](#3-how-it-works--step-by-step)
4. [UI Walkthrough](#4-ui-walkthrough)
5. [Business Rules](#5-business-rules)
6. [Installation](#6-installation)
7. [Configuration](#7-configuration)
8. [Running Tests](#8-running-tests)
9. [Sample Data](#9-sample-data)
10. [Tech Stack](#10-tech-stack)

---

## 1. Project Overview

**Who it's for:** Private tutors who teach multiple students — especially those with international students in different countries and timezones.

**What it does:**

- Keeps a complete record of every student, their subscription plan, and their session history
- Schedules sessions intelligently: no overlaps, no bookings outside working hours, no clashes with prayer times
- Shows every session in **two timezones** simultaneously — the tutor's Cairo time and the student's local time
- Generates financial reports (total income, per-student breakdown, daily earnings chart)
- Provides analytics on completion rates, occupancy, and peak productivity hours

---

## 2. Key Features

### Smart Scheduling
The system automatically validates every session booking against multiple rules before it is saved. It also has a **"Find Next Available Slot"** button that scans forward in time and returns the earliest free slot — respecting all constraints automatically.

### International Timezone Support
Each student has a **country** and **timezone** field. When viewing a session, the interface shows both:
- **Tutor time** (Cairo / Africa/Cairo)
- **Student local time** (whatever timezone the student is in — Germany, USA, UK, UAE, etc.)

This eliminates confusion when coordinating across borders.

### Prayer-Aware Scheduling
The tutor can enter daily prayer (adhan) times. The system automatically blocks a window around each prayer:
- **Grace period** (adhan → adhan + 10 min): allowed — tutor can finish a sentence
- **Blocked window** (adhan + 10 min → adhan + 25 min): no sessions allowed

Sessions that would fall inside the blocked window are rejected with a clear message.

### Working Hours & Exception Days
The tutor sets their weekly working schedule (e.g., Saturday–Thursday, 14:00–20:00 Cairo time). Any booking outside these hours is rejected. Individual days can be blocked entirely via **Exception Days** (holidays, sick days, etc.).

### Make-up Sessions
When a student misses a session, the tutor can schedule a **make-up session** directly from the session detail page. The system enforces that the make-up must be within 7 days of the original missed session.

### Financial Reports & Analytics
- **Financial Reports**: Filter by date range and student. Shows total income, completed/cancelled/missed counts, per-student income breakdown, and a daily earnings chart.
- **Analytics**: Shows cancellation rate, occupancy rate, most committed students (completion %), peak teaching hours heatmap, and 8-week session trend.

---

## 3. How It Works — Step-by-Step

### Adding a Student
1. Go to **Students → Add Student**
2. Fill in the student's name, country, and timezone (e.g., *Germany / Berlin*)
3. Set their subscription: sessions per week, session duration (30 or 60 min), hourly rate
4. The system immediately previews estimated weekly and monthly earnings
5. Click **Create Student**

### Scheduling a Session
1. Go to **Sessions → New Session** (or click **Smart Schedule** on the dashboard)
2. If you click **Smart Schedule**, the system auto-fills the next available slot
3. Otherwise, pick a student, date, and start time (all in Cairo time)
4. The system validates:
   - Is it within working hours?
   - Does it conflict with an existing session?
   - Does it fall on an exception day?
   - Does it overlap a prayer-blocked window?
5. If everything passes, the session is saved

### Viewing Dual Timezone Display
On any **Session Detail** page, you will see:
- **Cairo Time**: the tutor's local time
- **Student Local Time**: automatically converted to the student's timezone

Example: A session at 16:00 Cairo time for a German student shows as 15:00 Berlin time (in winter) or 16:00 (in summer/DST).

### Handling a Missed Session
1. Open the session → set status to **Missed**
2. A **"Schedule Make-up Session"** button appears
3. Pick a new date and time (must be within 7 days of the original)
4. The make-up session is linked back to the original for full traceability

### Quick Reschedule
From any session detail page, click **Quick Reschedule** to automatically move the session to the next available slot — the system finds the slot and saves it in one click.

---

## 4. UI Walkthrough

### Dashboard
The home screen shows:
- **4 stat cards**: Sessions Today, Today's Earnings, This Week's Earnings, Active Students
- **Conflict alert** if any sessions today overlap
- **Today's Sessions** timeline with status colour-coding
- **Upcoming Sessions** (next 5 scheduled)
- **Quick Actions** panel for common tasks

### Calendar
A full interactive calendar (FullCalendar) with month/week/day/agenda views. Clicking any event opens a popup showing:
- Session status and type
- Cairo time and student local time (if different)
- Student country/flag
- Link to full session details

A **"Find Slot"** modal lets the tutor pick a duration and see the next available time.

### Students
A card grid of all students showing subscription details and estimated earnings. Each card links to the student's full profile with session history.

### Session Detail
Shows all information about one session:
- Dual timezone display (Cairo + student local)
- Status update form
- Quick actions (reschedule, makeup, view student)
- Links to related makeup sessions

### Financial Reports
Filter by date range and/or student. Shows:
- Total income, completed/cancelled/missed counts, occupancy rate
- Daily earnings bar chart
- Per-student income breakdown with progress bars

### Analytics
30-day rolling view showing:
- Cancellation rate and occupancy rate
- Weekly session trend (line chart, last 8 weeks)
- Most productive teaching hours (bar chart by hour)
- Student commitment ranking (completion rate)
- Session status distribution (doughnut chart)

### Settings Pages
- **Working Hours**: Toggle each day on/off, set start and end times
- **Exception Days**: Add/remove individual blocked dates with a reason
- **Prayer Times**: Enter adhan times for each prayer by date; system auto-computes the blocked window

---

## 5. Business Rules

### No Overlapping Sessions
Two sessions may never occupy the same time slot. Touching (one ends exactly when another begins) is allowed. Only **scheduled** sessions block future bookings — completed/cancelled/missed sessions are historical and do not block.

### Prayer Time Blocking
- **Grace period**: Adhan → Adhan + 10 minutes (**PRAYER_BUFFER_START**) — allowed
- **Blocked window**: Adhan + 10 min → Adhan + 25 min (**PRAYER_BUFFER_END**) — no sessions

Sessions that start before the block and end inside it are also rejected.

### Working Hours
Sessions must fall entirely within the configured working hours for that weekday. A session cannot start within hours but end after the closing time.

### Exception Days
Exception days completely block all bookings for that date, regardless of working hours.

### Timezone Handling
- All datetimes are **stored in UTC** in the database (Django `USE_TZ = True`)
- The tutor's timezone is **Africa/Cairo** (set in `settings.TIME_ZONE`)
- Django's template system automatically converts UTC → Cairo for all time displays
- Student local times are computed on-the-fly using the student's timezone field
- The scheduling engine always works in Cairo time for validation

### Cancellation & Financial Rules
- **Only completed sessions** generate income — cancelled and missed sessions are excluded from all earnings calculations
- Occupancy rate only counts completed sessions as "booked" hours

### Make-up Session Rules
- Must be on or after the original session's date
- Must be within **MAKEUP_SESSION_WINDOW_DAYS** (default: 7) of the original
- Must pass all normal session validation rules
- The original session is automatically marked as **missed** when a makeup is created

---

## 6. Installation

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# 1. Clone the repository
git clone <repository-url>
cd tutor-system

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate    # Linux/macOS
# venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install django pytz whitenoise crispy-forms crispy-bootstrap5 Pillow

# 4. Apply database migrations
python manage.py migrate

# 5. Create an admin user
python manage.py createsuperuser

# 6. (Optional) Load sample data
python manage.py seed_data

# 7. Start the development server
python manage.py runserver 0.0.0.0:8000
```

Open **http://localhost:8000** in your browser.
Admin panel: **http://localhost:8000/admin/**

---

## 7. Configuration

All tunable settings are in `tutor_system/settings.py`:

```python
# Tutor's local timezone (all scheduling logic uses this)
TIME_ZONE = 'Africa/Cairo'

# Prayer time blocking window (in minutes after adhan)
PRAYER_BUFFER_START = 10   # Grace period: adhan → adhan+10 is ALLOWED
PRAYER_BUFFER_END   = 25   # Blocked: adhan+10 → adhan+25

# Maximum days allowed between original and makeup session
MAKEUP_SESSION_WINDOW_DAYS = 7
```

### Setting Up Prayer Times
After starting the server:
1. Go to **Settings → Prayer Times** in the sidebar
2. Add each prayer (Fajr, Dhuhr, Asr, Maghrib, Isha) with its adhan time for each day
3. The blocking window is calculated automatically

### Setting Up Working Hours
1. Go to **Settings → Working Hours**
2. Toggle each day on/off and set start/end times
3. Changes take effect immediately for all new session bookings

---

## 8. Running Tests

```bash
# Run the full test suite
python manage.py test scheduler

# Run with detailed output
python manage.py test scheduler --verbosity=2

# Run a specific test class
python manage.py test scheduler.tests.OverlapDetectionTests
python manage.py test scheduler.tests.PrayerTimeTests
python manage.py test scheduler.tests.FinancialCalculationTests
```

### Test Coverage

The test suite covers:
| Category | Tests |
|---|---|
| Timezone conversion helpers | 6 tests |
| Overlap detection | 8 tests |
| Working hours validation | 8 tests |
| Exception day blocking | 3 tests |
| Prayer-time blocking | 8 tests |
| Full session validation (integration) | 7 tests |
| Next-slot suggestion algorithm | 6 tests |
| Makeup session rules | 4 tests |
| Financial calculations & occupancy | 8 tests |
| Student model properties | 7 tests |

---

## 9. Sample Data

Load realistic sample data with one command:

```bash
python manage.py seed_data
```

This creates:
- **Working hours**: Saturday–Thursday (Saturday/Sunday 10:00–20:00, Monday–Thursday 14:00–20:00)
- **Prayer times**: For today and the next 3 days (Fajr, Dhuhr, Asr, Maghrib, Isha)
- **5 students** with active subscriptions:
  - Ahmed Hassan — 3 sessions/week, 60 min, 200 EGP/hr
  - Sara Mohamed — 2 sessions/week, 60 min, 180 EGP/hr
  - Omar Ali — 4 sessions/week, 30 min, 150 EGP/hr
  - Nour Ibrahim — 3 sessions/week, 60 min, 200 EGP/hr
  - Youssef Khaled — 2 sessions/week, 60 min, 170 EGP/hr
- **30 sessions** over the past 2 weeks and coming week with mixed statuses (completed, missed, cancelled, scheduled)
- **1 makeup session** linked to a missed session

---

## 10. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 (Python 3.11) |
| Database | SQLite (development) |
| Timezone handling | pytz |
| Frontend | Django Templates + Bootstrap 5.3 |
| Charts | Chart.js 4 (CDN) |
| Calendar | FullCalendar 6 (CDN) |
| Icons | Font Awesome 6 (CDN) |
| Static files | WhiteNoise |
| Forms | django-crispy-forms + crispy-bootstrap5 |

---

## Admin Access

- URL: `/admin/`
- Default credentials (after `createsuperuser` or using the seed setup): **admin / admin123**

---

*TutorSys — built for reliability, clarity, and real-world tutor workflows.*
