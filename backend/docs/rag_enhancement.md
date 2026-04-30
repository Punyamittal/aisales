# AI + RAG Enhancement

## Architecture

- **Embedding layer**: creates vectors for job descriptions and resumes.
- **Vector storage**: stores vectors in Supabase `rag_vectors` (pgvector target), with in-memory fallback for local development.
- **Retriever**: cosine-similarity search returns top matching jobs for candidate context.
- **Tailoring layer**: injects retrieved job context into resume generation prompt/content.
- **Pipeline integration**: `jobs -> retrieve -> resume tailor -> ATS`.

## Flow Diagram

```text
resume/profile input
  -> embed candidate text
  -> store/query candidate vector
  -> embed/index jobs
  -> retrieve top-k semantic jobs
  -> build RAG context (job requirements + candidate strengths)
  -> generate tailored resume
  -> ATS analyze and iterate if needed
```

## Tech Stack

- **OpenAI path**
  - Embeddings: `text-embedding-3-small`
  - LLM: GPT family for high-quality tailoring
- **Local path**
  - Embeddings: Ollama `/api/embeddings`
  - Generation: Ollama model configured via `OLLAMA_MODEL`
- **Vector DB**
  - Primary: Supabase Postgres + pgvector
  - Dev fallback: in-memory vector collection
