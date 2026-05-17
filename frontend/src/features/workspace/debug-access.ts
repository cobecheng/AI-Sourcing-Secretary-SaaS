type DebugAccessInput = {
  appEnv?: string;
  nodeEnv?: string;
  viewerMode?: string;
};

export function canShowModelUsageDebug({
  appEnv,
  nodeEnv,
  viewerMode,
}: DebugAccessInput): boolean {
  return nodeEnv !== "production" || appEnv === "development" || viewerMode === "admin";
}
