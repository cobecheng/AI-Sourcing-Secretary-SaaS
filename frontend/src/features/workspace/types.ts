export type ProjectSummary = {
  id: string;
  name: string;
  status: string;
  supplierCount: number;
  pendingApprovals: number;
  unreadReplies: number;
};

export type ChatMessage = {
  id: string;
  sender: "user" | "assistant";
  label: string;
  type: "text" | "milestone_update" | "missing_info_prompt";
  content: string;
};

export type ApprovalCard = {
  id: string;
  type: "email" | "contact_form";
  title: string;
  supplierName: string;
  status: "pending" | "edited" | "rejected";
  summary: string;
  evidence: string;
  missingInfo: string[];
  fields?: Array<{
    label: string;
    value: string;
  }>;
};

export type Supplier = {
  id: string;
  name: string;
  country: string;
  status: string;
  contactMethod: "email" | "form" | "manual_review";
  relevanceScore: number;
  trustScore: number;
};

export type Milestone = {
  id: string;
  name: string;
  status: "complete" | "active" | "pending";
};

export type SupplierTerm = {
  label: string;
  value: string;
};

export type ModelUsage = {
  taskType: string;
  provider: string;
  model: string;
  cost: string;
  latency: string;
  confidence: string;
  fallbackUsed: boolean;
};

export type WorkspaceData = {
  activeProject: ProjectSummary;
  projects: ProjectSummary[];
  messages: ChatMessage[];
  approvals: ApprovalCard[];
  suppliers: Supplier[];
  milestones: Milestone[];
  terms: SupplierTerm[];
  modelUsage: ModelUsage[];
};

