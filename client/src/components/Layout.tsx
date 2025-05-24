import { Navigation } from "./Navigation";
import { NotificationCenter } from "./NotificationCenter";
import { ChatWidget } from "./ChatWidget";
import { useLanguage } from "@/contexts/LanguageContext";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { isRTL } = useLanguage();

  return (
    <div className={`min-h-screen bg-gray-50 font-sans ${isRTL ? 'font-arabic' : ''}`}>
      <Navigation />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      <NotificationCenter />
      <ChatWidget />
    </div>
  );
}
