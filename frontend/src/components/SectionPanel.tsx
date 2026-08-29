interface SectionPanelProps {
  number: string;
  title: string;
  eyebrow?: string;
  status?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function SectionPanel({
  number,
  title,
  eyebrow,
  status,
  className = "",
  children,
}: SectionPanelProps) {
  const sectionKey = number.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const headingId = `section-${sectionKey}`;

  return (
    <section
      className={`section-panel ${className}`.trim()}
      aria-labelledby={headingId}
    >
      <header className="section-panel__header">
        <span className="section-panel__number" aria-hidden="true">
          {number}
        </span>
        <div className="section-panel__heading">
          {eyebrow ? <p className="section-panel__eyebrow">{eyebrow}</p> : null}
          <h2 id={headingId}>{title}</h2>
        </div>
        {status ? <div className="section-panel__status">{status}</div> : null}
      </header>
      <div className="section-panel__body">{children}</div>
    </section>
  );
}
