type JobCardProps = {
  title: string;
  company: string;
  location: string;
  match: number;
};

export function JobCard({ title, company, location, match }: JobCardProps) {
  return (
    <article className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="text-sm text-zinc-400">
            {company} - {location}
          </p>
        </div>
        <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300">
          {match}% match
        </span>
      </div>
    </article>
  );
}
