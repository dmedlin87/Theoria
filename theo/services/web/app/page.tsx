import Link from "next/link";

const FEATURES = [
  {
    title: "Semantic + lexical search",
    description:
      "Blend neural embeddings with keyword filters to surface the passages that matter most.",
    href: "/search",
    cta: "Open search",
  },
  {
    title: "Grounded copilot",
    description: "Run verse briefs, sermon prep, and comparative flows with OSIS-cited outputs.",
    href: "/copilot",
    cta: "Launch copilot",
  },
  {
    title: "Verse mentions explorer",
    description:
      "Trace how every verse is referenced across sermons, papers, and curated collections.",
    href: "/verse/John.1.1",
    cta: "Browse mentions",
  },
  {
    title: "Bulk ingest in seconds",
    description:
      "Upload documents or transcripts to enrich the corpus with automatic metadata extraction.",
    href: "/upload",
    cta: "Add new sources",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div>
          <p
            style={{
              textTransform: "uppercase",
              letterSpacing: "0.18em",
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "var(--accent)",
            }}
          >
            Research platform
          </p>
          <h2 id="hero-title">Bring theological research into focus.</h2>
          <p>
            Theo Engine unifies scripture-aware search, intelligent ingestion, and passage-level insights so your team can move
            from discovery to insight in record time.
          </p>
        </div>
        <div className="hero-actions">
          <Link href="/search" className="button">
            Start searching
          </Link>
          <Link href="/upload" className="button secondary">
            Upload documents
          </Link>
        </div>
      </section>

      <section aria-label="Platform capabilities">
        <div className="feature-grid">
          {FEATURES.map((feature) => (
            <article key={feature.title} className="feature-card">
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
              <Link href={feature.href}>{feature.cta}</Link>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
