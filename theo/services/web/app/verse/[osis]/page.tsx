interface VersePageProps {
  params: { osis: string };
}

export default function VersePage({ params }: VersePageProps) {
  return (
    <section>
      <h2>Verse Mentions</h2>
      <p>OSIS: {params.osis}</p>
      <p>No mentions yet (API stub).</p>
    </section>
  );
}
