# 🏗️ TutorStud System Redesign - Complete Architecture

**Created:** May 6, 2026  
**Status:** Comprehensive Redesign Document  
**For:** Single Private Teacher Management System

---

## 📋 EXECUTIVE SUMMARY

### Current System Issues
1. **Payment Logic Broken**: Earnings calculated by `(hourly_rate * duration) / 60 * sessions_per_week` - not tied to actual attendance
2. **Fragmented Student Onboarding**: Separate Student → Subscription → RecurringSchedule forms
3. **Auto-generation Missing**: Recurring schedules don't generate actual sessions
4. **No Global Config**: Every setting duplicated per subscription
5. **Weak Analytics**: Only basic weekly/monthly earnings display
6. **No Payment Control**: Can't override payment per session or track cancellation rules
7. **Status Confusion**: Session statuses (scheduled, completed, cancelled, missed) don't map to payment logic

### New System Design Goals
✅ **Single, unified student enrollment flow**  
✅ **Clear, rule-based payment system**  
✅ **Automatic session generation with manual overrides**  
✅ **Global configuration with per-student overrides**  
✅ **Rich analytics dashboard with insights**  
✅ **Zero data loss migration**  

---

## 🎯 CORE BUSINESS RULES (Implemented as Code)

### Payment Rules Engine
```
Rule 1: ATTENDED SESSION
  Condition: status = 'completed' AND attendance = 'present'
  Result: teacher_paid = TRUE, amount = session.price

Rule 2: NO-SHOW (Absent without notice)
  Condition: status = 'completed' AND attendance = 'absence'
  Result: teacher_paid = TRUE, amount = session.price

Rule 3: STUDENT CANCELLED (≥2 hours before)
  Condition: status = 'cancelled' AND cancelled_by = 'student'
           AND time_to_session ≥ cancellation_window
  Result: teacher_paid = FALSE, amount = 0

Rule 4: STUDENT CANCELLED (<2 hours before)
  Condition: status = 'cancelled' AND cancelled_by = 'student'
           AND time_to_session < cancellation_window
  Result: teacher_paid = TRUE, amount = session.price

Rule 5: TEACHER CANCELLED
  Condition: status = 'cancelled' AND cancelled_by = 'teacher'
  Result: teacher_paid = FALSE, amount = 0

Rule 6: MANUAL OVERRIDE
  Condition: session.payment_override IS NOT NULL
  Result: teacher_paid = override_value, amount = override_amount

Rule 7: RESCHEDULED SESSION
  Condition: status = 'rescheduled'
  Result: teacher_paid = FALSE (payment applies to replacement session)
```

### Cancellation Window Rules
- **Default**: 2 hours before session start
- **Teacher Override**: Can manually accept late cancellation → reschedule
- **Configuration**: Stored in GlobalConfig, applied to all students unless overridden per enrollment

---

## 🏗️ ARCHITECTURE LAYERS

### 1. **Data Layer** (Models)
- **GlobalConfig** (singleton): System-wide defaults
- **StudentEnrollment** (core entity): Student + Schedule + Price + Rules
- **Session** (generated from enrollment): Individual teaching session
- **SessionPayment** (tracked separately): How much teacher earned
- **SessionAttendance** (marked by teacher): Actual attendance record
- **Analytics** (denormalized): Pre-computed metrics for speed

### 2. **Service Layer** (Business Logic)
- **EnrollmentService**: Create/update enrollments
- **SessionGenerationService**: Auto-create sessions from recurring schedule
- **PaymentService**: Calculate payment based on rules
- **AttendanceService**: Mark attendance → trigger payment
- **CancellationService**: Cancel/reschedule sessions
- **AnalyticsService**: Compute dashboard metrics

### 3. **API Layer** (Views/Serializers)
- **EnrollmentAPI**: CRUD operations
- **SessionAPI**: List, detail, mark attendance, cancel, reschedule
- **PaymentAPI**: List payments, override payment
- **AnalyticsAPI**: Dashboard data, charts, insights

### 4. **UI Layer** (Templates)
- Unified student enrollment flow
- Teacher control panel (mark attendance, manage sessions)
- Analytics dashboard (revenue, attendance, patterns)
- Reports (monthly, weekly, per-student)

---

## 📊 DATA MODELS (New Schema)

### GlobalConfig (Singleton)
```python
class GlobalConfig(models.Model):
    # Pricing
    default_session_price = Decimal  # e.g., 200.00
    default_session_duration = IntegerField  # e.g., 60 (minutes)
    
    # Rules
    cancellation_window_hours = IntegerField  # e.g., 2
    allow_makeup_sessions = Boolean  # default=True
    allow_extra_sessions = Boolean  # default=True
    
    # Metadata
    updated_at = DateTimeField(auto_now=True)
    
    def __str__(self):
        return "System Configuration"
```

### StudentEnrollment (Core Entity) - REPLACES Subscription
```python
class StudentEnrollment(models.Model):
    # FK
    student = ForeignKey(Student)
    
    # Schedule
    recurring_schedule = ForeignKey(RecurringSchedule, null=True)
    # recurring_schedule contains:
    #   - day_of_week (Mon/Tue/etc)
    #   - start_time
    #   - duration
    
    # Pricing (snapshot from GlobalConfig at creation time)
    session_price = Decimal  # per session, not hourly
    session_duration = IntegerField  # minutes
    
    # Configuration (snapshot from GlobalConfig)
    cancellation_window_hours = IntegerField
    allow_makeup_sessions = Boolean
    allow_extra_sessions = Boolean
    
    # Status
    is_active = Boolean
    start_date = DateField
    end_date = DateField(null=True, blank=True)
    
    # Metadata
    config_snapshot = JSONField  # entire GlobalConfig at enrollment time
    created_at = DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.student.name} - {self.recurring_schedule}"
    
    @property
    def next_session_date(self):
        return self.sessions.filter(status='scheduled').first()?.start_time
    
    @property
    def active_sessions(self):
        return self.sessions.filter(status='scheduled')
```

### Session (Generated from Enrollment)
```python
class Session(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled to another date'),
    ]
    
    CANCELLED_BY_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]
    
    # FKs
    student = ForeignKey(Student)
    enrollment = ForeignKey(StudentEnrollment)  # which enrollment generated this
    recurring_schedule = ForeignKey(RecurringSchedule, null=True, blank=True)
    
    # Timing
    start_time = DateTimeField
    end_time = DateTimeField
    
    # Status
    status = CharField(choices=STATUS_CHOICES)
    cancelled_by = CharField(choices=CANCELLED_BY_CHOICES, null=True, blank=True)
    cancelled_at = DateTimeField(null=True, blank=True)
    cancellation_reason = TextField(blank=True)
    
    # Session Type  
    session_type = CharField(choices=[
        ('regular', 'From recurring schedule'),
        ('extra', 'Extra session'),
        ('makeup', 'Makeup session'),
    ], default='regular')
    
    # Original session if this is a makeup
    original_session = ForeignKey('self', null=True, blank=True, related_name='makeup_sessions')
    
    # Override
    is_override = Boolean  # Date/time modified from recurring pattern
    override_price = Decimal(null=True, blank=True)  # if different from enrollment price
    
    # Metadata
    notes = TextField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_time']
    
    @property
    def duration_minutes(self):
        return int((self.end_time - self.start_time).total_seconds() / 60)
    
    def can_be_cancelled_free(self):
        """Check if cancellation within window (no payment)"""
        time_until = self.start_time - timezone.now()
        return time_until.total_seconds() / 3600 >= self.enrollment.cancellation_window_hours
```

### SessionAttendance (Attendance Record)
```python
class SessionAttendance(models.Model):
    ATTENDANCE_CHOICES = [
        ('present', 'Student attended'),
        ('absence', 'Student absent (no notice)'),
        ('late', 'Student late'),
    ]
    
    session = OneToOneField(Session, on_delete=models.CASCADE, related_name='attendance')
    attendance_status = CharField(choices=ATTENDANCE_CHOICES)
    marked_at = DateTimeField(auto_now_add=True)
    notes = TextField(blank=True)
    
    def __str__(self):
        return f"{self.session.student.name} - {self.get_attendance_status_display()}"
```

### SessionPayment (Payment Record)
```python
class SessionPayment(models.Model):
    session = OneToOneField(Session, on_delete=models.CASCADE, related_name='payment')
    
    # Amount
    base_amount = Decimal  # enrollment.session_price
    override_amount = Decimal(null=True, blank=True)
    final_amount = Decimal  # base or override
    
    # Rule Applied
    rule_applied = CharField(max_length=100)  # which business rule triggered payment
    
    # Status
    is_paid = Boolean  # whether teacher received payment
    
    # Metadata
    calculated_at = DateTimeField(auto_now_add=True)
    reason = TextField(blank=True)
    
    def __str__(self):
        return f"{self.session} - {self.final_amount} (paid={self.is_paid})"
```

### RecurringSchedule (Unchanged Core Concept)
```python
class RecurringSchedule(models.Model):
    # Keep existing structure:
    student = ForeignKey(Student)
    day_of_week = IntegerField(choices=WEEKDAYS)
    start_time = TimeField
    duration = IntegerField  # 30, 45, 60, 90
    is_active = Boolean
    created_at = DateTimeField(auto_now_add=True)
    
    # Note: This no longer has Subscription FK
    #       Instead, StudentEnrollment points to RecurringSchedule
```

### StudentEnrollmentHistory (Audit Trail)
```python
class StudentEnrollmentHistory(models.Model):
    enrollment = ForeignKey(StudentEnrollment)
    action = CharField(choices=[
        ('created', 'Created'),
        ('price_changed', 'Price changed'),
        ('schedule_changed', 'Schedule changed'),
        ('deactivated', 'Deactivated'),
    ])
    old_value = JSONField(null=True)
    new_value = JSONField
    changed_at = DateTimeField(auto_now_add=True)
    reason = TextField(blank=True)
```

---

## 🎨 UX FLOW REDESIGN

### FLOW 1: Add New Student (Unified)
```
Step 1: Basic Info
  ├─ Name
  ├─ Country
  ├─ Timezone
  └─ Notes

Step 2: Schedule Setup
  ├─ Recurring schedule
  │  ├─ Day(s) of week (checkboxes)
  │  ├─ Start time
  │  └─ Duration (dropdown)
  |
  └─ OR: Flexible (no recurring)

Step 3: Pricing & Rules
  ├─ Session price (auto-filled from GlobalConfig)
  ├─ Session duration (auto-filled from GlobalConfig)
  ├─ Cancellation window (auto-filled from GlobalConfig)
  ├─ Allow makeup sessions (toggle)
  └─ Allow extra sessions (toggle)

Step 4: Review & Confirm
  ├─ Summary of all settings
  ├─ "Generate sessions for next 3 months?" (checkbox)
  └─ Create button

✓ Result: Single StudentEnrollment created
           Sessions auto-generated (if selected)
           Teacher ready to teach
```

### FLOW 2: Teacher's Daily Control Panel
```
📅 CALENDAR VIEW

┌─────────────────────────────────────┐
│ May 6, 2026                         │
├─────────────────────────────────────┤
│                                     │
│  10:00  [Ahmed Hassan]  ✓           │
│         30 min | EGP 200             │
│                                     │
│  12:00  [Layla Ahmed]   ⊘           │
│         60 min | EGP 200  [Mark]    │
│                                     │
│  14:00  [Fatima Mohamed] ⏱           │
│         45 min | EGP 150  [In 30m]   │
│                                     │
│  16:00  [+] Add Extra Session       │
│                                     │
└─────────────────────────────────────┘

Each session card has:
  ✓ (Completed)
  ⊘ (Missed/No action yet)
  ⏱ (In progress)
  
  Actions (hover/click):
  - Mark attendance
  - Reschedule
  - Cancel
  - Add notes
  - Override payment
```

### FLOW 3: Mark Attendance
```
Teacher clicks "Mark" on a session:

┌─────────────────────────────────────┐
│ Mark Attendance - Ahmed Hassan      │
├─────────────────────────────────────┤
│                                     │
│ Session: Mon 10:00 AM - 10:30 AM   │
│ Expected Payment: EGP 200           │
│                                     │
│ Did student attend?                 │
│ ( ) Yes, attended on time          │
│ ( ) Yes, but was late              │
│ ( ) No, absent                     │
│                                     │
│ Notes (optional): _______________   │
│                                     │
│ [Override Payment]  [Mark & Close]  │
│                                     │
└─────────────────────────────────────┘

✓ Result: SessionAttendance created
          SessionPayment calculated via rules
          Balance updated
```

### FLOW 4: Reschedule Session
```
Teacher clicks "Reschedule" on session:

┌─────────────────────────────────────┐
│ Reschedule Session                  │
├─────────────────────────────────────┤
│                                     │
│ Original: Mon 10:00 (Ahmed Hassan) │
│                                     │
│ New Date & Time:                    │
│ Date: [May 7] [Calendar picker]     │
│ Time: [14:00] [Time picker]         │
│ Duration: [Same as original]        │
│                                     │
│ Reason: [Late student notice]       │
│                                     │
│ [Reschedule]  [Cancel]              │
│                                     │
└─────────────────────────────────────┘

✓ Result: Original session → status='rescheduled'
          New session created with session_type='makeup'
          Original session links to makeup: original_session_id
          Payment applies to makeup, not original
```

### FLOW 5: Add Extra Session
```
Teacher clicks "Add Extra Session":

┌─────────────────────────────────────┐
│ Add Extra Session                   │
├─────────────────────────────────────┤
│                                     │
│ Student: [Dropdown of active]       │
│ Date: [May 7]                       │
│ Time: [14:00]                       │
│ Duration: [60 min] or custom        │
│ Price: [EGP 200] (can override)     │
│                                     │
│ [Add Session]                       │
│                                     │
└─────────────────────────────────────┘

✓ Result: Session created with session_type='extra'
          Added to calendar
```

### FLOW 6: Global Configuration
```
Settings → System Configuration

┌─────────────────────────────────────┐
│ Global System Settings              │
├─────────────────────────────────────┤
│                                     │
│ Default Session Price: [EGP 200]   │
│ Default Duration: [60] minutes     │
│ Cancellation Window: [2] hours     │
│                                     │
│ Allow Makeup Sessions: [✓]          │
│ Allow Extra Sessions: [✓]           │
│                                     │
│ [Save Defaults]                     │
│                                     │
│ ℹ️  These apply to new students only│
│    Existing enrollments keep their  │
│    snapshot values                  │
│                                     │
└─────────────────────────────────────┘
```

---

## 📊 ANALYTICS DASHBOARD REDESIGN

### 📈 Key Metrics (Top Section)
```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ This Month   │ Expected     │ Lost due to  │ No-show Rate │
│ Revenue      │ Revenue      │ Cancellations│              │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ EGP 12,500   │ EGP 14,200   │ EGP 1,700    │ 8%           │
│ ↑ 15% vs     │ (full rate)  │ (student     │ (1 of 12     │
│ last month   │              │  cancelled)  │  students)   │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

### 📊 Charts & Insights

#### Chart 1: Monthly Revenue Trend
```
EGP 15,000 │
           │     ╱╲
EGP 10,000 │    ╱  ╲    ╱╲
           │   ╱    ╲  ╱  ╲
EGP 5,000  │  ╱      ╲╱    ╲___
           │
           └────────────────────
             Jan Feb Mar Apr May

Legend:
  — Actual Revenue
  - - Expected (full rate)
```

#### Chart 2: Attendance by Student
```
Ahmed Hassan    ████████░░  90%
Layla Muhammad  ███████░░░░  70%
Fatima Mohamed  ██████████  100%
Mohammed Ali    ████░░░░░░  40%
```

#### Chart 3: Sessions by Day of Week
```
Saturday   ████████ 8 sessions (100% paid)
Sunday     ██████ 6 sessions (100% paid)
Monday     ████████████ 12 sessions (83% paid)
Tuesday    ██████ 6 sessions (67% paid)
```

### 🧠 Smart Insights
```
⚠️  Alert: No-Show Pattern
    Mohammed Ali has missed 3 of 7 sessions this month.
    Consider rescheduling or having a discussion.

💡 Insight: Most Profitable Day
    Saturdays generate EGP 1,600 on average.
    Consider adding more Sat sessions if available.

📈 Recommendation: Revenue Optimization  
    Current occupancy: 73%
    You could earn EGP 2,100 more by filling
    3 free slots next week (available: Tue 2pm, Wed 10am, Thu 6pm)

✨ Streak: Perfect Attendance
    5 students haven't missed a session in 30 days!
```

---

## 🔧 SERVICE LAYER (Business Logic)

### PaymentService
```python
class PaymentService:
    @staticmethod
    def calculate_payment_for_session(session):
        """
        Apply business rules to determine payment amount.
        Returns: (is_paid, amount, rule_applied, reason)
        """
        
        # Check if manual override exists
        if session.payment.override_amount is not None:
            return (
                True,
                session.payment.override_amount,
                'MANUAL_OVERRIDE',
                'Teacher manually set payment'
            )
        
        # If session not yet marked as complete, can't calculate
        if session.status != 'completed':
            return (False, 0, 'PENDING', 'Session not yet completed')
        
        # Get attendance  
        attendance = session.attendance
        if not attendance:
            # Session completed but attendance not marked
            # Assume present for now (configurable)
            return (True, session.enrollment.session_price, 'ASSUMED_PRESENT', '')
        
        # Rule engine
        if attendance.attendance_status == 'present':
            return (True, session.enrollment.session_price, 'ATTENDED', '')
        
        if attendance.attendance_status == 'absence':
            return (True, session.enrollment.session_price, 'NO_SHOW', '')
        
        # Cancelled cases
        if session.status == 'cancelled':
            if session.cancelled_by == 'teacher':
                return (False, 0, 'CANCELLED_BY_TEACHER', '')
            
            if session.cancelled_by == 'student':
                is_on_time = session.can_be_cancelled_free()
                if is_on_time:
                    return (False, 0, 'CANCELLED_ON_TIME', '')
                else:
                    return (True, session.enrollment.session_price, 'CANCELLED_LATE', 'Too late to cancel')
        
        # Rescheduled
        if session.status == 'rescheduled':
            return (False, 0, 'RESCHEDULED', 'Payment applies to makeup session')
        
        return (False, 0, 'UNKNOWN', 'Could not determine payment rule')

    @staticmethod
    def trigger_payment_on_attendance_mark(session, attendance_status):
        """Called when teacher marks attendance"""
        session.attendance.attendance_status = attendance_status
        session.attendance.save()
        
        is_paid, amount, rule, reason = PaymentService.calculate_payment_for_session(session)
        
        payment = session.payment or SessionPayment.objects.create(session=session)
        payment.base_amount = session.enrollment.session_price
        payment.final_amount = amount
        payment.rule_applied = rule
        payment.is_paid = is_paid
        payment.reason = reason
        payment.save()
        
        # Could trigger: webhook, notification, accounting integration, etc.
        return payment
```

### SessionGenerationService
```python
class SessionGenerationService:
    @staticmethod
    def generate_sessions_for_enrollment(enrollment, days_ahead=90):
        """
        Generate sessions from recurring_schedule.
        Respects working_hours and exception_days.
        """
        schedule = enrollment.recurring_schedule
        if not schedule:
            return []
        
        generated = []
        today = timezone.localdate()
        end_date = today + timedelta(days=days_ahead)
        
        # Iterate through date range
        current = today
        while current <= end_date:
            # Check if matches recurring day
            if current.weekday() == schedule.day_of_week:
                
                # Check exception days
                if ExceptionDay.objects.filter(date=current).exists():
                    current += timedelta(days=1)
                    continue
                
                # Create session
                start = make_aware_cairo(datetime.combine(current, schedule.start_time))
                end = start + timedelta(minutes=schedule.duration)
                
                # Check for conflicts (optional)
                if not SessionGenerationService.has_conflict(start, end, enrollment.student):
                    session = Session.objects.create(
                        student=enrollment.student,
                        enrollment=enrollment,
                        recurring_schedule=schedule,
                        start_time=start,
                        end_time=end,
                        session_type='regular',
                        status='scheduled'
                    )
                    SessionPayment.objects.create(session=session)
                    SessionAttendance.objects.create(session=session, attendance_status=None)
                    generated.append(session)
            
            current += timedelta(days=1)
        
        return generated

    @staticmethod
    def has_conflict(start, end, student):
        """Check if student has overlapping session"""
        conflicts = Session.objects.filter(
            student=student,
            status__in=['scheduled', 'completed'],
            start_time__lt=end,
            end_time__gt=start
        )
        return conflicts.exists()
```

### CancellationService
```python
class CancellationService:
    @staticmethod
    def cancel_session(session, cancelled_by, reason=''):
        """Cancel a session with proper logging"""
        session.status = 'cancelled'
        session.cancelled_by = cancelled_by
        session.cancelled_at = timezone.now()
        session.cancellation_reason = reason
        session.save()
        
        # Trigger payment recalculation
        PaymentService.calculate_payment_for_session(session)
    
    @staticmethod
    def reschedule_session(session, new_start, new_end, reason=''):
        """Reschedule session to new time (creates makeup)"""
        # Mark original as rescheduled
        session.status = 'rescheduled'
        session.cancellation_reason = reason
        session.save()
        
        # Create makeup session
        makeup = Session.objects.create(
            student=session.student,
            enrollment=session.enrollment,
            start_time=new_start,
            end_time=new_end,
            session_type='makeup',
            original_session=session,
            status='scheduled'
        )
        SessionPayment.objects.create(session=makeup)
        SessionAttendance.objects.create(session=makeup)
        
        return makeup
```

### AnalyticsService
```python
class AnalyticsService:
    @staticmethod
    def get_monthly_metrics(month, year):
        """Get dashboard metrics for month"""
        start = datetime(year, month, 1)
        end = datetime(year, month, 28) + timedelta(days=3)  # Next month
        end = end.replace(day=1)
        
        sessions = Session.objects.filter(
            start_time__gte=start,
            start_time__lt=end,
            status__in=['completed', 'cancelled']
        )
        
        paid_amount = sum(
            s.payment.final_amount 
            for s in sessions 
            if s.payment and s.payment.is_paid
        )
        
        total_expected = sum(
            s.enrollment.session_price 
            for s in sessions
        )
        
        lost_amount = total_expected - paid_amount
        
        no_shows = sessions.filter(
            attendance__attendance_status='absence'
        ).count()
        
        return {
            'actual_revenue': paid_amount,
            'expected_revenue': total_expected,
            'lost_revenue': lost_amount,
            'no_show_count': no_shows,
            'no_show_rate': (no_shows / max(sessions.count(), 1)) * 100,
            'total_sessions': sessions.count(),
        }

    @staticmethod
    def get_student_consistency(student, days=30):
        """Analyze student attendance pattern"""
        since = timezone.now() - timedelta(days=days)
        sessions = Session.objects.filter(
            student=student,
            start_time__gte=since,
            status__in=['completed', 'cancelled']
        )
        
        if not sessions:
            return None
        
        attended = sessions.filter(attendance__attendance_status__in=['present', 'late']).count()
        absent = sessions.filter(attendance__attendance_status='absence').count()
        cancelled = sessions.filter(status='cancelled').count()
        
        return {
            'attended': attended,
            'absent': absent,
            'cancelled_sessions': cancelled,
            'total': sessions.count(),
            'attendance_rate': (attended / max(sessions.count(), 1)) * 100,
        }
```

---

## 🔄 MIGRATION PLAN

### Phase 1: Data Preparation
```python
# management/commands/migrate_to_new_system.py

def migrate_subscriptions_to_enrollments():
    """Convert old Subscription → new StudentEnrollment"""
    
    global_config = GlobalConfig.objects.get_or_create(id=1)[0]
    
    for subscription in Subscription.objects.filter(is_active=True):
        student = subscription.student
        
        # Get recurring schedule if exists
        schedule = RecurringSchedule.objects.filter(
            student=student,
            is_active=True
        ).first()
        
        # Create enrollment snapshot of current config
        enrollment = StudentEnrollment.objects.create(
            student=student,
            recurring_schedule=schedule,
            session_price=subscription.session_rate,  # Already calculated (hourly * duration/60)
            session_duration=subscription.session_duration,
            cancellation_window_hours=2,  # Default (was implicit)
            allow_makeup_sessions=True,
            allow_extra_sessions=True,
            is_active=True,
            start_date=subscription.start_date,
            config_snapshot={
                'default_session_price': subscription.session_rate,
                'default_session_duration': subscription.session_duration,
                'cancellation_window_hours': 2,
            }
        )
        
        # Migrate existing sessions
        for old_session in Session.objects.filter(student=student):
            old_session.enrollment = enrollment
            old_session.save()
            
            # Create payment record
            if old_session.status == 'completed':
                is_paid = old_session.status != 'cancelled'
                SessionPayment.objects.create(
                    session=old_session,
                    base_amount=subscription.session_rate,
                    final_amount=subscription.session_rate if is_paid else 0,
                    rule_applied='MIGRATED_FROM_OLD_SYSTEM',
                    is_paid=is_paid,
                )
            
            # Create attendance record
            if not hasattr(old_session, 'attendance'):
                attendance_status = 'present' if old_session.status == 'completed' else 'absence'
                SessionAttendance.objects.create(
                    session=old_session,
                    attendance_status=attendance_status if old_session.status == 'completed' else None,
                )

def deactivate_old_models():
    """Mark old subscriptions as inactive"""
    Subscription.objects.all().update(is_active=False)
    RecurringSchedule.objects.all().update(is_active=False)
```

### Phase 2: Validation
```
✓ All student enrollments created
✓ All sessions linked to enrollments
✓ All payments calculated
✓ No data loss
✓ Historical earnings match
```

### Phase 3: Rollout
- Run migration in dev
- Verify data integrity
- Copy to staging with real data
- Teacher review & sign-off
- Deploy to production
- Keep old data for 6 months backup

---

## 🎯 KEY ARCHITECTURAL DECISIONS

### Decision 1: Price per Session (NOT Hourly Rate)
**Why**: Matches business model. Teacher charges per session, not per hour.
**Impact**: Simpler payment calculations, clearer to teacher, supports session length variations.

### Decision 2: Global Config + Enrollment Snapshot
**Why**: Teachers want system defaults BUT need historical consistency.
**Solution**: GlobalConfig stores current defaults. StudentEnrollment stores snapshot at creation.
**Benefit**: When teacher changes default price, existing students keep their agreed rate.

### Decision 3: Separate Payment Records
**Why**: Clear audit trail. Can override, track rules applied, integrate with accounting.
**Impact**: SessionPayment table grows, but enables future features (discounts, bonuses, etc).

### Decision 4: SessionAttendance vs Embedded
**Why**: Attendance is optional until session completes. Payment depends on it.
**Solution**: Separate model, nullable until marked. Clear separation of concerns.

### Decision 5: Auto-Generation + Manual Overrides
**Why**: Teachers want convenience (auto-schedule) + flexibility (change per session).
**Solution**: Auto-generate from enrollment, mark overridden sessions, allow modifications.

### Decision 6: Status Machine for Sessions
**Why**: Unclear state transitions → bugs.
**Solution**: Clear states: scheduled → completed OR cancelled OR rescheduled
**Transitions**:
  - scheduled → completed: Teacher marks attendance
  - scheduled → cancelled: Teacher/student cancels
  - scheduled → rescheduled: Automatic on reschedule (creates new makeup session)

### Decision 7: Denormalized Analytics
**Why**: Dashboard queries on 1000s of sessions would be slow.
**Solution**: Pre-compute metrics, store in Analytics table, update on session change.
**Cost**: Slight denormalization vs massive speed gain.

---

## 🚀 IMPLEMENTATION ROADMAP

### Week 1: Models & Migrations
- [ ] Create GlobalConfig, StudentEnrollment, SessionPayment, SessionAttendance models
- [ ] Write migration script
- [ ] Test with sample data

### Week 2: Service Layer
- [ ] Build PaymentService
- [ ] Build SessionGenerationService
- [ ] Build CancellationService
- [ ] Build AnalyticsService

### Week 3: Views & APIs
- [ ] Update StudentEnrollment CRUD views
- [ ] Build SessionListAPI with filtering
- [ ] Build PaymentAPI (list, override)
- [ ] Build AnalyticsAPI

### Week 4: Templates & UX
- [ ] Redesign student creation workflow
- [ ] Build teacher control panel (calendar view)
- [ ] Build analytics dashboard
- [ ] Build reports

### Week 5: Testing & Polish
- [ ] Unit tests for payment rules
- [ ] Integration tests for session generation
- [ ] E2E tests for critical flows
- [ ] Performance optimization

### Week 6: Deployment
- [ ] Migration on staging
- [ ] Teacher UAT
- [ ] Production deployment
- [ ] Monitoring & hotfixes

---

## 📋 QUICK REFERENCE: Old → New Mapping

| Old Model | Mapping |
|-----------|---------|
| Student | ✓ Keep unchanged |
| Subscription | → StudentEnrollment (NEW) |
| RecurringSchedule | ✓ Keep, use in enrollment |
| Session | ✓ Extend (add enrollment FK, payment FK) |
| Payment logic | → PaymentService (NEW) |
| Earnings calc | → SessionPayment table (NEW) |
| (none) | → GlobalConfig (NEW) |
| (none) | → SessionAttendance (NEW) |
| (none) | → SessionPayment (NEW) |

---

## 🎓 NEXT STEPS

1. **Review this document** with stakeholder
2. **Get clarification** on any business rules
3. **Review and approve** data models
4. **Start Phase 1** (Models & Migrations)
5. **Parallel**: Design exact UI mockups for control panel + dashboard

---

**Document Version:** 1.0  
**Last Updated:** May 6, 2026  
**Status:** Ready for Implementation
