type EmailCardProps = {
  subject: string;
  preview: string;
  status: "Draft" | "Scheduled" | "Sent";
};

export function EmailCard({ subject, preview, status }: EmailCardProps) {
  return (
    <article className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white">{subject}</h3>
        <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300">
          {status}
        </span>
      </div>
      <p className="mt-3 text-sm text-zinc-300">{preview}</p>
    </article>
  );
}
