type ATSScoreCardProps = {
  score: number;
  missingKeywords: string[];
};

export function ATSScoreCard({ score, missingKeywords }: ATSScoreCardProps) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white">ATS Score</h3>
        <span className="text-xl font-bold text-cyan-300">{score}/100</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {missingKeywords.map((keyword) => (
          <span
            key={keyword}
            className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300"
          >
            {keyword}
          </span>
        ))}
      </div>
    </section>
  );
}
