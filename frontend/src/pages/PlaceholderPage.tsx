interface PlaceholderPageProps {
  title: string;
  description: string;
}

/** Temporary page for a section that is not built yet. */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="page">
      <h1>{title}</h1>
      <p>{description}</p>
    </section>
  );
}
