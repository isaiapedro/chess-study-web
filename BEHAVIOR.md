# Chess Coach Experiment — Behavior

## Transient Operations
- Optimizes for local offline coaching spikes: PGN analysis, engine truth, RAG book recall, Ollama prose.
- Scid GUI, scrapers, and cloud LLMs are out of scope for this experiment node.

## Boundaries
- Stockfish is sole authority for evaluations and principal variations.
- RAG passages supply pedagogical language only; they never override engine numbers.
- Copyrighted book binaries stay under `data/books/` and must not be committed.
