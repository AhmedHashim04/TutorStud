import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { 
  Search, 
  Calendar, 
  Clock, 
  FileText,
  Upload,
  CheckCircle,
  XCircle,
  AlertCircle,
  Eye,
  Edit,
  Download,
  Plus
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest } from "@/lib/queryClient";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { insertSubmissionSchema } from "@shared/schema";
import { z } from "zod";
import { formatDistanceToNow, format, isAfter, isBefore, addDays } from "date-fns";

const submitAssignmentSchema = insertSubmissionSchema.omit({
  studentId: true,
});

type SubmitAssignmentData = z.infer<typeof submitAssignmentSchema>;

export default function Assignments() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState("pending");
  const [selectedAssignment, setSelectedAssignment] = useState<any>(null);
  const [isSubmitDialogOpen, setIsSubmitDialogOpen] = useState(false);

  const { data: userCourses } = useQuery({
    queryKey: ['/api/users', user?.id, 'courses'],
    enabled: !!user,
  });

  // Get assignments for all enrolled courses
  const courseIds = userCourses?.map((course: any) => course.id) || [];
  const assignmentQueries = courseIds.map(courseId =>
    useQuery({
      queryKey: ['/api/courses', courseId, 'assignments'],
      enabled: courseIds.length > 0,
    })
  );

  // Get all submissions for the user
  const { data: submissions } = useQuery({
    queryKey: ['/api/users', user?.id, 'submissions'],
    enabled: !!user,
  });

  const submitAssignmentMutation = useMutation({
    mutationFn: (submissionData: SubmitAssignmentData) =>
      apiRequest('POST', '/api/submissions', {
        ...submissionData,
        studentId: user?.id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/users', user?.id, 'submissions'] });
      setIsSubmitDialogOpen(false);
      form.reset();
      setSelectedAssignment(null);
    },
  });

  const form = useForm<SubmitAssignmentData>({
    resolver: zodResolver(submitAssignmentSchema),
    defaultValues: {
      content: "",
      attachments: [],
    },
  });

  const onSubmit = (data: SubmitAssignmentData) => {
    if (!selectedAssignment) return;
    submitAssignmentMutation.mutate({
      ...data,
      assignmentId: selectedAssignment.id,
    });
  };

  // Flatten all assignments from all courses
  const allAssignments = assignmentQueries
    .flatMap(query => query.data || [])
    .map((assignment: any) => {
      const course = userCourses?.find((c: any) => c.id === assignment.courseId);
      return { ...assignment, courseName: course?.title || 'Unknown Course' };
    });

  const filteredAssignments = allAssignments.filter(assignment =>
    assignment.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    assignment.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    assignment.courseName.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getAssignmentStatus = (assignment: any, submission?: any) => {
    const dueDate = new Date(assignment.dueDate);
    const now = new Date();

    if (submission) {
      if (submission.grade !== null && submission.grade !== undefined) {
        return {
          status: 'graded',
          label: `Graded (${submission.grade}/${assignment.maxPoints})`,
          color: 'text-green-600 bg-green-100',
          icon: CheckCircle
        };
      } else {
        return {
          status: 'submitted',
          label: 'Submitted',
          color: 'text-blue-600 bg-blue-100',
          icon: CheckCircle
        };
      }
    }

    if (isAfter(now, dueDate)) {
      return {
        status: 'overdue',
        label: 'Overdue',
        color: 'text-red-600 bg-red-100',
        icon: XCircle
      };
    }

    if (isBefore(now, addDays(dueDate, -1))) {
      return {
        status: 'upcoming',
        label: `Due ${formatDistanceToNow(dueDate, { addSuffix: true })}`,
        color: 'text-gray-600 bg-gray-100',
        icon: Clock
      };
    }

    return {
      status: 'due-soon',
      label: `Due ${formatDistanceToNow(dueDate, { addSuffix: true })}`,
      color: 'text-orange-600 bg-orange-100',
      icon: AlertCircle
    };
  };

  const getSubmissionForAssignment = (assignmentId: number) => {
    return submissions?.find((sub: any) => sub.assignmentId === assignmentId);
  };

  const pendingAssignments = filteredAssignments.filter(assignment => {
    const submission = getSubmissionForAssignment(assignment.id);
    return !submission && isBefore(new Date(), new Date(assignment.dueDate));
  });

  const submittedAssignments = filteredAssignments.filter(assignment => {
    const submission = getSubmissionForAssignment(assignment.id);
    return submission;
  });

  const overdueAssignments = filteredAssignments.filter(assignment => {
    const submission = getSubmissionForAssignment(assignment.id);
    return !submission && isAfter(new Date(), new Date(assignment.dueDate));
  });

  const AssignmentCard = ({ assignment }: { assignment: any }) => {
    const submission = getSubmissionForAssignment(assignment.id);
    const { status, label, color, icon: StatusIcon } = getAssignmentStatus(assignment, submission);

    return (
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <CardTitle className="text-lg line-clamp-2">{assignment.title}</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">{assignment.courseName}</p>
            </div>
            <Badge variant="outline" className={`text-xs ${color} ml-2`}>
              <StatusIcon className="mr-1 h-3 w-3" />
              {label}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="space-y-4">
            <p className="text-sm text-gray-600 line-clamp-3">{assignment.description}</p>
            
            <div className="flex items-center justify-between text-sm text-gray-500">
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-1">
                  <Calendar className="h-4 w-4" />
                  <span>Due: {format(new Date(assignment.dueDate), 'MMM dd, yyyy HH:mm')}</span>
                </div>
                <div className="flex items-center space-x-1">
                  <FileText className="h-4 w-4" />
                  <span>{assignment.maxPoints} points</span>
                </div>
              </div>
            </div>

            {submission && (
              <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Your Submission</span>
                  <span className="text-gray-500">
                    {formatDistanceToNow(new Date(submission.submittedAt), { addSuffix: true })}
                  </span>
                </div>
                {submission.grade !== null && submission.grade !== undefined && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Grade:</span>
                    <Badge variant="outline" className="text-green-600 border-green-200 bg-green-50">
                      {submission.grade}/{assignment.maxPoints}
                    </Badge>
                  </div>
                )}
                {submission.feedback && (
                  <div className="text-sm text-gray-600">
                    <p className="font-medium">Feedback:</p>
                    <p className="mt-1">{submission.feedback}</p>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="flex-1">
                <Eye className="mr-2 h-4 w-4" />
                View Details
              </Button>
              {!submission && isBefore(new Date(), new Date(assignment.dueDate)) && (
                <Button 
                  size="sm" 
                  className="flex-1"
                  onClick={() => {
                    setSelectedAssignment(assignment);
                    setIsSubmitDialogOpen(true);
                  }}
                >
                  <Upload className="mr-2 h-4 w-4" />
                  Submit
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const isLoading = assignmentQueries.some(query => query.isLoading);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("assignments")}</h1>
          <p className="text-gray-600 mt-1">Track your assignments and submissions</p>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center space-x-4">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder="Search assignments..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="pending">
            Pending ({pendingAssignments.length})
          </TabsTrigger>
          <TabsTrigger value="submitted">
            Submitted ({submittedAssignments.length})
          </TabsTrigger>
          <TabsTrigger value="overdue">
            Overdue ({overdueAssignments.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-6">
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <Card key={i} className="animate-pulse">
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
          ) : pendingAssignments.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">All caught up!</h3>
              <p className="mt-2 text-gray-500">You have no pending assignments at the moment.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {pendingAssignments.map((assignment: any) => (
                <AssignmentCard key={assignment.id} assignment={assignment} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="submitted" className="mt-6">
          {submittedAssignments.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">No submissions yet</h3>
              <p className="mt-2 text-gray-500">Your submitted assignments will appear here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {submittedAssignments.map((assignment: any) => (
                <AssignmentCard key={assignment.id} assignment={assignment} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="overdue" className="mt-6">
          {overdueAssignments.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle className="mx-auto h-12 w-12 text-green-500" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">Great job!</h3>
              <p className="mt-2 text-gray-500">You have no overdue assignments.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {overdueAssignments.map((assignment: any) => (
                <AssignmentCard key={assignment.id} assignment={assignment} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Submit Assignment Dialog */}
      <Dialog open={isSubmitDialogOpen} onOpenChange={setIsSubmitDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Submit Assignment</DialogTitle>
            <DialogDescription>
              Submit your work for "{selectedAssignment?.title}"
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Submission Content</FormLabel>
                    <FormControl>
                      <Textarea 
                        placeholder="Enter your submission content, answers, or explanations..."
                        className="min-h-[120px]"
                        {...field} 
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="space-y-2">
                <Label>Attachments (Optional)</Label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <Upload className="mx-auto h-12 w-12 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-600">
                    Drag and drop files here, or click to select files
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Support for documents, images, and other file types
                  </p>
                </div>
              </div>

              {selectedAssignment && (
                <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">Assignment Details:</span>
                  </div>
                  <div className="text-sm text-gray-600">
                    <p><strong>Course:</strong> {selectedAssignment.courseName}</p>
                    <p><strong>Due:</strong> {format(new Date(selectedAssignment.dueDate), 'MMM dd, yyyy HH:mm')}</p>
                    <p><strong>Max Points:</strong> {selectedAssignment.maxPoints}</p>
                  </div>
                </div>
              )}

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setIsSubmitDialogOpen(false);
                    setSelectedAssignment(null);
                  }}
                >
                  Cancel
                </Button>
                <Button 
                  type="submit" 
                  disabled={submitAssignmentMutation.isPending}
                >
                  {submitAssignmentMutation.isPending ? "Submitting..." : "Submit Assignment"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
