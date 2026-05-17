import styles from "./ChatWorkspace.module.css";
import type {
  ApprovalCard as ApprovalCardType,
  ChatMessage,
  Milestone,
  ModelUsage,
  ProjectSummary,
  Supplier,
  SupplierTerm,
  WorkspaceData,
} from "./types";

type ChatWorkspaceProps = {
  showModelUsageDebug?: boolean;
  workspace: WorkspaceData;
};

export function ChatWorkspace({
  showModelUsageDebug = false,
  workspace,
}: ChatWorkspaceProps) {
  return (
    <main className={styles.workspace}>
      <ProjectSidebar
        activeProject={workspace.activeProject}
        projects={workspace.projects}
      />
      <section className={styles.chatPanel} aria-label="Chat workspace">
        <header className={styles.chatHeader}>
          <div>
            <p className={styles.kicker}>Chat workspace</p>
            <h2>The chat is the product</h2>
          </div>
          <span className={styles.modeBadge}>Mock mode</span>
        </header>

        <div className={styles.messages}>
          {workspace.messages.map((message) => (
            <MessageBubble message={message} key={message.id} />
          ))}

          <section className={styles.approvalStack} aria-label="Approvals">
            {workspace.approvals.map((approval) => (
              <ApprovalCard approval={approval} key={approval.id} />
            ))}
          </section>
        </div>

        <form className={styles.chatInput}>
          <label className={styles.srOnly} htmlFor="chat-message">
            Message
          </label>
          <input
            id="chat-message"
            placeholder="Ask the secretary to research suppliers..."
          />
          <button className={styles.primaryButton} type="button">
            Send
          </button>
        </form>
      </section>

      <SupplierSidePanel
        milestones={workspace.milestones}
        suppliers={workspace.suppliers}
        terms={workspace.terms}
        modelUsage={workspace.modelUsage}
        showModelUsageDebug={showModelUsageDebug}
      />
    </main>
  );
}

function ProjectSidebar({
  activeProject,
  projects,
}: {
  activeProject: ProjectSummary;
  projects: ProjectSummary[];
}) {
  return (
    <aside className={styles.sidebar} aria-label="Projects">
      <div>
        <p className={styles.kicker}>AI Sourcing Secretary</p>
        <h1>{activeProject.name}</h1>
      </div>

      <button className={styles.primaryButton} type="button">
        New project
      </button>

      <div className={styles.statGrid}>
        <StatusMetric label="Project status" value={activeProject.status} />
        <StatusMetric
          label="Suppliers"
          value={String(activeProject.supplierCount)}
        />
        <StatusMetric
          label="Pending approvals"
          value={String(activeProject.pendingApprovals)}
        />
        <StatusMetric
          label="Unread replies"
          value={String(activeProject.unreadReplies)}
        />
      </div>

      <section aria-label="Project list" className={styles.projectList}>
        {projects.map((project) => (
          <article
            className={`${styles.projectRow} ${
              project.id === activeProject.id ? styles.projectRowActive : ""
            }`}
            key={project.id}
          >
            <strong>{project.name}</strong>
            <span>{project.status}</span>
          </article>
        ))}
      </section>
    </aside>
  );
}

function StatusMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  return (
    <article
      className={`${styles.message} ${
        message.sender === "user" ? styles.userMessage : ""
      } ${message.type === "missing_info_prompt" ? styles.infoMessage : ""}`}
    >
      <div className={styles.messageMeta}>
        <strong>{message.sender === "user" ? "User" : "AI Secretary"}</strong>
        <span>{message.label}</span>
      </div>
      <p>{message.content}</p>
    </article>
  );
}

function ApprovalCard({ approval }: { approval: ApprovalCardType }) {
  return (
    <article className={styles.approvalCard}>
      <div className={styles.approvalHeader}>
        <span className={styles.modeBadge}>Approval required</span>
        <span className={styles.approvalType}>
          {approval.type === "email" ? "Email" : "Contact form"}
        </span>
      </div>
      <div>
        <h3>{approval.title}</h3>
        <p>{approval.summary}</p>
      </div>

      <dl className={styles.previewList}>
        <div>
          <dt>Supplier</dt>
          <dd>{approval.supplierName}</dd>
        </div>
        <div>
          <dt>Evidence</dt>
          <dd>{approval.evidence}</dd>
        </div>
        {approval.fields?.map((field) => (
          <div key={field.label}>
            <dt>{field.label}</dt>
            <dd>{field.value}</dd>
          </div>
        ))}
      </dl>

      {approval.missingInfo.length > 0 ? (
        <div className={styles.missingInfo}>
          <strong>Missing information</strong>
          <ul>
            {approval.missingInfo.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className={styles.approvalActions}>
        <button type="button">Edit</button>
        <button type="button">Reject</button>
        <button className={styles.primaryButton} type="button">
          Approve
        </button>
      </div>
    </article>
  );
}

function SupplierSidePanel({
  milestones,
  suppliers,
  terms,
  modelUsage,
  showModelUsageDebug,
}: {
  milestones: Milestone[];
  suppliers: Supplier[];
  terms: SupplierTerm[];
  modelUsage: ModelUsage[];
  showModelUsageDebug: boolean;
}) {
  return (
    <aside className={styles.rightPanel} aria-label="Supplier status">
      <section>
        <p className={styles.kicker}>Current task</p>
        <ol className={styles.milestoneList}>
          {milestones.map((milestone) => (
            <li className={styles[milestone.status]} key={milestone.id}>
              <span aria-hidden="true" />
              <strong>{milestone.name}</strong>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <p className={styles.kicker}>Supplier list</p>
        <div className={styles.supplierList}>
          {suppliers.map((supplier) => (
            <SupplierCard supplier={supplier} key={supplier.id} />
          ))}
        </div>
      </section>

      <TermsPanel terms={terms} />
      {showModelUsageDebug ? <ModelUsageDebugPanel usage={modelUsage} /> : null}
    </aside>
  );
}

function SupplierCard({ supplier }: { supplier: Supplier }) {
  return (
    <article className={styles.supplierCard}>
      <div>
        <strong>{supplier.name}</strong>
        <span>{supplier.country}</span>
      </div>
      <p>{supplier.status}</p>
      <div className={styles.supplierScores}>
        <span>Relevance {Math.round(supplier.relevanceScore * 100)}%</span>
        <span>Trust {Math.round(supplier.trustScore * 100)}%</span>
      </div>
    </article>
  );
}

function TermsPanel({ terms }: { terms: SupplierTerm[] }) {
  return (
    <section className={styles.termsPanel}>
      <p className={styles.kicker}>Extracted terms</p>
      <dl>
        {terms.map((term) => (
          <div key={term.label}>
            <dt>{term.label}</dt>
            <dd>{term.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ModelUsageDebugPanel({ usage }: { usage: ModelUsage[] }) {
  return (
    <section className={styles.debugPanel} aria-label="Model usage debug">
      <div className={styles.debugHeader}>
        <p className={styles.kicker}>Model usage debug</p>
        <span>Admin</span>
      </div>
      <div className={styles.debugRows}>
        {usage.map((item) => (
          <article className={styles.debugRow} key={item.taskType}>
            <strong>{item.taskType}</strong>
            <dl className={styles.debugMetrics}>
              <div>
                <dt>Provider</dt>
                <dd>{item.provider}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{item.model}</dd>
              </div>
              <div>
                <dt>Cost</dt>
                <dd>{item.cost}</dd>
              </div>
              <div>
                <dt>Latency</dt>
                <dd>{item.latency}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{item.confidence}</dd>
              </div>
              <div>
                <dt>Fallback</dt>
                <dd>{item.fallbackUsed ? "yes" : "no"}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
