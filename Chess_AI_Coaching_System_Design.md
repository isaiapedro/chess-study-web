# Local AI Chess Coaching System

## 💡 The Core Idea

Large Language Models (LLMs) are notoriously bad at calculating chess variations and tracking piece positions, often hallucinating illegal moves. However, they are excellent at parsing natural language and explaining complex abstract concepts. 

The **Local AI Chess Coaching System** solves this by separating computation from communication. It uses a hybrid architecture built entirely on local, open-source Debian tools:
1. **Stockfish** acts as the tactical brain (Ground Truth).
2. **A Vector Database (RAG)** acts as the memory (Indexing classic chess books).
3. **A Local LLM (Ollama)** acts as the translator (Explaining the engine's moves using the book's principles).

By anchoring the LLM's commentary exclusively to the engine's strict numerical evaluation and the exact text of digitized chess books, you get an AI that talks like a Grandmaster author but calculates with the accuracy of a machine.

---

## 🚀 Core Features

### 1. Unified PGN Archive & GUI
* **Scid vs PC Integration:** A robust, localized database manager capable of storing millions of master games and personal games.
* **Tagging & Curation:** Manage distinct databases (e.g., "My Tournament Games", "My 60 Memorable Games").

### 2. Automated Game Sourcing & Scraping
* **Book Game Fetcher:** Python scripts utilizing `python-chess` and the Lichess Master API to automatically pull full PGN data for games referenced in classic chess books.
* **Format Standardization:** Automatically parses metadata (White, Black, Date, ECO code) and saves them to local directories for Scid ingestion.

### 3. Tactical Ground Truth via Local Engine
* **UCI Protocol Communication:** Directly feeds FEN positions to Stockfish 16+ via Python.
* **Precise Evaluations:** Extracts centipawn score, best engine lines (PV - Principal Variation), and depth to eliminate any risk of AI hallucination regarding board state.

### 4. RAG-Powered Chess Book Library
* **PDF & Text Ingestion:** Extracts text from digitized chess books (e.g., *Logical Chess*, *My System*).
* **Positional Vector Database:** Uses ChromaDB or FAISS to chunk and store book paragraphs.
* **Contextual Retrieval:** Queries the database using opening names (e.g., "Sicilian Dragon") or positional themes (e.g., "Isolated Queen Pawn", "Minority Attack") to fetch relevant book passages.

### 5. Synthesized AI Commentary (Local LLM)
* **Private & Offline:** Runs lightweight instruction-tuned models (like Qwen2.5 or Llama 3) entirely offline via Ollama.
* **Prompt Orchestration:** Constructs strict prompts combining the exact FEN, Stockfish's evaluation, and the retrieved book text. 
* **Human-Like Output:** Translates sterile engine variations (e.g., `+1.4 e4d5 exd5`) into pedagogical explanations citing the uploaded books.

---

## 🛠️ Recommended Tech Stack (Debian)

| Component | Tool / Technology | Purpose |
| :--- | :--- | :--- |
| **GUI & Database** | `scid-vs-pc` | PGN management, database searching, UI. |
| **Calculation Engine** | `stockfish` | Board evaluation and tactical calculation. |
| **Chess Logic** | `python-chess` | PGN parsing, FEN generation, UCI bridging. |
| **Vector DB (RAG)** | `chromadb` | Storing and searching chunked chess books. |
| **Local LLM Runner** | `ollama` | Running the commentary generation offline. |
| **Scripting / Glue** | `python3` | Tying the APIs, engines, and database together. |

