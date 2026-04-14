export default function StatCard({ title, value, hint }) {
  return (
    <article className="card">
      <span className="card-title">{title}</span>
      <strong className="card-value">{value}</strong>
      <p className="card-hint">{hint}</p>
    </article>
  );
}
