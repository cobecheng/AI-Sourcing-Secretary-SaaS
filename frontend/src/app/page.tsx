import styles from "./page.module.css";

const messages = [
  {
    sender: "User",
    type: "Request",
    content:
      "Find Pokemon TCG distributors in the UK or EU. I want sealed products like booster boxes and ETBs. Prefer suppliers that accept small retailers.",
  },
  {
    sender: "AI Secretary",
    type: "Milestone",
    content:
      "Request understood. I will check official distributors, wholesalers, importers, and specialist TCG suppliers, then report after each milestone.",
  },
  {
    sender: "AI Secretary",
    type: "Milestone",
    content:
      "Mock milestone complete: 14 suppliers look relevant. 8 have email addresses, 4 have contact forms only, and 2 need manual review.",
  },
];

const suppliers = [
  {
    name: "CardTrade Wholesale",
    country: "UK",
    status: "Email Drafted",
    score: "91%",
  },
  {
    name: "EU TCG Distribution",
    country: "EU",
    status: "Contact Form Found",
    score: "87%",
  },
  {
    name: "Specialist Cards Import",
    country: "UK",
    status: "Manual Review Needed",
    score: "72%",
  },
];

export default function Home() {
  return (
    <main className={styles.workspace}>
      <aside className={styles.sidebar} aria-label="Projects">
        <div>
          <p className={styles.kicker}>AI Sourcing Secretary</p>
          <h1>Pokemon TCG sourcing</h1>
        </div>
        <button className={styles.primaryButton}>New project</button>
        <div className={styles.statGrid}>
          <div>
            <span>Project status</span>
            <strong>Mock research</strong>
          </div>
          <div>
            <span>Suppliers</span>
            <strong>14</strong>
          </div>
          <div>
            <span>Pending approvals</span>
            <strong>2</strong>
          </div>
          <div>
            <span>Unread replies</span>
            <strong>0</strong>
          </div>
        </div>
      </aside>

      <section className={styles.chatPanel} aria-label="Chat workspace">
        <header className={styles.chatHeader}>
          <div>
            <p className={styles.kicker}>Chat workspace</p>
            <h2>The chat is the product</h2>
          </div>
          <span className={styles.modeBadge}>Mock mode</span>
        </header>

        <div className={styles.messages}>
          {messages.map((message) => (
            <article
              className={`${styles.message} ${
                message.sender === "User" ? styles.userMessage : ""
              }`}
              key={message.content}
            >
              <div className={styles.messageMeta}>
                <strong>{message.sender}</strong>
                <span>{message.type}</span>
              </div>
              <p>{message.content}</p>
            </article>
          ))}

          <article className={styles.approvalCard}>
            <div>
              <span className={styles.modeBadge}>Approval required</span>
              <h3>Approve supplier outreach email</h3>
              <p>
                Supplier: CardTrade Wholesale. The AI has drafted outreach but
                cannot send it until the user approves.
              </p>
            </div>
            <div className={styles.approvalActions}>
              <button>Edit</button>
              <button>Reject</button>
              <button className={styles.primaryButton}>Approve</button>
            </div>
          </article>
        </div>

        <form className={styles.chatInput}>
          <input
            aria-label="Message"
            placeholder="Ask the secretary to research suppliers..."
          />
          <button className={styles.primaryButton} type="button">
            Send
          </button>
        </form>
      </section>

      <aside className={styles.rightPanel} aria-label="Supplier status">
        <section>
          <p className={styles.kicker}>Supplier list</p>
          <div className={styles.supplierList}>
            {suppliers.map((supplier) => (
              <article className={styles.supplierCard} key={supplier.name}>
                <div>
                  <strong>{supplier.name}</strong>
                  <span>{supplier.country}</span>
                </div>
                <p>{supplier.status}</p>
                <span className={styles.score}>{supplier.score}</span>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.termsPanel}>
          <p className={styles.kicker}>Extracted terms</p>
          <dl>
            <div>
              <dt>MOQ</dt>
              <dd>Pending reply</dd>
            </div>
            <div>
              <dt>Pricing</dt>
              <dd>Requires account</dd>
            </div>
            <div>
              <dt>Lead time</dt>
              <dd>Unknown</dd>
            </div>
          </dl>
        </section>
      </aside>
    </main>
  );
}

