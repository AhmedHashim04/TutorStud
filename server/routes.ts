import type { Express } from "express";
import { createServer, type Server } from "http";
import { WebSocketServer, WebSocket } from "ws";
import { storage } from "./storage";
import { insertUserSchema, insertCourseSchema, insertAssignmentSchema, insertSubmissionSchema, insertMaterialSchema, insertMessageSchema, insertNotificationSchema } from "@shared/schema";

export async function registerRoutes(app: Express): Promise<Server> {
  const httpServer = createServer(app);

  // WebSocket setup for real-time features
  const wss = new WebSocketServer({ server: httpServer, path: '/ws' });
  const clients = new Map<number, WebSocket>();

  wss.on('connection', (ws, req) => {
    let userId: number | null = null;

    ws.on('message', async (data) => {
      try {
        const message = JSON.parse(data.toString());
        
        if (message.type === 'auth') {
          userId = message.userId;
          clients.set(userId, ws);
          ws.send(JSON.stringify({ type: 'auth_success' }));
        }
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    });

    ws.on('close', () => {
      if (userId) {
        clients.delete(userId);
      }
    });
  });

  // Broadcast notification to specific user
  const notifyUser = (userId: number, data: any) => {
    const client = clients.get(userId);
    if (client && client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  };

  // Auth routes
  app.post("/api/auth/register", async (req, res) => {
    try {
      const userData = insertUserSchema.parse(req.body);
      
      // Check if user exists
      const existingUser = await storage.getUserByEmail(userData.email);
      if (existingUser) {
        return res.status(400).json({ message: "User already exists" });
      }

      const user = await storage.createUser(userData);
      const { password, ...userWithoutPassword } = user;
      res.json(userWithoutPassword);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/auth/login", async (req, res) => {
    try {
      const { email, password } = req.body;
      const user = await storage.getUserByEmail(email);
      
      if (!user || user.password !== password) {
        return res.status(401).json({ message: "Invalid credentials" });
      }

      const { password: _, ...userWithoutPassword } = user;
      res.json(userWithoutPassword);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // User routes
  app.get("/api/users/:id", async (req, res) => {
    try {
      const user = await storage.getUser(parseInt(req.params.id));
      if (!user) {
        return res.status(404).json({ message: "User not found" });
      }
      const { password, ...userWithoutPassword } = user;
      res.json(userWithoutPassword);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.put("/api/users/:id", async (req, res) => {
    try {
      const updates = insertUserSchema.partial().parse(req.body);
      const user = await storage.updateUser(parseInt(req.params.id), updates);
      if (!user) {
        return res.status(404).json({ message: "User not found" });
      }
      const { password, ...userWithoutPassword } = user;
      res.json(userWithoutPassword);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Course routes
  app.get("/api/courses", async (req, res) => {
    try {
      const courses = await storage.getCourses();
      res.json(courses);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/courses/:id", async (req, res) => {
    try {
      const course = await storage.getCourse(parseInt(req.params.id));
      if (!course) {
        return res.status(404).json({ message: "Course not found" });
      }
      res.json(course);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/courses", async (req, res) => {
    try {
      const courseData = insertCourseSchema.parse(req.body);
      const course = await storage.createCourse(courseData);
      res.json(course);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.put("/api/courses/:id", async (req, res) => {
    try {
      const updates = insertCourseSchema.partial().parse(req.body);
      const course = await storage.updateCourse(parseInt(req.params.id), updates);
      if (!course) {
        return res.status(404).json({ message: "Course not found" });
      }
      res.json(course);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.delete("/api/courses/:id", async (req, res) => {
    try {
      const deleted = await storage.deleteCourse(parseInt(req.params.id));
      if (!deleted) {
        return res.status(404).json({ message: "Course not found" });
      }
      res.json({ message: "Course deleted" });
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Course enrollment routes
  app.post("/api/courses/:courseId/enroll", async (req, res) => {
    try {
      const { studentId } = req.body;
      const enrollment = await storage.enrollStudent(parseInt(req.params.courseId), studentId);
      
      // Notify student
      await storage.createNotification({
        userId: studentId,
        title: "Course Enrollment",
        message: "You have successfully enrolled in a new course",
        type: "course",
        relatedId: parseInt(req.params.courseId),
        isRead: false
      });
      
      notifyUser(studentId, {
        type: 'notification',
        data: { title: 'Course Enrollment', message: 'You have successfully enrolled in a new course' }
      });

      res.json(enrollment);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.delete("/api/courses/:courseId/enroll/:studentId", async (req, res) => {
    try {
      const deleted = await storage.unenrollStudent(
        parseInt(req.params.courseId),
        parseInt(req.params.studentId)
      );
      if (!deleted) {
        return res.status(404).json({ message: "Enrollment not found" });
      }
      res.json({ message: "Unenrolled successfully" });
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/users/:id/courses", async (req, res) => {
    try {
      const courses = await storage.getCoursesByStudent(parseInt(req.params.id));
      res.json(courses);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Assignment routes
  app.get("/api/courses/:courseId/assignments", async (req, res) => {
    try {
      const assignments = await storage.getAssignments(parseInt(req.params.courseId));
      res.json(assignments);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/assignments/:id", async (req, res) => {
    try {
      const assignment = await storage.getAssignment(parseInt(req.params.id));
      if (!assignment) {
        return res.status(404).json({ message: "Assignment not found" });
      }
      res.json(assignment);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/assignments", async (req, res) => {
    try {
      const assignmentData = insertAssignmentSchema.parse(req.body);
      const assignment = await storage.createAssignment(assignmentData);
      
      // Notify enrolled students
      const enrollments = await storage.getCourseEnrollments(assignment.courseId);
      for (const enrollment of enrollments) {
        await storage.createNotification({
          userId: enrollment.studentId,
          title: "New Assignment",
          message: `A new assignment "${assignment.title}" has been posted`,
          type: "assignment",
          relatedId: assignment.id,
          isRead: false
        });
        
        notifyUser(enrollment.studentId, {
          type: 'notification',
          data: { title: 'New Assignment', message: `A new assignment "${assignment.title}" has been posted` }
        });
      }

      res.json(assignment);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Assignment submission routes
  app.get("/api/assignments/:assignmentId/submissions", async (req, res) => {
    try {
      const submissions = await storage.getSubmissions(parseInt(req.params.assignmentId));
      res.json(submissions);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/submissions", async (req, res) => {
    try {
      const submissionData = insertSubmissionSchema.parse(req.body);
      const submission = await storage.createSubmission(submissionData);
      
      // Notify instructor
      const assignment = await storage.getAssignment(submission.assignmentId);
      if (assignment) {
        const course = await storage.getCourse(assignment.courseId);
        if (course) {
          await storage.createNotification({
            userId: course.instructorId,
            title: "New Submission",
            message: `A student has submitted an assignment: ${assignment.title}`,
            type: "assignment",
            relatedId: assignment.id,
            isRead: false
          });
          
          notifyUser(course.instructorId, {
            type: 'notification',
            data: { title: 'New Submission', message: `A student has submitted an assignment: ${assignment.title}` }
          });
        }
      }

      res.json(submission);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.put("/api/submissions/:id/grade", async (req, res) => {
    try {
      const { grade, feedback, gradedBy } = req.body;
      const submission = await storage.gradeSubmission(
        parseInt(req.params.id),
        grade,
        feedback,
        gradedBy
      );
      
      if (!submission) {
        return res.status(404).json({ message: "Submission not found" });
      }

      // Notify student about grade
      await storage.createNotification({
        userId: submission.studentId,
        title: "Assignment Graded",
        message: `Your assignment has been graded: ${grade}/${100}`,
        type: "grade",
        relatedId: submission.assignmentId,
        isRead: false
      });
      
      notifyUser(submission.studentId, {
        type: 'notification',
        data: { title: 'Assignment Graded', message: `Your assignment has been graded: ${grade}/100` }
      });

      res.json(submission);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Course materials routes
  app.get("/api/courses/:courseId/materials", async (req, res) => {
    try {
      const materials = await storage.getMaterials(parseInt(req.params.courseId));
      res.json(materials);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/materials", async (req, res) => {
    try {
      const materialData = insertMaterialSchema.parse(req.body);
      const material = await storage.createMaterial(materialData);
      
      // Notify enrolled students
      const enrollments = await storage.getCourseEnrollments(material.courseId);
      for (const enrollment of enrollments) {
        await storage.createNotification({
          userId: enrollment.studentId,
          title: "New Course Material",
          message: `New material "${material.title}" has been uploaded`,
          type: "course",
          relatedId: material.courseId,
          isRead: false
        });
        
        notifyUser(enrollment.studentId, {
          type: 'notification',
          data: { title: 'New Course Material', message: `New material "${material.title}" has been uploaded` }
        });
      }

      res.json(material);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Message routes
  app.get("/api/users/:userId/messages", async (req, res) => {
    try {
      const messages = await storage.getMessages(parseInt(req.params.userId));
      res.json(messages);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/conversations/:user1Id/:user2Id", async (req, res) => {
    try {
      const conversation = await storage.getConversation(
        parseInt(req.params.user1Id),
        parseInt(req.params.user2Id)
      );
      res.json(conversation);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/messages", async (req, res) => {
    try {
      const messageData = insertMessageSchema.parse(req.body);
      const message = await storage.createMessage(messageData);
      
      // Notify recipient via WebSocket
      if (message.receiverId) {
        notifyUser(message.receiverId, {
          type: 'message',
          data: message
        });
        
        // Create notification
        await storage.createNotification({
          userId: message.receiverId,
          title: "New Message",
          message: "You have received a new message",
          type: "message",
          relatedId: message.id,
          isRead: false
        });
      }

      res.json(message);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  // Notification routes
  app.get("/api/users/:userId/notifications", async (req, res) => {
    try {
      const notifications = await storage.getNotifications(parseInt(req.params.userId));
      res.json(notifications.sort((a, b) => b.createdAt!.getTime() - a.createdAt!.getTime()));
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.put("/api/notifications/:id/read", async (req, res) => {
    try {
      const notification = await storage.markNotificationAsRead(parseInt(req.params.id));
      if (!notification) {
        return res.status(404).json({ message: "Notification not found" });
      }
      res.json(notification);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.put("/api/users/:userId/notifications/read-all", async (req, res) => {
    try {
      await storage.markAllNotificationsAsRead(parseInt(req.params.userId));
      res.json({ message: "All notifications marked as read" });
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  return httpServer;
}
