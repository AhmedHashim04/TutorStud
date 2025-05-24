import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  ArrowLeft,
  Users, 
  Calendar, 
  Clock, 
  FileText,
  Video,
  Download,
  Plus,
  BookOpen,
  ClipboardList,
  Upload,
  Play,
  Eye,
  CheckCircle,
  XCircle,
  AlertCircle
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest } from "@/lib/queryClient";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { insertAssignmentSchema, insertMaterialSchema } from "@shared/schema";
import { z } from "zod";
import { formatDistanceToNow, format } from "date-fns";

interface CourseDetailProps {
  courseId: number;
}

const createAssignmentSchema = insertAssignmentSchema.extend({
  dueDate: z.string(),
});

const createMaterialSchema = insertMaterialSchema.omit({
  courseId: true,
  uploadedBy: true,
});

type CreateAssignmentData = z.infer<typeof createAssignmentSchema>;
type CreateMaterialData = z.infer<typeof createMaterialSchema>;

export default function CourseDetail({ courseId }: CourseDetailProps) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [, setLocation] = useLocation();
  const [activeTab, setActiveTab] = useState("overview");
  const [isAssignmentDialogOpen, setIsAssignmentDialogOpen] = useState(false);
  const [isMaterialDialogOpen, setIsMaterialDialogOpen] = useState(false);

  const { data: course, isLoading: isLoadingCourse } = useQuery({
    queryKey: ['/api/courses', courseId],
  });

  const { data: assignments, isLoading: isLoadingAssignments } = useQuery({
    queryKey: ['/api/courses', courseId, 'assignments'],
  });

  const { data: materials, isLoading: isLoadingMaterials } = useQuery({
    queryKey: ['/api/courses', courseId, 'materials'],
  });

  const { data: enrollments } = useQuery({
    queryKey: ['/api/courses', courseId, 'enrollments'],
  });

  const { data: userCourses } = useQuery({
    queryKey: ['/api/users', user?.id, 'courses'],
    enabled: !!user,
  });

  const createAssignmentMutation = useMutation({
    mutationFn: (assignmentData: CreateAssignmentData) => {
      const { dueDate, ...rest } = assignmentData;
      return apiRequest('POST', '/api/assignments', {
        ...rest,
        courseId,
        dueDate: new Date(dueDate).toISOString(),
        createdBy: user?.id,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/courses', courseId, 'assignments'] });
      setIsAssignmentDialogOpen(false);
      assignmentForm.reset();
    },
  });

  const createMaterialMutation = useMutation({
    mutationFn: (materialData: CreateMaterialData) =>
      apiRequest('POST', '/api/materials', {
        ...materialData,
        courseId,
        uploadedBy: user?.id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/courses', courseId, 'materials'] });
      setIsMaterialDialogOpen(false);
      materialForm.reset();
    },
  });

  const enrollMutation = useMutation({
    mutationFn: () =>
      apiRequest('POST', `/api/courses/${courseId}/enroll`, { studentId: user?.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/users', user?.id, 'courses'] });
      queryClient.invalidateQueries({ queryKey: ['/api/courses', courseId, 'enrollments'] });
    },
  });

  const unenrollMutation = useMutation({
    mutationFn: () =>
      apiRequest('DELETE', `/api/courses/${courseId}/enroll/${user?.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/users', user?.id, 'courses'] });
      queryClient.invalidateQueries({ queryKey: ['/api/courses', courseId, 'enrollments'] });
    },
  });

  const assignmentForm = useForm<CreateAssignmentData>({
    resolver: zodResolver(createAssignmentSchema),
    defaultValues: {
      title: "",
      description: "",
      maxPoints: 100,
      isActive: true,
    },
  });

  const materialForm = useForm<CreateMaterialData>({
    resolver: zodResolver(createMaterialSchema),
    defaultValues: {
      title: "",
      description: "",
      type: "document",
      url: "",
      isPublic: true,
      order: 0,
    },
  });

  const onSubmitAssignment = (data: CreateAssignmentData) => {
    createAssignmentMutation.mutate(data);
  };

  const onSubmitMaterial = (data: CreateMaterialData) => {
    createMaterialMutation.mutate(data);
  };

  const isEnrolled = userCourses?.some((c: any) => c.id === courseId);
  const isInstructor = user?.role === "instructor" && course?.instructorId === user?.id;
  const isAssistant = user?.role === "assistant"; // TODO: Check if assistant is assigned to this course

  const canManage = isInstructor || isAssistant;

  const getMaterialIcon = (type: string) => {
    switch (type) {
      case 'video':
        return Video;
      case 'pdf':
        return FileText;
      case 'presentation':
        return FileText;
      default:
        return FileText;
    }
  };

  const getMaterialColor = (type: string) => {
    switch (type) {
      case 'video':
        return 'text-blue-600 bg-blue-100';
      case 'pdf':
        return 'text-red-600 bg-red-100';
      case 'presentation':
        return 'text-green-600 bg-green-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getAssignmentStatus = (dueDate: string) => {
    const due = new Date(dueDate);
    const now = new Date();
    const timeDiff = due.getTime() - now.getTime();
    const daysDiff = Math.ceil(timeDiff / (1000 * 3600 * 24));

    if (daysDiff < 0) {
      return { status: 'overdue', color: 'text-red-600 bg-red-100', icon: XCircle };
    } else if (daysDiff === 0) {
      return { status: 'due-today', color: 'text-orange-600 bg-orange-100', icon: AlertCircle };
    } else if (daysDiff <= 3) {
      return { status: 'due-soon', color: 'text-yellow-600 bg-yellow-100', icon: Clock };
    } else {
      return { status: 'upcoming', color: 'text-green-600 bg-green-100', icon: CheckCircle };
    }
  };

  if (isLoadingCourse) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-4" />
          <div className="h-64 bg-gray-200 rounded" />
        </div>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="text-center py-12">
        <h3 className="text-lg font-medium text-gray-900">Course not found</h3>
        <p className="text-gray-500 mt-2">The course you're looking for doesn't exist.</p>
        <Button onClick={() => setLocation('/courses')} className="mt-4">
          Back to Courses
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="icon" onClick={() => setLocation('/courses')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-gray-900">{course.title}</h1>
          <p className="text-gray-600 mt-1">{course.description}</p>
        </div>
        
        {user?.role === "student" && (
          <div className="flex space-x-2">
            {isEnrolled ? (
              <Button 
                variant="outline"
                onClick={() => unenrollMutation.mutate()}
                disabled={unenrollMutation.isPending}
              >
                {unenrollMutation.isPending ? "Leaving..." : "Leave Course"}
              </Button>
            ) : (
              <Button 
                onClick={() => enrollMutation.mutate()}
                disabled={enrollMutation.isPending}
              >
                {enrollMutation.isPending ? "Enrolling..." : "Enroll Now"}
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Course Info Card */}
      <Card>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="md:col-span-1">
              <img 
                src={course.coverImage || `https://images.unsplash.com/photo-1516321318423-f06f85e504b3?ixlib=rb-4.0.3&auto=format&fit=crop&w=300&h=200`}
                alt={course.title}
                className="w-full h-48 md:h-full object-cover rounded-lg"
              />
            </div>
            <div className="md:col-span-3 space-y-4">
              <div className="flex items-center space-x-4">
                <Badge variant={course.isActive ? "default" : "secondary"}>
                  {course.isActive ? "Active" : "Inactive"}
                </Badge>
                {isEnrolled && (
                  <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                    Enrolled
                  </Badge>
                )}
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <Users className="h-4 w-4" />
                  <span>{enrollments?.length || 0} / {course.maxStudents || "∞"} students</span>
                </div>
                
                {course.startDate && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Calendar className="h-4 w-4" />
                    <span>Starts {format(new Date(course.startDate), 'MMM dd, yyyy')}</span>
                  </div>
                )}
                
                {course.endDate && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Clock className="h-4 w-4" />
                    <span>Ends {format(new Date(course.endDate), 'MMM dd, yyyy')}</span>
                  </div>
                )}
              </div>

              <p className="text-gray-700 leading-relaxed">{course.description}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="materials">Materials</TabsTrigger>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="students">Students</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Course Description</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-700 leading-relaxed">{course.description}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Recent Activity</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* Sample activity items */}
                    <div className="flex items-start space-x-3">
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-2" />
                      <div>
                        <p className="text-sm text-gray-900">New assignment posted: Final Project</p>
                        <p className="text-xs text-gray-500">2 hours ago</p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <div className="w-2 h-2 bg-green-500 rounded-full mt-2" />
                      <div>
                        <p className="text-sm text-gray-900">Course material uploaded: Lecture Notes</p>
                        <p className="text-xs text-gray-500">1 day ago</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Quick Stats</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Total Students</span>
                    <span className="font-semibold">{enrollments?.length || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Assignments</span>
                    <span className="font-semibold">{assignments?.length || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Materials</span>
                    <span className="font-semibold">{materials?.length || 0}</span>
                  </div>
                </CardContent>
              </Card>

              {canManage && (
                <Card>
                  <CardHeader>
                    <CardTitle>Quick Actions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Dialog open={isAssignmentDialogOpen} onOpenChange={setIsAssignmentDialogOpen}>
                      <DialogTrigger asChild>
                        <Button className="w-full justify-start">
                          <Plus className="mr-2 h-4 w-4" />
                          Create Assignment
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Create New Assignment</DialogTitle>
                          <DialogDescription>
                            Create a new assignment for this course.
                          </DialogDescription>
                        </DialogHeader>
                        <Form {...assignmentForm}>
                          <form onSubmit={assignmentForm.handleSubmit(onSubmitAssignment)} className="space-y-4">
                            <FormField
                              control={assignmentForm.control}
                              name="title"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Assignment Title</FormLabel>
                                  <FormControl>
                                    <Input placeholder="Enter assignment title" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={assignmentForm.control}
                              name="description"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Description</FormLabel>
                                  <FormControl>
                                    <Textarea 
                                      placeholder="Enter assignment description"
                                      className="min-h-[80px]"
                                      {...field} 
                                    />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <div className="grid grid-cols-2 gap-4">
                              <FormField
                                control={assignmentForm.control}
                                name="maxPoints"
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Max Points</FormLabel>
                                    <FormControl>
                                      <Input 
                                        type="number"
                                        placeholder="100"
                                        {...field}
                                        onChange={(e) => field.onChange(e.target.value ? parseInt(e.target.value) : undefined)}
                                      />
                                    </FormControl>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />

                              <FormField
                                control={assignmentForm.control}
                                name="dueDate"
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Due Date</FormLabel>
                                    <FormControl>
                                      <Input type="datetime-local" {...field} />
                                    </FormControl>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />
                            </div>

                            <DialogFooter>
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsAssignmentDialogOpen(false)}
                              >
                                Cancel
                              </Button>
                              <Button 
                                type="submit" 
                                disabled={createAssignmentMutation.isPending}
                              >
                                {createAssignmentMutation.isPending ? "Creating..." : "Create Assignment"}
                              </Button>
                            </DialogFooter>
                          </form>
                        </Form>
                      </DialogContent>
                    </Dialog>

                    <Dialog open={isMaterialDialogOpen} onOpenChange={setIsMaterialDialogOpen}>
                      <DialogTrigger asChild>
                        <Button variant="outline" className="w-full justify-start">
                          <Upload className="mr-2 h-4 w-4" />
                          Upload Material
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Upload Course Material</DialogTitle>
                          <DialogDescription>
                            Add new learning material to this course.
                          </DialogDescription>
                        </DialogHeader>
                        <Form {...materialForm}>
                          <form onSubmit={materialForm.handleSubmit(onSubmitMaterial)} className="space-y-4">
                            <FormField
                              control={materialForm.control}
                              name="title"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Material Title</FormLabel>
                                  <FormControl>
                                    <Input placeholder="Enter material title" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={materialForm.control}
                              name="description"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Description</FormLabel>
                                  <FormControl>
                                    <Textarea 
                                      placeholder="Enter material description"
                                      className="min-h-[60px]"
                                      {...field} 
                                    />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={materialForm.control}
                              name="type"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Material Type</FormLabel>
                                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                                    <FormControl>
                                      <SelectTrigger>
                                        <SelectValue placeholder="Select material type" />
                                      </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                      <SelectItem value="video">Video</SelectItem>
                                      <SelectItem value="pdf">PDF Document</SelectItem>
                                      <SelectItem value="presentation">Presentation</SelectItem>
                                      <SelectItem value="document">Document</SelectItem>
                                    </SelectContent>
                                  </Select>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={materialForm.control}
                              name="url"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Material URL</FormLabel>
                                  <FormControl>
                                    <Input placeholder="https://example.com/material" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <DialogFooter>
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsMaterialDialogOpen(false)}
                              >
                                Cancel
                              </Button>
                              <Button 
                                type="submit" 
                                disabled={createMaterialMutation.isPending}
                              >
                                {createMaterialMutation.isPending ? "Uploading..." : "Upload Material"}
                              </Button>
                            </DialogFooter>
                          </form>
                        </Form>
                      </DialogContent>
                    </Dialog>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="materials" className="mt-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Course Materials</h3>
              {canManage && (
                <Button onClick={() => setIsMaterialDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Material
                </Button>
              )}
            </div>

            {isLoadingMaterials ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[...Array(3)].map((_, i) => (
                  <Card key={i} className="animate-pulse">
                    <div className="aspect-video bg-gray-200" />
                    <CardContent className="p-4">
                      <div className="space-y-2">
                        <div className="h-4 bg-gray-200 rounded" />
                        <div className="h-3 bg-gray-200 rounded w-2/3" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : materials?.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900">No materials yet</h3>
                <p className="mt-2 text-gray-500">Course materials will appear here once uploaded.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {materials?.map((material: any) => {
                  const IconComponent = getMaterialIcon(material.type);
                  return (
                    <Card key={material.id} className="hover:shadow-md transition-shadow">
                      <div className="aspect-video bg-gray-100 flex items-center justify-center">
                        <IconComponent className="h-12 w-12 text-gray-400" />
                      </div>
                      <CardContent className="p-4">
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <Badge variant="secondary" className={`text-xs ${getMaterialColor(material.type)}`}>
                              {material.type.toUpperCase()}
                            </Badge>
                            {material.duration && (
                              <span className="text-xs text-gray-500">{material.duration} min</span>
                            )}
                          </div>
                          <h4 className="font-medium text-gray-900 line-clamp-2">{material.title}</h4>
                          {material.description && (
                            <p className="text-sm text-gray-600 line-clamp-2">{material.description}</p>
                          )}
                          <Button 
                            className="w-full"
                            size="sm"
                            onClick={() => window.open(material.url, '_blank')}
                          >
                            {material.type === 'video' ? (
                              <>
                                <Play className="mr-2 h-4 w-4" />
                                Watch Now
                              </>
                            ) : (
                              <>
                                <Eye className="mr-2 h-4 w-4" />
                                View Material
                              </>
                            )}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="assignments" className="mt-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Assignments</h3>
              {canManage && (
                <Button onClick={() => setIsAssignmentDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Assignment
                </Button>
              )}
            </div>

            {isLoadingAssignments ? (
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <Card key={i} className="animate-pulse">
                    <CardContent className="p-6">
                      <div className="space-y-3">
                        <div className="h-4 bg-gray-200 rounded w-1/3" />
                        <div className="h-3 bg-gray-200 rounded" />
                        <div className="h-3 bg-gray-200 rounded w-2/3" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : assignments?.length === 0 ? (
              <div className="text-center py-12">
                <ClipboardList className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900">No assignments yet</h3>
                <p className="mt-2 text-gray-500">Assignments will appear here once created.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {assignments?.map((assignment: any) => {
                  const { status, color, icon: StatusIcon } = getAssignmentStatus(assignment.dueDate);
                  return (
                    <Card key={assignment.id} className="hover:shadow-md transition-shadow">
                      <CardContent className="p-6">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-3 mb-2">
                              <h4 className="font-semibold text-gray-900">{assignment.title}</h4>
                              <Badge variant="outline" className={`text-xs ${color}`}>
                                <StatusIcon className="mr-1 h-3 w-3" />
                                Due {formatDistanceToNow(new Date(assignment.dueDate), { addSuffix: true })}
                              </Badge>
                            </div>
                            <p className="text-sm text-gray-600 mb-3">{assignment.description}</p>
                            <div className="flex items-center space-x-4 text-sm text-gray-500">
                              <span>Max Points: {assignment.maxPoints}</span>
                              <span>Due: {format(new Date(assignment.dueDate), 'MMM dd, yyyy HH:mm')}</span>
                            </div>
                          </div>
                          <div className="flex space-x-2">
                            <Button variant="outline" size="sm">
                              View Details
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="students" className="mt-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Enrolled Students</h3>
              <div className="text-sm text-gray-500">
                {enrollments?.length || 0} {enrollments?.length === 1 ? 'student' : 'students'} enrolled
              </div>
            </div>

            {enrollments?.length === 0 ? (
              <div className="text-center py-12">
                <Users className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900">No students enrolled</h3>
                <p className="mt-2 text-gray-500">Students will appear here once they enroll in the course.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {enrollments?.map((enrollment: any, index: number) => (
                  <Card key={enrollment.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-12 h-12 bg-gradient-to-r from-primary to-secondary rounded-full flex items-center justify-center text-white font-semibold">
                          S{index + 1}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">Student {enrollment.studentId}</h4>
                          <p className="text-sm text-gray-500">
                            Enrolled {formatDistanceToNow(new Date(enrollment.enrolledAt), { addSuffix: true })}
                          </p>
                          <div className="mt-2">
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span>Progress</span>
                              <span>{enrollment.progress}%</span>
                            </div>
                            <Progress value={enrollment.progress} className="h-2" />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
