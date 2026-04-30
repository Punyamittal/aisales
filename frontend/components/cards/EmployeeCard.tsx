type EmployeeCardProps = {
  name: string;
  title: string;
  company: string;
  mutualTopics: string[];
};

export function EmployeeCard({
  name,
  title,
  company,
  mutualTopics,
}: EmployeeCardProps) {
  return (
    <article className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <h3 className="text-base font-semibold text-white">{name}</h3>
      <p className="mt-1 text-sm text-zinc-400">
        {title} at {company}
      </p>
      <p className="mt-3 text-xs uppercase tracking-wide text-zinc-500">
        Outreach Hooks
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {mutualTopics.map((topic) => (
          <span
            key={topic}
            className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-200"
          >
            {topic}
          </span>
        ))}
      </div>
    </article>
  );
}
