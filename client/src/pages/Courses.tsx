import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Search, 
  Plus, 
  BookOpen, 
  Users, 
  Clock, 
  Calendar,
  Filter,
  Grid3X3,
  List,
  Star,
  MapPin
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest } from "@/lib/queryClient";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { insertCourseSchema } from "@shared/schema";
import { z } from "zod";
import { formatDistanceToNow } from "date-fns";

const createCourseSchema = insertCourseSchema.extend({
  enrollmentStart: z.string().optional(),
  enrollmentEnd: z.string().optional(),
  startDate: z.string().optional(),
  endDate: z.string().optional(),
});

type CreateCourseData = z.infer<typeof createCourseSchema>;

export default function Courses() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [activeTab, setActiveTab] = useState("enrolled");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  const { data: allCourses, isLoading: isLoadingAll } = useQuery({
    queryKey: ['/api/courses'],
  });

  const { data: enrolledCourses, isLoading: isLoadingEnrolled } = useQuery({
    queryKey: ['/api/users', user?.id, 'courses'],
    enabled: !!user,
  });

  const { data: enrollments } = useQuery({
    queryKey: ['/api/users', user?.id, 'enrollments'],
    enabled: !!user,
  });

  const createCourseMutation = useMutation({
    mutationFn: (courseData: CreateCourseData) => {
      const { enrollmentStart, enrollmentEnd, startDate, endDate, ...rest } = courseData;
      return apiRequest('POST', '/api/courses', {
        ...rest,
        enrollmentStart: enrollmentStart ? new Date(enrollmentStart).toISOString() : null,
        enrollmentEnd: enrollmentEnd ? new Date(enrollmentEnd).toISOString() : null,
        startDate: startDate ? new Date(startDate).toISOString() : null,
        endDate: endDate ? new Date(endDate).toISOString() : null,
        instructorId: user?.id,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/courses'] });
      setIsCreateDialogOpen(false);
      form.reset();
    },
  });

  const enrollMutation = useMutation({
    mutationFn: (courseId: number) =>
      apiRequest('POST', `/api/courses/${courseId}/enroll`, { studentId: user?.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/users', user?.id, 'courses'] });
      queryClient.invalidateQueries({ queryKey: ['/api/users', user?.id, 'enrollments'] });
    },
  });

  const form = useForm<CreateCourseData>({
    resolver: zodResolver(createCourseSchema),
    defaultValues: {
      title: "",
      description: "",
      maxStudents: 30,
      isActive: true,
    },
  });

  const onSubmit = (data: CreateCourseData) => {
    createCourseMutation.mutate(data);
  };

  const filteredCourses = (courses: any[]) => {
    if (!courses) return [];
    return courses.filter(course =>
      course.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      course.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  };

  const availableCourses = allCourses?.filter((course: any) => {
    const isEnrolled = enrolledCourses?.some((enrolled: any) => enrolled.id === course.id);
    return !isEnrolled && course.isActive;
  }) || [];

  const isEnrolled = (courseId: number) => {
    return enrolledCourses?.some((course: any) => course.id === courseId);
  };

  const getEnrollmentProgress = (courseId: number) => {
    const enrollment = enrollments?.find((e: any) => e.courseId === courseId);
    return enrollment?.progress || 0;
  };

  const CourseCard = ({ course, showEnrollButton = false }: { course: any; showEnrollButton?: boolean }) => (
    <Card className="hover:shadow-md transition-shadow overflow-hidden">
      <div className="aspect-video w-full overflow-hidden">
        <img 
          src={course.coverImage || `https://images.unsplash.com/photo-1516321318423-f06f85e504b3?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=200`}
          alt={course.title}
          className="w-full h-full object-cover"
        />
      </div>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-lg line-clamp-2">{course.title}</CardTitle>
          <Badge variant={course.isActive ? "default" : "secondary"}>
            {course.isActive ? "Active" : "Inactive"}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground line-clamp-2">{course.description}</p>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center space-x-1">
              <Users className="h-4 w-4" />
              <span>{course.maxStudents || "Unlimited"} students</span>
            </div>
            <div className="flex items-center space-x-1">
              <Calendar className="h-4 w-4" />
              <span>
                {course.startDate 
                  ? formatDistanceToNow(new Date(course.startDate), { addSuffix: true })
                  : "No start date"
                }
              </span>
            </div>
          </div>

          {isEnrolled(course.id) && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Progress</span>
                <span>{getEnrollmentProgress(course.id)}%</span>
              </div>
              <Progress value={getEnrollmentProgress(course.id)} className="h-2" />
            </div>
          )}

          <div className="flex gap-2">
            <Button asChild variant="outline" className="flex-1">
              <Link href={`/courses/${course.id}`}>View Details</Link>
            </Button>
            {showEnrollButton && !isEnrolled(course.id) && (
              <Button 
                onClick={() => enrollMutation.mutate(course.id)}
                disabled={enrollMutation.isPending}
                className="flex-1"
              >
                {enrollMutation.isPending ? "Enrolling..." : "Enroll"}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const CourseListItem = ({ course, showEnrollButton = false }: { course: any; showEnrollButton?: boolean }) => (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-center space-x-4">
          <img 
            src={course.coverImage || `https://images.unsplash.com/photo-1516321318423-f06f85e504b3?ixlib=rb-4.0.3&auto=format&fit=crop&w=80&h=80`}
            alt={course.title}
            className="w-20 h-20 rounded-lg object-cover"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold truncate">{course.title}</h3>
              <Badge variant={course.isActive ? "default" : "secondary"}>
                {course.isActive ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{course.description}</p>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                <div className="flex items-center space-x-1">
                  <Users className="h-4 w-4" />
                  <span>{course.maxStudents || "Unlimited"}</span>
                </div>
                <div className="flex items-center space-x-1">
                  <Calendar className="h-4 w-4" />
                  <span>
                    {course.startDate 
                      ? formatDistanceToNow(new Date(course.startDate), { addSuffix: true })
                      : "No start date"
                    }
                  </span>
                </div>
              </div>
              
              <div className="flex gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link href={`/courses/${course.id}`}>View Details</Link>
                </Button>
                {showEnrollButton && !isEnrolled(course.id) && (
                  <Button 
                    onClick={() => enrollMutation.mutate(course.id)}
                    disabled={enrollMutation.isPending}
                    size="sm"
                  >
                    {enrollMutation.isPending ? "Enrolling..." : "Enroll"}
                  </Button>
                )}
              </div>
            </div>

            {isEnrolled(course.id) && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Progress</span>
                  <span>{getEnrollmentProgress(course.id)}%</span>
                </div>
                <Progress value={getEnrollmentProgress(course.id)} className="h-2" />
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("myCourses")}</h1>
          <p className="text-gray-600 mt-1">Manage and explore your learning journey</p>
        </div>
        
        {(user?.role === "instructor" || user?.role === "assistant") && (
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button className="flex items-center space-x-2">
                <Plus className="h-4 w-4" />
                <span>{t("createCourse")}</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create New Course</DialogTitle>
                <DialogDescription>
                  Fill in the details to create a new course.
                </DialogDescription>
              </DialogHeader>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                  <FormField
                    control={form.control}
                    name="title"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Course Title</FormLabel>
                        <FormControl>
                          <Input placeholder="Enter course title" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <Textarea 
                            placeholder="Enter course description"
                            className="min-h-[80px]"
                            {...field} 
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="maxStudents"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Max Students</FormLabel>
                        <FormControl>
                          <Input 
                            type="number"
                            placeholder="30"
                            {...field}
                            onChange={(e) => field.onChange(e.target.value ? parseInt(e.target.value) : undefined)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="startDate"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Start Date</FormLabel>
                          <FormControl>
                            <Input type="date" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="endDate"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>End Date</FormLabel>
                          <FormControl>
                            <Input type="date" {...field} />
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
                      onClick={() => setIsCreateDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button 
                      type="submit" 
                      disabled={createCourseMutation.isPending}
                    >
                      {createCourseMutation.isPending ? "Creating..." : "Create Course"}
                    </Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Search and Filters */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder="Search courses..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant={viewMode === "grid" ? "default" : "outline"}
            size="icon"
            onClick={() => setViewMode("grid")}
          >
            <Grid3X3 className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === "list" ? "default" : "outline"}
            size="icon"
            onClick={() => setViewMode("list")}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="enrolled">My Courses</TabsTrigger>
          <TabsTrigger value="available">Available Courses</TabsTrigger>
        </TabsList>

        <TabsContent value="enrolled" className="mt-6">
          {isLoadingEnrolled ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <div className="aspect-video bg-gray-200" />
                  <CardContent className="p-6">
                    <div className="space-y-3">
                      <div className="h-4 bg-gray-200 rounded" />
                      <div className="h-3 bg-gray-200 rounded w-2/3" />
                      <div className="h-8 bg-gray-200 rounded" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : enrolledCourses?.length === 0 ? (
            <div className="text-center py-12">
              <BookOpen className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">No enrolled courses</h3>
              <p className="mt-2 text-gray-500">Start your learning journey by enrolling in available courses.</p>
              <Button 
                className="mt-4"
                onClick={() => setActiveTab("available")}
              >
                Browse Available Courses
              </Button>
            </div>
          ) : (
            <div className={viewMode === "grid" 
              ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
              : "space-y-4"
            }>
              {filteredCourses(enrolledCourses).map((course: any) => 
                viewMode === "grid" 
                  ? <CourseCard key={course.id} course={course} />
                  : <CourseListItem key={course.id} course={course} />
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="available" className="mt-6">
          {isLoadingAll ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <div className="aspect-video bg-gray-200" />
                  <CardContent className="p-6">
                    <div className="space-y-3">
                      <div className="h-4 bg-gray-200 rounded" />
                      <div className="h-3 bg-gray-200 rounded w-2/3" />
                      <div className="h-8 bg-gray-200 rounded" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : availableCourses.length === 0 ? (
            <div className="text-center py-12">
              <BookOpen className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">No available courses</h3>
              <p className="mt-2 text-gray-500">Check back later for new courses or contact your administrator.</p>
            </div>
          ) : (
            <div className={viewMode === "grid" 
              ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
              : "space-y-4"
            }>
              {filteredCourses(availableCourses).map((course: any) => 
                viewMode === "grid" 
                  ? <CourseCard key={course.id} course={course} showEnrollButton />
                  : <CourseListItem key={course.id} course={course} showEnrollButton />
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
