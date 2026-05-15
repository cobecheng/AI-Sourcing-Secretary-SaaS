import { ChatWorkspace } from "@/features/workspace/ChatWorkspace";
import { mockWorkspace } from "@/features/workspace/mock-data";

export default function Home() {
  return <ChatWorkspace workspace={mockWorkspace} />;
}
