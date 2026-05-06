# System Architecture: Flexible Scheduling

## Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     TUTORSTUD DASHBOARD                         │
│  Student List → [Student Detail] → Edit Schedules              │
│                      ↓                    ↓                      │
│              [Schedules Tab]      [Exceptions Tab]              │
└─────────────────────────────────────────────────────────────────┘
                        ↓                   ↓
        ┌───────────────────────┬──────────────────────┐
        │                       │                      │
    ┌───────────┐        ┌────────────────┐    ┌──────────────┐
    │ Schedules │        │ Exceptions     │    │ Add. Exc.    │
    │ Manager   │        │ Manager        │    │ Dialog       │
    ├───────────┤        ├────────────────┤    ├──────────────┤
    │ • List    │        │ • Tabbed view  │    │ • type:skip  │
    │ • Edit    │◄────┐  │ • By schedule  │    │ • type:move  │
    │ • Delete  │     │  │ • Edit exc.    │    │ • type:add   │
    │ • Add new │     │  │ • Delete       │    └──────────────┘
    └───────────┘     │  └────────────────┘
         ↓            │         ↓
    ┌─────────┐       │    ┌──────────┐
    │ Forms   │───────┴──→ │ Handlers │
    ├─────────┤            ├──────────┤
    │Schedule │            │ Save     │
    │  Form   │            │ Delete   │
    │Except.  │            │ Regen.   │
    │  Form   │            └──────────┘
    └─────────┘                 │
       ↓                        ↓
┌─────────────────────────────────────┐
│        DATABASE MODELS              │
├─────────────────────────────────────┤
│ Student                             │
│ ├─ id, name, country, timezone      │
│ ├─ session_duration, price          │
│ └─ is_active                        │
│                                     │
│ RecurringSchedule (UPDATED)         │
│ ├─ student_id (FK)                  │
│ ├─ weekday, start_time              │
│ ├─ is_active (NEW)                  │
│ ├─ created_at (NEW)                 │
│ ├─ updated_at (NEW)                 │
│ └─ One-to-many: ScheduleException   │
│                                     │
│ ScheduleException (NEW)             │
│ ├─ schedule_id (FK)                 │
│ ├─ exception_type (skip/move/add)    │
│ ├─ week_start_date                  │
│ ├─ move_to_date, move_to_time       │
│ ├─ add_date, add_time, add_count    │
│ ├─ reason, created_at, created_by   │
│ └─ Full audit trail                 │
│                                     │
│ Session                             │
│ ├─ student_id (FK)                  │
│ ├─ start_time, duration, price      │
│ ├─ status (scheduled/attended/etc)  │
│ └─ notes, created_at                │
└─────────────────────────────────────┘
         ↓
    ┌────────────────────────────┐
    │ Session Generation Engine  │
    ├────────────────────────────┤
    │ generate_sessions_for_     │
    │  student(student, weeks=4) │
    │                            │
    │ 1. Load active schedules   │
    │ 2. For each week:          │
    │    a. Check exceptions     │
    │    b. Apply skip/move/add  │
    │    c. Validate slot        │
    │    d. Create session       │
    │                            │
    │ Result: New sessions with  │
    │ exceptions applied         │
    └────────────────────────────┘
```

## Data Flow: Example Scenario

**Scenario: Skip next week, then add makeup session**

```
┌─────────────────────────────────────┐
│ User: Skip Next Week                │
├─────────────────────────────────────┤
│ Dashboard → Edit Schedules          │
│          → Manage Exceptions        │
│          → Add Exception            │
│          → Type: SKIP               │
│          → Week: May 12-18          │
│          → Save                     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ System: Save Exception              │
├─────────────────────────────────────┤
│ INSERT INTO                         │
│   scheduler_scheduleexception       │
│ VALUES                              │
│   (schedule_id=1,                   │
│    exception_type='skip',           │
│    week_start_date='2026-05-12',    │
│    reason='Student vacation',       │
│    created_at=NOW(),               │
│    created_by='user')               │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ System: Regenerate Sessions         │
├─────────────────────────────────────┤
│ for week in [May 5, May 12,         │
│             May 19, May 26]:        │
│    if week == May 12-18:            │
│       # SKIP exception found        │
│       continue  # Don't generate    │
│    else:                            │
│       create_session(...)           │
│                                     │
│ Result:                             │
│ • May 5: Session created ✓          │
│ • May 12: SKIPPED ✗                 │
│ • May 19: Session created ✓         │
│ • May 26: Session created ✓         │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ User: Add Makeup Session            │
├─────────────────────────────────────┤
│ Dashboard → Edit Schedules          │
│          → Manage Exceptions        │
│          → Add Exception            │
│          → Type: ADD                │
│          → Week: May 12-18          │
│          → Sessions: 1              │
│          → Date: May 13             │
│          → Time: 5:00 PM            │
│          → Save                     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ System: Another Regeneration        │
├─────────────────────────────────────┤
│ for week in [May 5, May 12,         │
│             May 19, May 26]:        │
│    if week == May 12-18:            │
│       if SKIP exception:            │
│          pass  # still skip         │
│       if ADD exception:             │
│          create_extra_session(      │
│            date='2026-05-13',       │
│            time='17:00'             │
│          )                          │
│                                     │
│ Result:                             │
│ • May 5: Session ✓                  │
│ • May 12: SKIPPED ✗                 │
│ • May 13: MAKEUP SESSION ✓          │
│ • May 19: Session ✓                 │
│ • May 26: Session ✓                 │
└─────────────────────────────────────┘
```

## URL Routing Map

```
BASE: /scheduler/

Student-Related
├── /students/                                    → student_list
├── /students/<id>/                              → student_detail
└── /students/<id>/update-notes/                → update_student_notes

Schedule Management (NEW)
├── /students/<id>/schedules/                    → student_schedules
├── /schedules/<id>/edit/                        → edit_schedule
└── /schedules/<id>/delete/                      → delete_schedule

Exception Management (NEW)
├── /students/<id>/exceptions/                   → manage_exceptions
├── /exceptions/<schedule_id>/create/            → create_exception
├── /exceptions/<id>/edit/                       → edit_exception
└── /exceptions/<id>/delete/                     → delete_exception

Session Operations
├── /add-student/                                → add_student
├── /add-session/                                → add_session
├── /session/<id>/status/                        → update_session_status
├── /session/<id>/delete/                        → delete_session
└── /generate-sessions/                          → generate_sessions_view
```

## Form Hierarchy

```
RecurringScheduleForm
├── weekday (RadioSelect) - Monday through Sunday
├── start_time (TimeField)
└── is_active (CheckboxInput) - Toggle enable/disable

ScheduleExceptionForm
├── exception_type (RadioSelect)
│   ├── skip    → No additional fields required
│   ├── move    → move_to_date, move_to_time
│   └── add     → add_date, add_time, add_count
├── week_start_date (DateField) - Common to all
└── reason (CharField) - Optional documentation
```

## State Machine: Schedule Lifecycle

```
                    Schedule Created
                          ↓
                    is_active = True
                          ↓
        ┌─────────────────┴──────────────────┐
        ↓                                    ↓
    [ACTIVE]                            [Session Generation]
    ├─ Generate sessions               ├─ Every 4 weeks
    ├─ Can have exceptions             ├─ Check exceptions
    ├─ Can be toggled                  ├─ Apply skip/move/add
    └─ Tomorrow: sessions go down      └─ Create future sessions
        ↓
    ┌───────────────────────────────┐
    │ Exception Applied:            │
    │ • SKIP: pause generation      │
    │ • MOVE: reschedule to new dt  │
    │ • ADD: extra sessions         │
    └───────────────────────────────┘
        ↓
    [MODIFIED SCHEDULE]
    ├─ Base rule unchanged
    ├─ Exception temporary
    ├─ Sessions regenerated
    └─ Workflow complete

    Lifecycle:
    [ACTIVE] → [EXCEPTION] → [ACTIVE] → [PAUSED] → [ACTIVE] → [DELETED]
```

## Session Creation Timeline

```
Today (May 1, 2026)

Base Schedule: Monday at 3 PM

Week 1 (May 5-11)      [Monday May 5]
   ✓ Session created   3:00 PM

Week 2 (May 12-18)     [Monday May 12]
   ✗ SKIPPED           (vacation exception)

Week 3 (May 19-25)     [Monday May 19]
   ✓ Session created   3:00 PM
   ✓ Wednesday May 21   5:00 PM (ADD makeup)

Week 4 (May 26-Jun 1)  [Monday May 26]
   ✓ Session created   3:00 PM
   ~ MOVED to Friday   June 2 @ 2:00 PM (MOVE exception)

Timeline:
T+1   May 5: Regular session
T+2   May 12: NO SESSION (skipped)
T+3   May 19: Regular session
T+4   May 21: EXTRA makeup session (added)
T+5   May 26: Regular session
T+6   June 2: MOVED session (from original Monday)
```

## Admin Interface Map

```
Django Admin (/admin/)
├── Students
│   ├── List view: name, country, price, active, created
│   ├── Detail: Basic info, Sessions, Schedules
│   └── Stats: Attendance, revenue, no-show rate
│
├── Recurring Schedules (NEW)
│   ├── List: student, weekday, time, active, updated
│   ├── Filter: by weekday, active status, update date
│   └── Search: by student name
│
├── Schedule Exceptions (NEW)
│   ├── List: schedule, type, week_start_date, reason, created
│   ├── Filter: by type, week, created date
│   ├── Search: by student, reason
│   └── Detail: Full exception info + generated description
│
├── Sessions
│   ├── List: student, time, duration, status, price
│   ├── Filter: by status, date, created
│   └── Search: by student
│
├── Prayer Times
│   ├── List: date, prayer, time, duration
│   └── Filter: by prayer, date
│
└── Global Settings (Singleton)
    └── Read-only defaults
```

## Cache & Performance

```
No external caching currently.
Optimization opportunities:

1. Query Optimization
   ├── select_related() for FK lookups
   ├── prefetch_related() for Many-to-Many
   └── Use only() to limit fields

2. Generated Sessions
   ├── 4-week look-ahead (configurable)
   ├── Lazy generation on demand
   └── Can add caching layer if needed

3. Exception Lookups
   ├── Query by schedule + week_start_date
   ├── Index on (schedule, week_start_date)
   └── Typically <20 exceptions per student
```

## Security Model

```
Authentication
├── Django default (session-based)
├── Admin protected by @admin
└── View protection by request context

Authorization
├── Student owns their schedules
├── Schedules tied to Student
├── Exceptions tied to Schedule
└── Cascading permissions

Data Protection
├── No raw SQL (Django ORM)
├── No XSS (template escaping)
├── CSRF tokens on all forms
├── Timezone normalization
└── Audit trail for compliance
```

---

## Summary

This architecture provides:

✅ **Modular Design**: Each component (model, form, view) self-contained  
✅ **Clean Data Flow**: Clear paths from UI → logic → database  
✅ **Scalability**: Easily extend with bulk operations, notifications  
✅ **Maintainability**: Well-organized code with clear patterns  
✅ **Safety**: No data loss, reversible operations  
✅ **Auditability**: Full exception history tracked  

**Ready for production deployment** 🚀
