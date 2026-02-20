"""
Retrieval-Augmented Generation (RAG) pipeline for the Push Fight AI referee.

Uses LangChain to orchestrate:
  1. **Embedding & retrieval** — ``nomic-embed-text`` via Ollama embeds the
     game's Markdown rulebook into a ChromaDB vector store, then retrieves
     the top-*k* most relevant chunks for each question.
  2. **LLM generation** — ``llama3`` (configurable) via Ollama answers the
     question grounded in the retrieved context *and* a snapshot of the
     current board state, keeping the referee factual.

The pipeline is constructed once at startup (see :class:`PushFightRAG`) and
reused for every question via the LCEL ``chain.invoke()`` call.

Environment variables:
  - ``OLLAMA_HOST``  — Ollama server URL (default ``http://localhost:11434``)
  - ``CHROMA_HOST``  — Optional remote ChromaDB host for persistent storage
  - ``CHROMA_PORT``  — ChromaDB port (default ``8000``)
"""

import os
from operator import itemgetter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


class PushFightRAG:
    """
    RAG pipeline for answering Push Fight rules questions.

    On construction the class:
      1. Ingests the Markdown rulebook into a ChromaDB collection
         (or reuses an existing one).
      2. Builds an LCEL chain: question → retriever → prompt → LLM → answer.

    Attributes:
        model_name (str): Ollama model identifier for the chat LLM.
        rules_path (str): Filesystem path to the ``rules.md`` Markdown file.
        vector_store (Chroma): ChromaDB vector store holding rule embeddings.
        retriever: LangChain retriever (top-5 similarity search).
        chain: LCEL runnable that accepts ``{question, game_state}``
            and returns a plain-text answer string.
    """

    def __init__(self, rules_path="assets/rules.md", model_name="llama3"):
        """
        Initialise the RAG pipeline.

        Args:
            rules_path: Path to the Markdown rules file to ingest.
            model_name: Ollama model name for the chat LLM (e.g. ``"llama3"``).
        """
        self.model_name = model_name
        self.rules_path = rules_path
        self.vector_store = None
        self.retriever = None
        self.chain = None

        # Initialize the system — ingest rules, then wire the LCEL chain
        self._initialize_vector_store()
        self._build_chain()

    def _initialize_vector_store(self):
        """
        Ingest the Markdown rulebook and build the ChromaDB vector store.

        Three storage strategies are tried in order:
          1. **Remote Chroma** — if ``CHROMA_HOST`` is set, connect to a
             remote ChromaDB server and ingest if the collection is empty.
          2. **Local persistent Chroma** — if ``./chroma_db/`` already exists
             on disk, reuse it (no re-ingestion).
          3. **Fresh local Chroma** — read, split, embed the rules file and
             persist to ``./chroma_db/``.

        The rulebook is split by Markdown headers (#, ##, ###) so each
        chunk corresponds to a logical section of the rules.
        """
        persist_dir = "./chroma_db"
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        chroma_host = os.getenv("CHROMA_HOST")
        chroma_port = os.getenv("CHROMA_PORT", "8000")

        # Embedding model used for both ingestion and query-time retrieval
        embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=ollama_host
        )

        def ingest_docs(vector_store_cls, **kwargs):
            """Read the rules Markdown, split by headers, and embed into Chroma."""
            if not os.path.exists(self.rules_path):
                raise FileNotFoundError(f"Rules file not found at {self.rules_path}")

            with open(self.rules_path, "r") as f:
                rules_text = f.read()

            # Split on Markdown heading levels so each chunk is a coherent section
            headers_to_split_on = [
                ("#", "Title"),
                ("##", "Section"),
                ("###", "Subsection"),
            ]
            text_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
            chunks = text_splitter.split_text(rules_text)

            return vector_store_cls.from_documents(
                documents=chunks,
                embedding=embeddings,
                collection_name="push_fight_rules",
                **kwargs
            )

        # --- Strategy 1: Remote ChromaDB server ---
        if chroma_host:
            import chromadb
            client = chromadb.HttpClient(host=chroma_host, port=int(chroma_port))
            self.vector_store = Chroma(
                client=client,
                embedding_function=embeddings,
                collection_name="push_fight_rules"
            )
            # If the remote collection is empty, ingest the rulebook
            if self.vector_store._collection.count() == 0:
                self.vector_store = ingest_docs(Chroma, client=client)

        # --- Strategy 2: Existing local persistent DB ---
        elif os.path.exists(persist_dir):
            self.vector_store = Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings,
                collection_name="push_fight_rules"
            )

        # --- Strategy 3: Create a fresh local DB from the rulebook ---
        else:
            self.vector_store = ingest_docs(Chroma, persist_directory=persist_dir)

        # Retrieve the top 5 most relevant chunks for each query
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

    def _build_chain(self):
        """
        Construct the LCEL (LangChain Expression Language) RAG chain.

        The chain wiring::

            question ──► retriever ──► format_docs ──┐
            game_state ──────────────────────────────►├─► prompt ─► LLM ─► str
            question ────────────────────────────────►┘

        The system prompt instructs the LLM to act as a strict rules referee,
        answering only from the retrieved context and current board state.
        """
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        # LLM configuration — temperature=0 for deterministic, factual answers
        llm = ChatOllama(
            model=self.model_name,
            base_url=ollama_host,
            temperature=0,       # deterministic output for rule adjudication
            num_predict=300,     # cap response length to keep answers concise
        )

        # ── System prompt: establishes the referee persona and ground rules ──
        system_template = """You are the AI Referee for Push Fight: BJJ Edition, a two-player board game on a 10×4 grid.

GAME BASICS (always true):
- Each player has 5 pieces: 3 square pieces (sleeve, lapel, belt) and 2 round pieces (neck, joint).
- Only SQUARE pieces (sleeve, lapel, belt) can push. Round pieces (neck, joint) CANNOT push.
- Each turn: optionally move 0-2 pieces, then MUST push exactly once with a square piece.
- The anchor marks the last piece that pushed. The opponent cannot move or push the anchored piece.
- Win by pushing opponent's round piece off the board, OR pushing 2 of their square pieces off.
- Lose if you push your own piece off, or have no legal push at the start of your turn.

USING THE GAME STATE:
- The "Game State" section contains the current phase, piece positions, AND available actions.
- In Setup phase: refer to the placement status to tell the player what pieces they still need to place.
- In Move phase: use the "Valid moves" list to tell the player exactly where each piece can move.
- In Push phase: use the "Valid pushes" list to tell the player which pieces can push and in what directions.
- Never guess at valid moves or pushes — only report what is listed in the game state.

RULES:
1. Answer ONLY from the provided rules and game state. Never invent pieces, rules, or sections.
2. Use the actual piece names: sleeve, lapel, belt, neck, joint. Never say "Push piece" or "Player piece".
3. When citing rules, use the section titles from the provided context (e.g., "Pushing Rules and Restrictions").
4. Keep answers under 100 words. Be direct and factual.
5. For yes/no questions, start with "Yes" or "No" immediately."""

        # ── Human prompt template: injects retrieved rules + live board state ──
        human_template = """Rules Context:
{context}

Game State:
{game_state}

Question: {question}"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template),
        ])

        def format_docs(docs):
            """Join retrieved Document objects into a single context string."""
            return "\n\n".join(doc.page_content for doc in docs)

        # LCEL chain: parallel retrieval + passthrough → prompt → LLM → string
        self.chain = (
            {
                # Retrieve relevant rule chunks for the user's question
                "context": itemgetter("question") | self.retriever | format_docs,
                # Pass through the board state and question unchanged
                "game_state": itemgetter("game_state"),
                "question": itemgetter("question")
            }
            | prompt
            | llm
            | StrOutputParser()
        )

    def ask(self, question: str, game_state_info: str) -> str:
        """
        Run the full RAG pipeline for a single rules question.

        Args:
            question: The user's natural-language question.
            game_state_info: Plain-text snapshot of the board (produced by
                :func:`~app.rag.state_formatter.format_game_state`).

        Returns:
            The referee's answer as a plain string (≤ 300 tokens).
        """
        return self.chain.invoke({
            "question": question,
            "game_state": game_state_info
        })