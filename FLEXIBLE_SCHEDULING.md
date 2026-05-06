# Flexible Schedule Editing & Exceptions

## Overview

This implementation extends the TutorStud scheduling system with **editable schedule rules** and **schedule exceptions**, enabling flexible management of student sessions while preserving data integrity and ensuring only future sessions are affected.

## Features

### 1. **Editable Schedule Rules** ✅

Each student's recurring schedule is now fully editable after creation:

- **Change Day**: Move a session from Monday to Wednesday (or any other weekday)
- **Change Time**: Adjust start time without affecting the schedule rule
- **Change Frequency**: Modify frequency settings (currently supports weekly)
- **Enable/Disable**: Temporarily pause a schedule without deleting it (toggled via `is_active` flag)
- **Non-Destructive**: Changes only affect future sessions; past sessions remain unchanged

**How It Works:**
1. User navigates to Student → "Edit Schedules"
2. Clicks "Edit" on any schedule rule
3. Updates day, time, or active status
4. Saves changes
5. System automatically regenerates future sessions (next 4 weeks)

### 2. **Schedule Exceptions** ✅

Exceptions allow temporary overrides to the regular schedule without modifying the base rule:

#### Exception Type: **SKIP WEEK**
- Don't generate a session for a specific week
- Use case: Student is on vacation, needs a break
- The base schedule remains intact; normal sessions resume next week

#### Exception Type: **MOVE SESSION**
- Reschedule a session to a different day/time in the same or adjacent week
- Use case: Tutor unavailable Monday; move session to Wednesday
- Original base schedule is preserved

#### Exception Type: **ADD SESSIONS**
- Schedule extra makeup or bonus sessions in a specific week
- Number of sessions configurable (1-10)
- Multiple sessions spaced 1 hour apart
- Use case: Student missed 2 weeks, add 2 makeup sessions

**How It Works:**
1. User navigates to Student → "Manage Exceptions"
2. Selects a recurring schedule
3. Clicks "Add Exception"
4. Chooses exception type (SKIP/MOVE/ADD)
5. Fills in week and details (date/time as needed)
6. Saves exception
7. System regenerates sessions with exception applied

## Data Models

### RecurringSchedule (Updated)
```python
class RecurringSchedule(models.Model):
    student = ForeignKey(Student)
    weekday = IntegerField(choices=WEEKDAYS)  # 0=Mon, 5=Sat, etc.
    start_time = TimeField()
    is_active = BooleanField(default=True)    # NEW: Toggle enable/disable
    created_at = DateTimeField(auto_now_add=True)  # NEW: Track creation
    updated_at = DateTimeField(auto_now=True)      # NEW: Track updates
```

### ScheduleException (New)
```python
class ScheduleException(models.Model):
    schedule = ForeignKey(RecurringSchedule)
    exception_type = CharField(choices=['skip', 'move', 'add'])
    
    # Common to all types
    week_start_date = DateField()  # Monday of affected week
    reason = CharField()           # Why this exception exists
    
    # For MOVE type
    move_to_date = DateField()
    move_to_time = TimeField()
    
    # For ADD type
    add_date = DateField()
    add_time = TimeField()
    add_count = IntegerField()     # 1-10 sessions
```

## Session Generation Logic (Updated)

The `generate_sessions_for_student()` function now:

1. **Loads Base Schedule**: Gets all active recurring schedules
2. **Checks for Exceptions**: For each scheduled week, looks up exceptions
3. **Applies Logic**:
   - **SKIP**: Don't create session for that week
   - **MOVE**: Create session at moved date/time instead
   - **ADD**: Generate regular session + extra sessions
4. **Validates**: Checks for prayer times, conflicts, and other constraints
5. **Creates Sessions**: Only if past the current date

```python
def generate_sessions_for_student(student, weeks=4):
    """
    1. Filter active schedules
    2. For each week:
       - Check exceptions
       - Apply exception logic (skip/move/add)
       - Validate slot availability
       - Create session(s)
    """
```

**Key Protection:** Uses `is_active` flag on schedules to prevent generating sessions for paused schedules.

## URL Routes (New)

```
# View/manage schedules
/students/<id>/schedules/           → student_schedules (list all)
/schedules/<id>/edit/               → edit_schedule
/schedules/<id>/delete/             → delete_schedule

# View/manage exceptions
/students/<id>/exceptions/          → manage_exceptions (list all)
/exceptions/<schedule_id>/create/   → create_exception
/exceptions/<id>/edit/              → edit_exception
/exceptions/<id>/delete/            → delete_exception
```

## UI Workflows

### Workflow 1: Edit a Schedule Rule

**Goal:** Change a student's Monday session to Wednesday

```
Dashboard → Students → [Student Name] → Edit Schedules
→ [Schedule Card] → Edit Button
→ Change Day to "Wednesday"
→ Save
→ System regenerates future sessions on Wednesday
```

### Workflow 2: Skip a Week

**Goal:** Student is on vacation; skip next week's session

```
Dashboard → Students → [Student Name] → Edit Schedules
→ Manage Exceptions
→ Add Exception
→ Select Schedule
→ Exception Type: "Skip Week"
→ Week Start Date: [Monday of vacation week]
→ Save
→ System removes session for that week
```

### Workflow 3: Move a Session

**Goal:** Reschedule Monday session to Friday due to tutor conflict

```
Dashboard → Students → [Student Name] → Edit Schedules
→ Manage Exceptions
→ Add Exception
→ Select Schedule (Monday rule)
→ Exception Type: "Move Session"
→ Week Start Date: [target week]
→ Move to Date: [Friday date]
→ Move to Time: [original time]
→ Save
→ System creates session on Friday instead
```

### Workflow 4: Add Makeup Sessions

**Goal:** Student missed 2 weeks; add 2 makeup sessions this week

```
Dashboard → Students → [Student Name] → Edit Schedules
→ Manage Exceptions
→ Add Exception
→ Select Schedule
→ Exception Type: "Add Sessions"
→ Week Start Date: [target week]
→ Number of Sessions: 2
→ Date: [makeup day]
→ Start Time: [time]
→ Save
→ System creates 2 sessions on that date, 1 hour apart
```

## Database Changes

### Migration 0003_recurringschedule_created_at_and_more.py

```python
- Add field 'is_active' to RecurringSchedule (default=True)
- Add field 'created_at' to RecurringSchedule (auto_now_add)
- Add field 'updated_at' to RecurringSchedule (auto_now)
- Create model 'ScheduleException'
```

**Applied:** Yes ✅

## Behavior Rules

### ✅ What Always Happens

1. **Past Sessions Never Affected**: Only future sessions can be modified
2. **Base Schedule Preserved**: Exceptions don't modify base rule
3. **Exception Types Exclusive**: Each exception can be ONE type (skip/move/add)
4. **Validation**: Prayer times, conflicts checked before creating sessions
5. **Audit Trail**: Created_at, created_by tracked for exceptions

### ✅ What Happens on Save

1. **Schedule Edit**: Regenerates next 4 weeks of sessions
2. **Exception Create**: Regenerates next 4 weeks with exception applied
3. **Exception Edit**: Regenerates next 4 weeks with updated exception
4. **Exception Delete**: Regenerates to remove exception's effects

### ⚠️ Considerations

- **Week Definition**: Monday = start of week (used for week_start_date)
- **Multiple Exceptions**: Can have multiple exceptions for same schedule/week
- **Spacing**: Multiple added sessions spaced 1 hour apart
- **Timezone**: All times stored in Cairo timezone (CAIRO_TZ)

## Testing Checklist

- [ ] Create student with schedule
- [ ] Edit schedule rule (change day)
- [ ] Edit schedule rule (change time)
- [ ] Toggle schedule active/inactive
- [ ] Create SKIP exception
- [ ] Create MOVE exception with valid date/time
- [ ] Create ADD exception with multiple sessions
- [ ] Verify past sessions unaffected
- [ ] Verify future sessions regenerated
- [ ] Delete exception, verify sessions updated
- [ ] Delete schedule, verify cascading exception deletion
- [ ] Validate slot conflicts checked
- [ ] Verify prayer time blocking still works

## Forms

### RecurringScheduleForm
Fields: `weekday`, `start_time`, `is_active`
Validation: Standard model validation

### ScheduleExceptionForm
Fields: `exception_type`, `week_start_date`, `move_to_date`, `move_to_time`, `add_date`, `add_time`, `add_count`, `reason`
Validation: 
- If MOVE type: must have move_to_date and move_to_time
- If ADD type: must have add_date and add_time

## Templates

1. **student_schedules.html**: List all schedules, edit/delete buttons
2. **schedule_form.html**: Edit schedule rule
3. **schedule_exceptions.html**: Tabbed view of exceptions by schedule
4. **exception_form.html**: Create/edit exception with type-specific fields
5. **student_detail.html** (updated): New "Schedule Management" section

## API Endpoints

All endpoints are GET/POST only; no REST API currently.

- GET `/students/<id>/schedules/` → List schedules
- POST `/schedules/<id>/edit/` → Save schedule changes
- POST `/schedules/<id>/delete/` → Delete schedule
- GET `/students/<id>/exceptions/` → List exceptions
- POST `/exceptions/<schedule_id>/create/` → Create exception
- POST `/exceptions/<id>/edit/` → Save exception changes
- POST `/exceptions/<id>/delete/` → Delete exception

## Deployment

Requires:
1. Run migrations: `python manage.py migrate scheduler`
2. No manual data fixes needed
3. Existing schedules default to `is_active=True`
4. No breaking changes to existing views

## Performance Notes

- Queries optimized with `select_related()` where needed
- Exceptions loaded per schedule (no N+1)
- Session generation respects `weeks=4` limit
- No recurring queries in templates

## Future Enhancements

1. **Bulk Operations**: Apply exception to multiple students
2. **Recurring Exceptions**: "Skip every 4th week"
3. **Exception Templates**: Pre-made exception patterns
4. **Session History**: Track which exception generated which session
5. **Notification System**: Alert tutor when exception created
6. **Calendar Integration**: Visual indicators for exceptions on calendar

## Support

For issues or questions:
1. Check database migrations completed: `python manage.py showmigrations scheduler`
2. Verify forms render: Visit `/students/<id>/schedules/`
3. Test session generation: `generate_sessions_for_student(student, weeks=4)`
4. Check server logs for validation errors
