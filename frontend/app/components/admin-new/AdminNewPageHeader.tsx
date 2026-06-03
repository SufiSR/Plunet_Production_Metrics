interface AdminNewPageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
}

export function AdminNewPageHeader({ eyebrow, title, description }: AdminNewPageHeaderProps) {
  return (
    <header className="mb-10">
      {eyebrow ? (
        <p className="text-[10px] font-editorial font-bold uppercase tracking-[0.1em] text-primary mb-2">
          {eyebrow}
        </p>
      ) : null}
      <h1 className="text-3xl md:text-4xl font-editorial font-bold tracking-tight text-on-surface mb-3">
        {title}
      </h1>
      {description ? (
        <p className="text-on-surface-variant max-w-3xl leading-relaxed text-sm">{description}</p>
      ) : null}
    </header>
  );
}
