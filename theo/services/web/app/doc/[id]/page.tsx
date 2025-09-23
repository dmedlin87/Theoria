interface DocumentPageProps {
  params: { id: string };
}

export default function DocumentPage({ params }: DocumentPageProps) {
  return (
    <section>
      <h2>Document</h2>
      <p>Document ID: {params.id}</p>
      <p>Document viewer coming soon.</p>
    </section>
  );
}
