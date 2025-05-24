import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { MessageCircle, Send } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useWebSocket } from "@/hooks/useWebSocket";
import { apiRequest } from "@/lib/queryClient";
import { formatDistanceToNow } from "date-fns";

export function ChatWidget() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { on } = useWebSocket();
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [newMessage, setNewMessage] = useState("");
  const [selectedConversation, setSelectedConversation] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: messages } = useQuery({
    queryKey: ['/api/users', user?.id, 'messages'],
    enabled: !!user,
  });

  const { data: conversation } = useQuery({
    queryKey: ['/api/conversations', user?.id, selectedConversation],
    enabled: !!user && !!selectedConversation,
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
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
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
    if (!acc.find(c => c.userId === otherUserId)) {
      acc.push({
        userId: otherUserId,
        lastMessage: message,
        unreadCount: messages.filter((m: any) => 
          m.senderId === otherUserId && !m.isRead
        ).length
      });
    }
    return acc;
  }, []) || [];

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button
          size="icon"
          className="fixed bottom-6 right-6 h-12 w-12 rounded-full shadow-lg hover:shadow-xl transition-shadow z-50"
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      </SheetTrigger>
      <SheetContent className="w-[400px] sm:w-[540px]">
        <SheetHeader>
          <SheetTitle className="flex items-center space-x-2">
            <MessageCircle className="h-5 w-5" />
            <span>{t("messages")}</span>
          </SheetTitle>
          <SheetDescription>
            {selectedConversation ? "Chat conversation" : "Select a conversation"}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 h-[calc(100vh-120px)]">
          {!selectedConversation ? (
            // Conversation list
            <ScrollArea className="h-full">
              <div className="space-y-3">
                {conversations.length === 0 ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="text-sm text-gray-500">No conversations yet</div>
                  </div>
                ) : (
                  conversations.map((conv: any) => (
                    <Card
                      key={conv.userId}
                      className="cursor-pointer hover:bg-gray-50 transition-colors"
                      onClick={() => setSelectedConversation(conv.userId)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-center space-x-3">
                          <Avatar className="h-10 w-10">
                            <AvatarFallback>
                              {conv.lastMessage.senderId === user?.id ? 'You' : 'U'}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900">
                              User {conv.userId}
                            </p>
                            <p className="text-sm text-gray-600 truncate">
                              {conv.lastMessage.content}
                            </p>
                            <p className="text-xs text-gray-500">
                              {formatDistanceToNow(new Date(conv.lastMessage.sentAt), { addSuffix: true })}
                            </p>
                          </div>
                          {conv.unreadCount > 0 && (
                            <div className="bg-primary text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                              {conv.unreadCount}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </ScrollArea>
          ) : (
            // Conversation view
            <div className="flex flex-col h-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="font-semibold">User {selectedConversation}</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedConversation(null)}
                >
                  Back
                </Button>
              </div>

              <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                <div className="space-y-4">
                  {conversation?.map((message: any) => (
                    <div
                      key={message.id}
                      className={`flex ${
                        message.senderId === user?.id ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      <div
                        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                          message.senderId === user?.id
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <p className="text-sm">{message.content}</p>
                        <p className="text-xs opacity-70 mt-1">
                          {formatDistanceToNow(new Date(message.sentAt), { addSuffix: true })}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

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
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
