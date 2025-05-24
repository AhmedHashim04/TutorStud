import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: {
          // Navigation
          dashboard: "Dashboard",
          myCourses: "My Courses",
          assignments: "Assignments",
          messages: "Messages",
          profile: "Profile",
          logout: "Logout",
          
          // Dashboard
          welcomeBack: "Welcome back, {{name}}!",
          todayActivity: "Here's what's happening with your courses today.",
          activeCourses: "Active Courses",
          pendingTasks: "Pending Tasks",
          progress: "Progress",
          newMessages: "New Messages",
          
          // Courses
          recentCourses: "Recent Courses",
          viewAll: "View All",
          enrollInCourse: "Enroll in Course",
          createCourse: "Create New Course",
          courseDetails: "Course Details",
          courseMaterials: "Course Materials",
          
          // Assignments
          upcomingAssignments: "Upcoming Assignments",
          dueDate: "Due Date",
          dueTomorrow: "Due Tomorrow",
          dueIn: "Due in {{time}}",
          submitAssignment: "Submit Assignment",
          gradeAssignment: "Grade Assignment",
          
          // Messages
          recentMessages: "Recent Messages",
          sendMessage: "Send Message",
          newMessage: "New Message",
          
          // Quick Actions
          quickActions: "Quick Actions",
          uploadMaterials: "Upload Materials",
          scheduleAssignment: "Schedule Assignment",
          
          // Recent Activity
          recentActivity: "Recent Activity",
          assignmentSubmitted: "Assignment submitted",
          newMessageFrom: "New message from instructor",
          courseMaterialUploaded: "New course material uploaded",
          gradeReceived: "Grade received",
          
          // Common
          save: "Save",
          cancel: "Cancel",
          submit: "Submit",
          edit: "Edit",
          delete: "Delete",
          loading: "Loading...",
          error: "Error",
          success: "Success",
          
          // Time
          hoursAgo: "{{count}} hours ago",
          daysAgo: "{{count}} days ago",
          yesterday: "Yesterday",
          now: "Now",
        }
      },
      ar: {
        translation: {
          // Navigation
          dashboard: "لوحة التحكم",
          myCourses: "دوراتي",
          assignments: "المهام",
          messages: "الرسائل",
          profile: "الملف الشخصي",
          logout: "تسجيل الخروج",
          
          // Dashboard
          welcomeBack: "مرحباً بعودتك، {{name}}!",
          todayActivity: "إليك ما يحدث مع دوراتك اليوم.",
          activeCourses: "الدورات النشطة",
          pendingTasks: "المهام المعلقة",
          progress: "التقدم",
          newMessages: "رسائل جديدة",
          
          // Courses
          recentCourses: "الدورات الأخيرة",
          viewAll: "عرض الكل",
          enrollInCourse: "الانضمام للدورة",
          createCourse: "إنشاء دورة جديدة",
          courseDetails: "تفاصيل الدورة",
          courseMaterials: "المواد الدراسية",
          
          // Assignments
          upcomingAssignments: "المهام القادمة",
          dueDate: "تاريخ التسليم",
          dueTomorrow: "مطلوب غداً",
          dueIn: "مطلوب خلال {{time}}",
          submitAssignment: "تسليم المهمة",
          gradeAssignment: "تقييم المهمة",
          
          // Messages
          recentMessages: "الرسائل الأخيرة",
          sendMessage: "إرسال رسالة",
          newMessage: "رسالة جديدة",
          
          // Quick Actions
          quickActions: "الإجراءات السريعة",
          uploadMaterials: "رفع المواد",
          scheduleAssignment: "جدولة مهمة",
          
          // Recent Activity
          recentActivity: "النشاط الأخير",
          assignmentSubmitted: "تم تسليم المهمة",
          newMessageFrom: "رسالة جديدة من المدرس",
          courseMaterialUploaded: "تم رفع مادة دراسية جديدة",
          gradeReceived: "تم استلام الدرجة",
          
          // Common
          save: "حفظ",
          cancel: "إلغاء",
          submit: "إرسال",
          edit: "تحرير",
          delete: "حذف",
          loading: "جاري التحميل...",
          error: "خطأ",
          success: "نجح",
          
          // Time
          hoursAgo: "منذ {{count}} ساعات",
          daysAgo: "منذ {{count}} أيام",
          yesterday: "أمس",
          now: "الآن",
        }
      }
    },
    lng: 'en',
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
