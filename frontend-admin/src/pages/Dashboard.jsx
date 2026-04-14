import StatCard from "../components/StatCard";

const cards = [
  { title: "Employees", value: "0", hint: "Registered staff identities" },
  { title: "Gates", value: "1", hint: "Edge kiosk at the main entrance" },
  { title: "Queue", value: "0", hint: "Embedding and sync jobs pending" },
];

export default function Dashboard() {
  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Face Access Control</p>
        <h1>Admin workspace for a practical office access-control system.</h1>
        <p className="lead">
          The user-facing flow stays at the entrance kiosk. This admin app is
          reserved for employee enrollment, role management, audit logs,
          threshold tuning, and device configuration.
        </p>
      </section>

      <section className="grid">
        {cards.map((card) => (
          <StatCard key={card.title} {...card} />
        ))}
      </section>
    </main>
  );
}
