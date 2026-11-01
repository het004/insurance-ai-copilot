import { Suspense } from "react";
import { ChatView } from "@/features/chat/chat-view";

export const metadata = { title: "Chat with Amaan" };

export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatView />
    </Suspense>
  );
}
