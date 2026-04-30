export default function Home() {
  return (
    <section className="space-y-6">
      <div className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900 to-zinc-950 p-6">
        <h1 className="text-3xl font-semibold tracking-tight text-white">
          AI Career Assistant
        </h1>
        <p className="mt-2 max-w-2xl text-zinc-400">
          Plan your job search, tailor your resume, improve ATS score, and run
          personalized outreach from one workspace.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[
          "Smart profile intake",
          "Resume optimization",
          "Live job matching",
          "ATS analyzer",
          "Outreach drafting",
          "Progress analytics",
        ].map((item) => (
          <div
            key={item}
            className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4"
          >
            <p className="text-sm text-zinc-200">{item}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
