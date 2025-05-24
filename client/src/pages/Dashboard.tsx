import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { 
  BookOpen, 
  ClipboardList, 
  TrendingUp, 
  MessageSquare,
  Plus,
  Upload,
  Calendar,
  Check,
  Clock,
  Star,
  FileText,
  Video,
  Presentation
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { formatDistanceToNow } from "date-fns";

export default function Dashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();

  const { data: courses } = useQuery({
    queryKey: ['/api/users', user?.id, 'courses'],
    enabled: !!user,
  });

  const { data: notifications } = useQuery({
    queryKey: ['/api/users', user?.id, 'notifications'],
    enabled: !!user,
  });

  const { data: messages } = useQuery({
    queryKey: ['/api/users', user?.id, 'messages'],
    enabled: !!user,
  });

  const activeCourses = courses?.length || 0;
  const unreadNotifications = notifications?.filter((n: any) => !n.isRead).length || 0;
  const unreadMessages = messages?.filter((m: any) => !m.isRead && m.receiverId === user?.id).length || 0;
  const totalProgress = courses?.reduce((acc: number, course: any) => acc + (course.progress || 0), 0) || 0;
  const averageProgress = activeCourses > 0 ? Math.round(totalProgress / activeCourses) : 0;

  const recentNotifications = notifications?.slice(0, 4) || [];
  const recentCourses = courses?.slice(0, 3) || [];

  const stats = [
    {
      title: t("activeCourses"),
      value: activeCourses,
      icon: BookOpen,
      color: "bg-blue-100 text-blue-600",
    },
    {
      title: t("pendingTasks"),
      value: unreadNotifications,
      icon: ClipboardList,
      color: "bg-purple-100 text-purple-600",
    },
    {
      title: t("progress"),
      value: `${averageProgress}%`,
      icon: TrendingUp,
      color: "bg-green-100 text-green-600",
    },
    {
      title: t("newMessages"),
      value: unreadMessages,
      icon: MessageSquare,
      color: "bg-orange-100 text-orange-600",
    },
  ];

  const quickActions = [
    {
      title: t("createCourse"),
      icon: Plus,
      action: () => {}, // TODO: Implement
      primary: true,
    },
    {
      title: t("uploadMaterials"),
      icon: Upload,
      action: () => {}, // TODO: Implement
    },
    {
      title: t("scheduleAssignment"),
      icon: Calendar,
      action: () => {}, // TODO: Implement
    },
  ];

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'assignment':
        return Check;
      case 'message':
        return MessageSquare;
      case 'course':
        return BookOpen;
      case 'grade':
        return Star;
      default:
        return Clock;
    }
  };

  const getActivityColor = (type: string) => {
    switch (type) {
      case 'assignment':
        return 'text-green-600 bg-green-100';
      case 'message':
        return 'text-blue-600 bg-blue-100';
      case 'course':
        return 'text-purple-600 bg-purple-100';
      case 'grade':
        return 'text-orange-600 bg-orange-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getMaterialIcon = (type: string) => {
    switch (type) {
      case 'video':
        return Video;
      case 'pdf':
        return FileText;
      case 'presentation':
        return Presentation;
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

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          {t("welcomeBack", { name: user?.firstName || "Student" })}
        </h1>
        <p className="text-gray-600">{t("todayActivity")}</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <Card key={index} className="hover:shadow-md transition-shadow">
            <CardContent className="p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className={`w-10 h-10 ${stat.color} rounded-lg flex items-center justify-center`}>
                    <stat.icon className="h-5 w-5" />
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column */}
        <div className="lg:col-span-2 space-y-8">
          {/* Recent Courses */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{t("recentCourses")}</CardTitle>
                <Link href="/courses">
                  <Button variant="ghost" size="sm">
                    {t("viewAll")}
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentCourses.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No courses enrolled yet
                  </div>
                ) : (
                  recentCourses.map((course: any, index: number) => (
                    <div key={course.id} className="flex items-center p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors">
                      <img 
                        src={`https://images.unsplash.com/photo-${index === 0 ? '1498050108023-c5249f4df085' : index === 1 ? '1522202176988-66273c2fd55f' : '1516321318423-f06f85e504b3'}?ixlib=rb-4.0.3&auto=format&fit=crop&w=64&h=64`} 
                        alt={course.title} 
                        className="w-16 h-16 rounded-lg object-cover"
                      />
                      <div className="ml-4 flex-1">
                        <h3 className="font-medium text-gray-900">{course.title}</h3>
                        <p className="text-sm text-gray-600 truncate">{course.description}</p>
                        <div className="flex items-center mt-2">
                          <div className="flex-1 bg-gray-200 rounded-full h-2">
                            <div 
                              className="bg-primary h-2 rounded-full" 
                              style={{ width: `${course.progress || 0}%` }}
                            />
                          </div>
                          <span className="ml-3 text-sm text-gray-600">{course.progress || 0}%</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <Link href={`/courses/${course.id}`}>
                          <Button variant="outline" size="sm">
                            View Course
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Upcoming Assignments */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{t("upcomingAssignments")}</CardTitle>
                <Link href="/assignments">
                  <Button variant="ghost" size="sm">
                    {t("viewAll")}
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Sample upcoming assignments */}
                <div className="border-l-4 border-red-500 pl-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">Final Project Submission</h3>
                      <p className="text-sm text-gray-600">Web Development Course</p>
                    </div>
                    <Badge variant="destructive">Due Tomorrow</Badge>
                  </div>
                </div>
                <div className="border-l-4 border-orange-500 pl-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">Data Analysis Report</h3>
                      <p className="text-sm text-gray-600">Data Science Course</p>
                    </div>
                    <Badge variant="outline" className="text-orange-600 border-orange-600">
                      Due in 3 days
                    </Badge>
                  </div>
                </div>
                <div className="border-l-4 border-blue-500 pl-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">Mobile App Prototype</h3>
                      <p className="text-sm text-gray-600">Mobile Development Course</p>
                    </div>
                    <Badge variant="outline" className="text-blue-600 border-blue-600">
                      Due in 1 week
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column */}
        <div className="space-y-8">
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>{t("quickActions")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {quickActions.map((action, index) => (
                  <Button
                    key={index}
                    variant={action.primary ? "default" : "outline"}
                    className="w-full justify-start"
                    onClick={action.action}
                  >
                    <action.icon className="mr-2 h-4 w-4" />
                    {action.title}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle>{t("recentActivity")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentNotifications.length === 0 ? (
                  <div className="text-center py-4 text-gray-500">
                    No recent activity
                  </div>
                ) : (
                  recentNotifications.map((notification: any) => {
                    const IconComponent = getActivityIcon(notification.type);
                    return (
                      <div key={notification.id} className="flex items-start space-x-3">
                        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${getActivityColor(notification.type)}`}>
                          <IconComponent className="h-4 w-4" />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm text-gray-900">{notification.message}</p>
                          <p className="text-xs text-gray-500">
                            {formatDistanceToNow(new Date(notification.createdAt), { addSuffix: true })}
                          </p>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>

          {/* Sample Recent Messages Preview */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{t("recentMessages")}</CardTitle>
                <Link href="/messages">
                  <Button variant="ghost" size="sm">
                    {t("viewAll")}
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&auto=format&fit=crop&w=32&h=32" />
                    <AvatarFallback>SW</AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">Sarah Wilson</p>
                    <p className="text-xs text-gray-600">Thanks for the feedback on...</p>
                  </div>
                  <div className="text-xs text-gray-500">5m</div>
                </div>
                <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>ED</AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">Emma Davis</p>
                    <p className="text-xs text-gray-600">Could you help me with...</p>
                  </div>
                  <div className="text-xs text-gray-500">1h</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Course Materials Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{t("courseMaterials")}</CardTitle>
            <div className="flex space-x-2">
              <Button variant="outline" size="sm">All</Button>
              <Button variant="default" size="sm">Videos</Button>
              <Button variant="outline" size="sm">PDFs</Button>
              <Button variant="outline" size="sm">Presentations</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Sample materials */}
            {[
              { type: 'video', title: 'React Fundamentals', duration: '45 min', image: 'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=200' },
              { type: 'pdf', title: 'JavaScript ES6+ Guide', pages: '24 pages', image: 'https://images.unsplash.com/photo-1456324504439-367cee3b3c32?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=200' },
              { type: 'presentation', title: 'Database Design Patterns', slides: '32 slides', image: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=200' }
            ].map((material, index) => {
              const IconComponent = getMaterialIcon(material.type);
              return (
                <Card key={index} className="overflow-hidden hover:shadow-md transition-shadow">
                  <div className="aspect-video w-full overflow-hidden">
                    <img src={material.image} alt={material.title} className="w-full h-full object-cover" />
                  </div>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="secondary" className={`text-xs ${getMaterialColor(material.type)}`}>
                        {material.type.toUpperCase()}
                      </Badge>
                      <span className="text-xs text-gray-500">
                        {material.duration || material.pages || material.slides}
                      </span>
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">{material.title}</h3>
                    <p className="text-sm text-gray-600 mb-3">
                      Learn the basics of {material.title.toLowerCase()} and core concepts.
                    </p>
                    <Button 
                      className={`w-full ${material.type === 'video' ? 'bg-blue-600 hover:bg-blue-700' : 
                        material.type === 'pdf' ? 'bg-red-600 hover:bg-red-700' : 
                        'bg-green-600 hover:bg-green-700'}`}
                      size="sm"
                    >
                      <IconComponent className="mr-2 h-4 w-4" />
                      {material.type === 'video' ? 'Watch Now' : 
                       material.type === 'pdf' ? 'Download PDF' : 
                       'View Slides'}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
