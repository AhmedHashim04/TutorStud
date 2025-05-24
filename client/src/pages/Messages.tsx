import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { 
  Search, 
  Send, 
  Phone, 
  Video, 
  MoreVertical,
  Plus,
  Users,
  MessageCircle,
  WebhookOff,
  CheckCheck,
  Check
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useWebSocket } from "@/hooks/useWebSocket";
import { apiRequest } from "@/lib/queryClient";
import { formatDistanceToNow, format, isToday, isYesterday } from "date-fns";

export default function Messages() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { on } = useWebSocket();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedConversation, setSelectedConversation] = useState<number | null>(null);
  const [newMessage, setNewMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: messages } = useQuery({
    queryKey: ['/api/users', user?.id, 'messages'],
    enabled: !!user,
  });

  const { data: conversation } = useQuery({
    queryKey: ['/api/conversations', user?.id, selectedConversation],
    enabled: !!user && !!selectedConversation,
  });

  const { data: users } = useQuery({
    queryKey: ['/api/users'],
  });

  const sendMessageMutation = useMutation({
    mutationFn: (messageData: any) =>
      apiRequest('POST', '/api/messages', messageData),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['/api/users', user?.id, 'messages']
      });
      queryClient.invalidateQueries({
        queryKey: ['/api/conversations', user?.id, selectedConversation]
      });
      setNewMessage("");
    },
  });

  const markAsReadMutation = useMutation({
    mutationFn: (messageId: number) =>
      apiRequest('PUT', `/api/messages/${messageId}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['/api/users', user?.id, 'messages']
      });
    },
  });

  // Listen for real-time messages
  useEffect(() => {
    const cleanup = on('message', () => {
      queryClient.invalidateQueries({
        queryKey: ['/api/users', user?.id, 'messages']
      });
      if (selectedConversation) {
        queryClient.invalidateQueries({
          queryKey: ['/api/conversations', user?.id, selectedConversation]
        });
      }
    });

    return cleanup;
  }, [on, queryClient, user?.id, selectedConversation]);

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  const handleSendMessage = () => {
    if (!newMessage.trim() || !selectedConversation) return;

    sendMessageMutation.mutate({
      senderId: user?.id,
      receiverId: selectedConversation,
      content: newMessage.trim(),
      type: 'direct'
    });
  };

  // Get unique conversations from messages
  const conversations = messages?.reduce((acc: any[], message: any) => {
    const otherUserId = message.senderId === user?.id ? message.receiverId : message.senderId;
    const existingConversation = acc.find(c => c.userId === otherUserId);
    
    if (!existingConversation) {
      const otherUser = users?.find((u: any) => u.id === otherUserId);
      acc.push({
        userId: otherUserId,
        user: otherUser,
        lastMessage: message,
        unreadCount: messages.filter((m: any) => 
          m.senderId === otherUserId && m.receiverId === user?.id && !m.isRead
        ).length
      });
    } else if (new Date(message.sentAt) > new Date(existingConversation.lastMessage.sentAt)) {
      existingConversation.lastMessage = message;
    }
    
    return acc;
  }, []) || [];

  // Sort conversations by last message time
  conversations.sort((a, b) => 
    new Date(b.lastMessage.sentAt).getTime() - new Date(a.lastMessage.sentAt).getTime()
  );

  const filteredConversations = conversations.filter(conv =>
    conv.user?.firstName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.user?.lastName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.user?.username?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.lastMessage.content.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedUser = selectedConversation 
    ? users?.find((u: any) => u.id === selectedConversation)
    : null;

  const formatMessageTime = (date: Date) => {
    if (isToday(date)) {
      return format(date, 'HH:mm');
    } else if (isYesterday(date)) {
      return 'Yesterday';
    } else {
      return format(date, 'MMM dd');
    }
  };

  const formatLastSeen = (date: Date) => {
    return `Last seen ${formatDistanceToNow(date, { addSuffix: true })}`;
  };

  return (
    <div className="h-[calc(100vh-120px)] max-h-[800px]">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
        {/* Conversations List */}
        <div className="lg:col-span-1 flex flex-col">
          <Card className="flex-1 flex flex-col">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{t("messages")}</CardTitle>
                <Button size="icon" variant="outline">
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  placeholder="Search conversations..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </CardHeader>
            <CardContent className="flex-1 p-0">
              <ScrollArea className="h-full">
                <div className="space-y-1 p-3">
                  {filteredConversations.length === 0 ? (
                    <div className="text-center py-8">
                      <MessageCircle className="mx-auto h-12 w-12 text-gray-400" />
                      <h3 className="mt-4 text-sm font-medium text-gray-900">No conversations</h3>
                      <p className="mt-2 text-xs text-gray-500">Start a conversation with someone</p>
                    </div>
                  ) : (
                    filteredConversations.map((conv: any) => (
                      <div
                        key={conv.userId}
                        className={`flex items-center space-x-3 p-3 rounded-lg cursor-pointer transition-colors ${
                          selectedConversation === conv.userId 
                            ? 'bg-primary/10 border border-primary/20' 
                            : 'hover:bg-gray-50'
                        }`}
                        onClick={() => setSelectedConversation(conv.userId)}
                      >
                        <div className="relative">
                          <Avatar className="h-12 w-12">
                            <AvatarImage src={conv.user?.avatar} />
                            <AvatarFallback>
                              {conv.user?.firstName?.[0]}{conv.user?.lastName?.[0]}
                            </AvatarFallback>
                          </Avatar>
                          <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-white rounded-full" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {conv.user?.firstName} {conv.user?.lastName}
                            </p>
                            <p className="text-xs text-gray-500">
                              {formatMessageTime(new Date(conv.lastMessage.sentAt))}
                            </p>
                          </div>
                          <div className="flex items-center justify-between">
                            <p className="text-sm text-gray-600 truncate">
                              {conv.lastMessage.senderId === user?.id ? 'You: ' : ''}
                              {conv.lastMessage.content}
                            </p>
                            {conv.unreadCount > 0 && (
                              <Badge variant="destructive" className="h-5 w-5 p-0 flex items-center justify-center text-xs">
                                {conv.unreadCount}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Chat Area */}
        <div className="lg:col-span-2 flex flex-col">
          {selectedConversation ? (
            <Card className="flex-1 flex flex-col">
              {/* Chat Header */}
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-10 w-10">
                      <AvatarImage src={selectedUser?.avatar} />
                      <AvatarFallback>
                        {selectedUser?.firstName?.[0]}{selectedUser?.lastName?.[0]}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {selectedUser?.firstName} {selectedUser?.lastName}
                      </h3>
                      <p className="text-xs text-gray-500 flex items-center">
                        <div className="w-2 h-2 bg-green-500 rounded-full mr-2" />
                        WebhookOff
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Button size="icon" variant="ghost">
                      <Phone className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost">
                      <Video className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <Separator />
              </CardHeader>

              {/* Messages */}
              <CardContent className="flex-1 p-0">
                <ScrollArea className="h-full p-4">
                  <div className="space-y-4">
                    {conversation?.map((message: any) => (
                      <div
                        key={message.id}
                        className={`flex ${
                          message.senderId === user?.id ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        <div
                          className={`max-w-xs lg:max-w-md px-4 py-2 rounded-2xl ${
                            message.senderId === user?.id
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          <p className="text-sm">{message.content}</p>
                          <div className="flex items-center justify-between mt-1">
                            <p className="text-xs opacity-70">
                              {format(new Date(message.sentAt), 'HH:mm')}
                            </p>
                            {message.senderId === user?.id && (
                              <div className="ml-2">
                                {message.isRead ? (
                                  <CheckCheck className="h-3 w-3 opacity-70" />
                                ) : (
                                  <Check className="h-3 w-3 opacity-70" />
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </div>
                </ScrollArea>
              </CardContent>

              {/* Message Input */}
              <div className="p-4 border-t">
                <div className="flex space-x-2">
                  <Input
                    placeholder="Type a message..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        handleSendMessage();
                      }
                    }}
                    className="flex-1"
                  />
                  <Button
                    size="icon"
                    onClick={handleSendMessage}
                    disabled={!newMessage.trim() || sendMessageMutation.isPending}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <MessageCircle className="mx-auto h-16 w-16 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900">Select a conversation</h3>
                <p className="mt-2 text-gray-500">Choose a conversation from the sidebar to start messaging</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
