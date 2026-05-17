import { ChatWorkspace } from "@/features/workspace/ChatWorkspace";
import { canShowModelUsageDebug } from "@/features/workspace/debug-access";
import { mockWorkspace } from "@/features/workspace/mock-data";

export default function Home() {
  const showModelUsageDebug = canShowModelUsageDebug({
    appEnv: process.env.APP_ENV,
    nodeEnv: process.env.NODE_ENV,
    viewerMode: process.env.WORKSPACE_VIEWER_MODE,
  });

  return (
    <ChatWorkspace
      showModelUsageDebug={showModelUsageDebug}
      workspace={mockWorkspace}
    />
  );
}
