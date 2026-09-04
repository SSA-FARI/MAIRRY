import { AuthGuard } from "@/domains/auth";
import { ChatPage } from "@/domains/chat";

export default function ChatRoute() {
  return (
    <AuthGuard>
      <ChatPage />
    </AuthGuard>
  );
}
