import type { WorkspaceData } from "./types";

export const mockWorkspace: WorkspaceData = {
  activeProject: {
    id: "pokemon-uk-eu",
    name: "Pokemon TCG sourcing",
    status: "Mock research",
    supplierCount: 14,
    pendingApprovals: 2,
    unreadReplies: 0,
  },
  projects: [
    {
      id: "pokemon-uk-eu",
      name: "Pokemon TCG sourcing",
      status: "Mock research",
      supplierCount: 14,
      pendingApprovals: 2,
      unreadReplies: 0,
    },
    {
      id: "sealed-products",
      name: "Sealed product wholesalers",
      status: "Draft",
      supplierCount: 0,
      pendingApprovals: 0,
      unreadReplies: 0,
    },
  ],
  messages: [
    {
      id: "msg-1",
      sender: "user",
      label: "Request",
      type: "text",
      content:
        "Find Pokemon TCG distributors in the UK or EU. I want sealed products like booster boxes and ETBs. Prefer suppliers that accept small retailers.",
    },
    {
      id: "msg-2",
      sender: "assistant",
      label: "Milestone",
      type: "milestone_update",
      content:
        "Request understood. I will check official distributors, wholesalers, importers, and specialist TCG suppliers, then report after each milestone.",
    },
    {
      id: "msg-3",
      sender: "assistant",
      label: "Milestone",
      type: "milestone_update",
      content:
        "Mock milestone complete: 14 suppliers look relevant. 8 have email addresses, 4 have contact forms only, and 2 need manual review.",
    },
    {
      id: "msg-4",
      sender: "assistant",
      label: "Missing information",
      type: "missing_info_prompt",
      content:
        "Some suppliers ask for a store name, business website, country, optional VAT number, and expected monthly order size before sharing wholesale pricing.",
    },
  ],
  approvals: [
    {
      id: "approval-email-1",
      type: "email",
      title: "Approve supplier outreach email",
      supplierName: "CardTrade Wholesale",
      status: "pending",
      summary:
        "Draft asks whether the supplier supports small retailers and can share wholesale account requirements for sealed Pokemon TCG products.",
      evidence: "Supplier source: mock/cardtrade-wholesale/contact",
      missingInfo: ["Store website", "Expected monthly order size"],
      fields: [
        { label: "Recipient", value: "sales@example-supplier.test" },
        { label: "Subject", value: "Wholesale Pokemon TCG account enquiry" },
      ],
    },
    {
      id: "approval-form-1",
      type: "contact_form",
      title: "Review contact form payload",
      supplierName: "EU TCG Distribution",
      status: "pending",
      summary:
        "The mock browser agent found a wholesale enquiry form. Submission is blocked until required business details are provided and approved.",
      evidence: "Supplier source: mock/eu-tcg-distribution/wholesale-form",
      missingInfo: ["VAT number optional", "Business phone number"],
      fields: [
        { label: "Form URL", value: "https://supplier.example/wholesale" },
        { label: "Requires CAPTCHA", value: "No in mock mode" },
      ],
    },
  ],
  suppliers: [
    {
      id: "supplier-1",
      name: "CardTrade Wholesale",
      country: "UK",
      status: "Email Drafted",
      contactMethod: "email",
      relevanceScore: 0.91,
      trustScore: 0.78,
    },
    {
      id: "supplier-2",
      name: "EU TCG Distribution",
      country: "EU",
      status: "Contact Form Found",
      contactMethod: "form",
      relevanceScore: 0.87,
      trustScore: 0.73,
    },
    {
      id: "supplier-3",
      name: "Specialist Cards Import",
      country: "UK",
      status: "Manual Review Needed",
      contactMethod: "manual_review",
      relevanceScore: 0.72,
      trustScore: 0.61,
    },
  ],
  milestones: [
    { id: "milestone-1", name: "Request understood", status: "complete" },
    { id: "milestone-2", name: "Suppliers discovered", status: "complete" },
    { id: "milestone-3", name: "Suppliers verified", status: "active" },
    { id: "milestone-4", name: "Outreach approval", status: "pending" },
  ],
  terms: [
    { label: "MOQ", value: "Pending reply" },
    { label: "Pricing", value: "Requires account" },
    { label: "Payment terms", value: "Unknown" },
    { label: "Lead time", value: "Unknown" },
  ],
  modelUsage: [
    {
      taskType: "milestone_update",
      provider: "mock",
      model: "mock-cheap",
      cost: "$0.0000",
      latency: "8 ms",
      confidence: "0.99",
      fallbackUsed: false,
    },
    {
      taskType: "supplier_relevance_scoring",
      provider: "mock",
      model: "mock-mid",
      cost: "$0.0000",
      latency: "12 ms",
      confidence: "0.87",
      fallbackUsed: false,
    },
  ],
};

