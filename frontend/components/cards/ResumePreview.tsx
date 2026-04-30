type ResumePreviewProps = {
  name: string;
  role: string;
  summary: string;
};

export function ResumePreview({ name, role, summary }: ResumePreviewProps) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <h3 className="text-base font-semibold text-white">{name}</h3>
      <p className="mt-1 text-sm text-cyan-300">{role}</p>
      <p className="mt-3 text-sm text-zinc-300">{summary}</p>
    </section>
  );
}
