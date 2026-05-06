# Quick Start: Flexible Schedule Management

## For Tutors: Managing Student Schedules Flexibly

### The Problem You're Solving

Before: You had to delete and recreate schedules when things changed. Now: Make quick adjustments without disrupting the system.

---

## 📋 5-Minute Setup

### Step 1: Access Schedule Management
```
Dashboard → Students → [Pick Student] → Edit Schedules
```

### Step 2: View Current Schedules
You'll see a table of all recurring sessions:
- **Sunday at 3:00 PM** (Active)
- **Wednesday at 5:00 PM** (Active)
- etc.

### Step 3: Make a Change
Click the 🖍️ **Edit** button on any schedule

---

## 🎯 Common Scenarios

### "I need to move the Tuesday session to Thursday"

1. Go to Edit Schedules
2. Click Edit on the Tuesday session
3. Change "Day of Week" to Thursday
4. Click Save
5. ✅ Future sessions move to Thursday automatically

**What happens:**
- Past Tuesday sessions stay
- Future sessions now on Thursday
- Base rule updated

---

### "Student is on vacation next week - skip it"

1. Go to Edit Schedules
2. Click "Manage Exceptions"
3. Click "Add Exception"
4. Select the recurring schedule
5. Choose "Skip Week"
6. Set "Week Start Date" to next Monday
7. Click Save
8. ✅ No session generated for that week

**What happens:**
- Regular schedule untouched
- Just this one week skipped
- Week after, normal sessions resume

---

### "Reschedule Monday to Friday this week"

1. Go to Edit Schedules
2. Click "Manage Exceptions"
3. Click "Add Exception"
4. Select the Monday schedule
5. Choose "Move Session"
6. Week Start Date: Monday of this week
7. Move to Date: Friday's date
8. Move to Time: (keep same or change)
9. Click Save
10. ✅ This week's session moved to Friday

---

### "Add 2 makeup sessions this week"

1. Go to Edit Schedules
2. Click "Manage Exceptions"
3. Click "Add Exception"
4. Select the schedule
5. Choose "Add Sessions"
6. Number of Sessions: 2
7. Date: (pick a day)
8. Start Time: (pick time)
9. Click Save
10. ✅ 2 sessions created (1 hour apart)

---

## 💡 Key Concepts

### Schedule Rule vs. Session
- **Schedule Rule**: The standing pattern (Tuesday at 3 PM)
- **Session**: One actual appointment (Tuesday Jan 15 at 3 PM)

### Changes Don't Affect Past
When you edit a schedule:
- ✅ Future sessions affected
- ❌ Past sessions untouched
- ✅ Record stays clean

### Exceptions Are Temporary
When you add an exception:
- ✅ Doesn't change the base rule
- ✅ Only affects that specific week
- ✅ Base rule stays intact

### Active vs. Paused
- **Active** (🟢): New sessions generated normally
- **Paused** (⚫): No new sessions, rule stays in system

---

## 🚀 Power Moves

### Temporarily Pause a Student
1. Edit Schedules
2. Edit the schedule
3. Uncheck "Active Schedule"
4. Save
5. ✅ No new sessions generated until you re-enable

**Use when:** Student paying installment, taking a break, etc.

---

### Bulk Reschedule Pattern
**Scenario:** Every Tuesday needs to move to Thursday

1. Edit first schedule (Tuesday) → change to Thursday → Save
2. Do same for other Tuesday slots
3. All future sessions updated

---

### Document Everything
Use the "Reason" field when creating exceptions:
- "Student requested makeup"
- "Tutor traveling"
- "Birthday makeup session"
- etc.

Helps you remember why you made changes!

---

## ⚠️ Be Careful!

### ❌ DON'T
- Delete a schedule when you just need to pause it (use Active toggle instead)
- Create overlapping exceptions for the same week
- Move sessions to times blocked by prayers

### ✅ DO
- Check the calendar before moving sessions (avoid conflicts)
- Document exceptions with reasons
- Review upcoming sessions after making changes

---

## 📱 Where to Find Things

| What | Where |
|------|-------|
| View all schedules | Dashboard → Students → [Name] → Edit Schedules |
| Edit a schedule | Edit Schedules → 🖍️ Edit button |
| Delete a schedule | Edit Schedules → 🗑️ Trash button |
| Manage exceptions | Edit Schedules → ⭐ Manage Exceptions |
| Add exception | Manage Exceptions → Add Exception button |
| See all exceptions | Manage Exceptions → Tabbed view |

---

## 🎓 Examples

### Example 1: Weekly Schedule → Bi-weekly
**Goal:** Change from every week to every 2 weeks

❌ Old way: Delete schedule, recreate
✅ New way:
1. Add exception: Skip Week (every other week)
2. Repeat for each week to skip

(Note: Bi-weekly support coming soon)

---

### Example 2: Student Starts Late
**Goal:** Student can't start until February 15

✅ Best approach:
1. Create schedule with today's date
2. Add consecutive "Skip Week" exceptions until Feb 15
3. When Feb 15 arrives, other exceptions deleted

---

### Example 3: Holiday Break
**Goal:** No sessions for 2 weeks (Dec 20 - Jan 5)

✅ Solution:
1. Edit schedule → Uncheck "Active"
2. Set reminder to re-enable Jan 6
3. When ready: Edit schedule → Check "Active" → Save

---

## 🔧 Troubleshooting

### "I edited the schedule but sessions didn't change"
Check recent sessions in calendar - they may have already been created before you edited.
Only future sessions are affected.

### "I got an error about prayer times"
Ensure no conflict with prayer time blocks. Check Settings → Prayer Times.

### "Can't move session to that date"
Another student may have schedule at that time. Check calendar first.

### "Exception not showing"
Refresh the page. System regenerates sessions when you save.

---

## 📊 Session Generation Rules

When you save changes:
- System looks ahead 4 weeks
- Applies exceptions
- Generates new sessions
- Updates calendar

**Frequency:** Every time you:
- Edit a schedule
- Create an exception
- Edit an exception
- Delete an exception

---

## 🎯 Best Practices

1. **Name Your Exceptions**
   - Use "Reason" field
   - "Student request" vs "Tutor unavailable" matters later

2. **Batch Changes**
   - Edit all schedules, then refresh
   - Makes calendar update cleaner

3. **Review After Changing**
   - Go to calendar
   - Verify sessions look correct
   - Spot conflicts early

4. **Use Pause, Not Delete**
   - Toggle active off instead of deleting
   - Exceptions stay preserved
   - Can re-enable anytime

5. **Document Holidays**
   - Add exceptions early for known holidays
   - Prevents accidentally generating sessions

---

## ❓ FAQ

**Q: Does editing a schedule affect past sessions?**
A: No. Only future sessions change.

**Q: Can I have multiple exceptions for the same week?**
A: Yes - one SKIP, one MOVE, one ADD per week.

**Q: What happens when I delete a schedule?**
A: Exceptions deleted too. Future sessions no longer generated.

**Q: Can I edit an exception after creating it?**
A: Yes - click the 🖍️ Edit button on that exception.

**Q: If I pause a schedule, are exceptions still active?**
A: No - paused schedules don't generate any sessions. Exceptions only matter for active schedules.

**Q: Can I move a session to next week?**
A: Yes - just pick a date in the next week in the "Move to Date" field.

---

## 📞 Need Help?

Check the system for:
- Info icons (ℹ️) explain what fields do
- Blue alerts explain what happens when you save
- Hover tooltips on form labels

---

**Happy scheduling!** 🎓✨
