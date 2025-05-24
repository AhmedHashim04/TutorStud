import {
  users, courses, assignments, assignmentSubmissions, courseMaterials,
  messages, notifications, courseEnrollments, courseAssistants,
  type User, type InsertUser, type Course, type InsertCourse,
  type Assignment, type InsertAssignment, type AssignmentSubmission, type InsertSubmission,
  type CourseMaterial, type InsertMaterial, type Message, type InsertMessage,
  type Notification, type InsertNotification, type CourseEnrollment, type CourseAssistant
} from "@shared/schema";

export interface IStorage {
  // Users
  getUser(id: number): Promise<User | undefined>;
  getUserByUsername(username: string): Promise<User | undefined>;
  getUserByEmail(email: string): Promise<User | undefined>;
  createUser(user: InsertUser): Promise<User>;
  updateUser(id: number, updates: Partial<InsertUser>): Promise<User | undefined>;

  // Courses
  getCourses(): Promise<Course[]>;
  getCoursesByInstructor(instructorId: number): Promise<Course[]>;
  getCoursesByStudent(studentId: number): Promise<Course[]>;
  getCourse(id: number): Promise<Course | undefined>;
  createCourse(course: InsertCourse): Promise<Course>;
  updateCourse(id: number, updates: Partial<InsertCourse>): Promise<Course | undefined>;
  deleteCourse(id: number): Promise<boolean>;

  // Course Enrollments
  enrollStudent(courseId: number, studentId: number): Promise<CourseEnrollment>;
  unenrollStudent(courseId: number, studentId: number): Promise<boolean>;
  getCourseEnrollments(courseId: number): Promise<CourseEnrollment[]>;
  getStudentEnrollments(studentId: number): Promise<CourseEnrollment[]>;
  updateEnrollmentProgress(courseId: number, studentId: number, progress: number): Promise<CourseEnrollment | undefined>;

  // Course Assistants
  assignAssistant(courseId: number, assistantId: number, permissions: any): Promise<CourseAssistant>;
  removeAssistant(courseId: number, assistantId: number): Promise<boolean>;
  getCourseAssistants(courseId: number): Promise<CourseAssistant[]>;

  // Assignments
  getAssignments(courseId: number): Promise<Assignment[]>;
  getAssignment(id: number): Promise<Assignment | undefined>;
  createAssignment(assignment: InsertAssignment): Promise<Assignment>;
  updateAssignment(id: number, updates: Partial<InsertAssignment>): Promise<Assignment | undefined>;
  deleteAssignment(id: number): Promise<boolean>;

  // Assignment Submissions
  getSubmissions(assignmentId: number): Promise<AssignmentSubmission[]>;
  getStudentSubmission(assignmentId: number, studentId: number): Promise<AssignmentSubmission | undefined>;
  createSubmission(submission: InsertSubmission): Promise<AssignmentSubmission>;
  updateSubmission(id: number, updates: Partial<InsertSubmission>): Promise<AssignmentSubmission | undefined>;
  gradeSubmission(id: number, grade: number, feedback: string, gradedBy: number): Promise<AssignmentSubmission | undefined>;

  // Course Materials
  getMaterials(courseId: number): Promise<CourseMaterial[]>;
  getMaterial(id: number): Promise<CourseMaterial | undefined>;
  createMaterial(material: InsertMaterial): Promise<CourseMaterial>;
  updateMaterial(id: number, updates: Partial<InsertMaterial>): Promise<CourseMaterial | undefined>;
  deleteMaterial(id: number): Promise<boolean>;

  // Messages
  getMessages(userId: number): Promise<Message[]>;
  getConversation(user1Id: number, user2Id: number): Promise<Message[]>;
  getCourseMessages(courseId: number): Promise<Message[]>;
  createMessage(message: InsertMessage): Promise<Message>;
  markMessageAsRead(id: number): Promise<Message | undefined>;

  // Notifications
  getNotifications(userId: number): Promise<Notification[]>;
  createNotification(notification: InsertNotification): Promise<Notification>;
  markNotificationAsRead(id: number): Promise<Notification | undefined>;
  markAllNotificationsAsRead(userId: number): Promise<boolean>;
}

export class MemStorage implements IStorage {
  private users: Map<number, User> = new Map();
  private courses: Map<number, Course> = new Map();
  private assignments: Map<number, Assignment> = new Map();
  private submissions: Map<number, AssignmentSubmission> = new Map();
  private materials: Map<number, CourseMaterial> = new Map();
  private messages: Map<number, Message> = new Map();
  private notifications: Map<number, Notification> = new Map();
  private enrollments: Map<number, CourseEnrollment> = new Map();
  private assistants: Map<number, CourseAssistant> = new Map();
  
  private currentId = 1;

  // Users
  async getUser(id: number): Promise<User | undefined> {
    return this.users.get(id);
  }

  async getUserByUsername(username: string): Promise<User | undefined> {
    return Array.from(this.users.values()).find(user => user.username === username);
  }

  async getUserByEmail(email: string): Promise<User | undefined> {
    return Array.from(this.users.values()).find(user => user.email === email);
  }

  async createUser(insertUser: InsertUser): Promise<User> {
    const id = this.currentId++;
    const user: User = {
      ...insertUser,
      id,
      createdAt: new Date(),
    };
    this.users.set(id, user);
    return user;
  }

  async updateUser(id: number, updates: Partial<InsertUser>): Promise<User | undefined> {
    const user = this.users.get(id);
    if (!user) return undefined;

    const updatedUser = { ...user, ...updates };
    this.users.set(id, updatedUser);
    return updatedUser;
  }

  // Courses
  async getCourses(): Promise<Course[]> {
    return Array.from(this.courses.values());
  }

  async getCoursesByInstructor(instructorId: number): Promise<Course[]> {
    return Array.from(this.courses.values()).filter(course => course.instructorId === instructorId);
  }

  async getCoursesByStudent(studentId: number): Promise<Course[]> {
    const enrollments = Array.from(this.enrollments.values()).filter(e => e.studentId === studentId);
    const courseIds = enrollments.map(e => e.courseId);
    return Array.from(this.courses.values()).filter(course => courseIds.includes(course.id));
  }

  async getCourse(id: number): Promise<Course | undefined> {
    return this.courses.get(id);
  }

  async createCourse(insertCourse: InsertCourse): Promise<Course> {
    const id = this.currentId++;
    const course: Course = {
      ...insertCourse,
      id,
      createdAt: new Date(),
    };
    this.courses.set(id, course);
    return course;
  }

  async updateCourse(id: number, updates: Partial<InsertCourse>): Promise<Course | undefined> {
    const course = this.courses.get(id);
    if (!course) return undefined;

    const updatedCourse = { ...course, ...updates };
    this.courses.set(id, updatedCourse);
    return updatedCourse;
  }

  async deleteCourse(id: number): Promise<boolean> {
    return this.courses.delete(id);
  }

  // Course Enrollments
  async enrollStudent(courseId: number, studentId: number): Promise<CourseEnrollment> {
    const id = this.currentId++;
    const enrollment: CourseEnrollment = {
      id,
      courseId,
      studentId,
      enrolledAt: new Date(),
      progress: 0,
    };
    this.enrollments.set(id, enrollment);
    return enrollment;
  }

  async unenrollStudent(courseId: number, studentId: number): Promise<boolean> {
    const enrollment = Array.from(this.enrollments.entries()).find(
      ([_, e]) => e.courseId === courseId && e.studentId === studentId
    );
    if (enrollment) {
      return this.enrollments.delete(enrollment[0]);
    }
    return false;
  }

  async getCourseEnrollments(courseId: number): Promise<CourseEnrollment[]> {
    return Array.from(this.enrollments.values()).filter(e => e.courseId === courseId);
  }

  async getStudentEnrollments(studentId: number): Promise<CourseEnrollment[]> {
    return Array.from(this.enrollments.values()).filter(e => e.studentId === studentId);
  }

  async updateEnrollmentProgress(courseId: number, studentId: number, progress: number): Promise<CourseEnrollment | undefined> {
    const enrollment = Array.from(this.enrollments.values()).find(
      e => e.courseId === courseId && e.studentId === studentId
    );
    if (!enrollment) return undefined;

    enrollment.progress = progress;
    this.enrollments.set(enrollment.id, enrollment);
    return enrollment;
  }

  // Course Assistants
  async assignAssistant(courseId: number, assistantId: number, permissions: any): Promise<CourseAssistant> {
    const id = this.currentId++;
    const assistant: CourseAssistant = {
      id,
      courseId,
      assistantId,
      permissions,
      assignedAt: new Date(),
    };
    this.assistants.set(id, assistant);
    return assistant;
  }

  async removeAssistant(courseId: number, assistantId: number): Promise<boolean> {
    const assistant = Array.from(this.assistants.entries()).find(
      ([_, a]) => a.courseId === courseId && a.assistantId === assistantId
    );
    if (assistant) {
      return this.assistants.delete(assistant[0]);
    }
    return false;
  }

  async getCourseAssistants(courseId: number): Promise<CourseAssistant[]> {
    return Array.from(this.assistants.values()).filter(a => a.courseId === courseId);
  }

  // Assignments
  async getAssignments(courseId: number): Promise<Assignment[]> {
    return Array.from(this.assignments.values()).filter(a => a.courseId === courseId);
  }

  async getAssignment(id: number): Promise<Assignment | undefined> {
    return this.assignments.get(id);
  }

  async createAssignment(insertAssignment: InsertAssignment): Promise<Assignment> {
    const id = this.currentId++;
    const assignment: Assignment = {
      ...insertAssignment,
      id,
      createdAt: new Date(),
    };
    this.assignments.set(id, assignment);
    return assignment;
  }

  async updateAssignment(id: number, updates: Partial<InsertAssignment>): Promise<Assignment | undefined> {
    const assignment = this.assignments.get(id);
    if (!assignment) return undefined;

    const updatedAssignment = { ...assignment, ...updates };
    this.assignments.set(id, updatedAssignment);
    return updatedAssignment;
  }

  async deleteAssignment(id: number): Promise<boolean> {
    return this.assignments.delete(id);
  }

  // Assignment Submissions
  async getSubmissions(assignmentId: number): Promise<AssignmentSubmission[]> {
    return Array.from(this.submissions.values()).filter(s => s.assignmentId === assignmentId);
  }

  async getStudentSubmission(assignmentId: number, studentId: number): Promise<AssignmentSubmission | undefined> {
    return Array.from(this.submissions.values()).find(
      s => s.assignmentId === assignmentId && s.studentId === studentId
    );
  }

  async createSubmission(insertSubmission: InsertSubmission): Promise<AssignmentSubmission> {
    const id = this.currentId++;
    const submission: AssignmentSubmission = {
      ...insertSubmission,
      id,
      submittedAt: new Date(),
      grade: null,
      feedback: null,
      gradedBy: null,
      gradedAt: null,
    };
    this.submissions.set(id, submission);
    return submission;
  }

  async updateSubmission(id: number, updates: Partial<InsertSubmission>): Promise<AssignmentSubmission | undefined> {
    const submission = this.submissions.get(id);
    if (!submission) return undefined;

    const updatedSubmission = { ...submission, ...updates };
    this.submissions.set(id, updatedSubmission);
    return updatedSubmission;
  }

  async gradeSubmission(id: number, grade: number, feedback: string, gradedBy: number): Promise<AssignmentSubmission | undefined> {
    const submission = this.submissions.get(id);
    if (!submission) return undefined;

    submission.grade = grade;
    submission.feedback = feedback;
    submission.gradedBy = gradedBy;
    submission.gradedAt = new Date();
    this.submissions.set(id, submission);
    return submission;
  }

  // Course Materials
  async getMaterials(courseId: number): Promise<CourseMaterial[]> {
    return Array.from(this.materials.values()).filter(m => m.courseId === courseId);
  }

  async getMaterial(id: number): Promise<CourseMaterial | undefined> {
    return this.materials.get(id);
  }

  async createMaterial(insertMaterial: InsertMaterial): Promise<CourseMaterial> {
    const id = this.currentId++;
    const material: CourseMaterial = {
      ...insertMaterial,
      id,
      uploadedAt: new Date(),
    };
    this.materials.set(id, material);
    return material;
  }

  async updateMaterial(id: number, updates: Partial<InsertMaterial>): Promise<CourseMaterial | undefined> {
    const material = this.materials.get(id);
    if (!material) return undefined;

    const updatedMaterial = { ...material, ...updates };
    this.materials.set(id, updatedMaterial);
    return updatedMaterial;
  }

  async deleteMaterial(id: number): Promise<boolean> {
    return this.materials.delete(id);
  }

  // Messages
  async getMessages(userId: number): Promise<Message[]> {
    return Array.from(this.messages.values()).filter(
      m => m.senderId === userId || m.receiverId === userId
    );
  }

  async getConversation(user1Id: number, user2Id: number): Promise<Message[]> {
    return Array.from(this.messages.values()).filter(
      m => (m.senderId === user1Id && m.receiverId === user2Id) ||
           (m.senderId === user2Id && m.receiverId === user1Id)
    ).sort((a, b) => a.sentAt!.getTime() - b.sentAt!.getTime());
  }

  async getCourseMessages(courseId: number): Promise<Message[]> {
    return Array.from(this.messages.values()).filter(m => m.courseId === courseId);
  }

  async createMessage(insertMessage: InsertMessage): Promise<Message> {
    const id = this.currentId++;
    const message: Message = {
      ...insertMessage,
      id,
      sentAt: new Date(),
    };
    this.messages.set(id, message);
    return message;
  }

  async markMessageAsRead(id: number): Promise<Message | undefined> {
    const message = this.messages.get(id);
    if (!message) return undefined;

    message.isRead = true;
    this.messages.set(id, message);
    return message;
  }

  // Notifications
  async getNotifications(userId: number): Promise<Notification[]> {
    return Array.from(this.notifications.values()).filter(n => n.userId === userId);
  }

  async createNotification(insertNotification: InsertNotification): Promise<Notification> {
    const id = this.currentId++;
    const notification: Notification = {
      ...insertNotification,
      id,
      createdAt: new Date(),
    };
    this.notifications.set(id, notification);
    return notification;
  }

  async markNotificationAsRead(id: number): Promise<Notification | undefined> {
    const notification = this.notifications.get(id);
    if (!notification) return undefined;

    notification.isRead = true;
    this.notifications.set(id, notification);
    return notification;
  }

  async markAllNotificationsAsRead(userId: number): Promise<boolean> {
    const userNotifications = Array.from(this.notifications.values()).filter(n => n.userId === userId);
    userNotifications.forEach(notification => {
      notification.isRead = true;
      this.notifications.set(notification.id, notification);
    });
    return true;
  }
}

export const storage = new MemStorage();
