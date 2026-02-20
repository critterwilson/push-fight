import os
from operator import itemgetter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

class PushFightRAG:
    def __init__(self, rules_path="assets/rules.md", model_name="llama3.2:1b"):
        self.model_name = model_name
        self.rules_path = rules_path
        self.vector_store = None
        self.retriever = None
        self.chain = None
        
        # Initialize the system
        self._initialize_vector_store()
        self._build_chain()

    def _initialize_vector_store(self):
        """Ingests rules.txt, chunks it, and stores embeddings in ChromaDB."""
        persist_dir = "./chroma_db"
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        chroma_host = os.getenv("CHROMA_HOST")
        chroma_port = os.getenv("CHROMA_PORT", "8000")
        
        embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=ollama_host
        )

        # Helper to ingest data
        def ingest_docs(vector_store_cls, **kwargs):
            if not os.path.exists(self.rules_path):
                raise FileNotFoundError(f"Rules file not found at {self.rules_path}")
            
            with open(self.rules_path, "r") as f:
                rules_text = f.read()

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

        if chroma_host:
            import chromadb
            client = chromadb.HttpClient(host=chroma_host, port=int(chroma_port))
            self.vector_store = Chroma(
                client=client,
                embedding_function=embeddings,
                collection_name="push_fight_rules"
            )
            # If collection is empty, ingest data
            if self.vector_store._collection.count() == 0:
                self.vector_store = ingest_docs(Chroma, client=client)

        elif os.path.exists(persist_dir):
            # Load existing DB
            self.vector_store = Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings,
                collection_name="push_fight_rules"
            )
        else:
            # Create new DB
            self.vector_store = ingest_docs(Chroma, persist_directory=persist_dir)
            
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

    def _build_chain(self):
        """Constructs the RAG chain."""
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        llm = ChatOllama(
            model=self.model_name,
            base_url=ollama_host,
            temperature=0,
            num_predict=300,
        )

        system_template = """You are the AI Referee for Push Fight: BJJ Edition, a two-player board game on a 10×4 grid.

GAME BASICS (always true):
- Each player has 5 pieces: 3 square pieces (sleeve, lapel, belt) and 2 round pieces (neck, joint).
- Only SQUARE pieces (sleeve, lapel, belt) can push. Round pieces (neck, joint) CANNOT push.
- Each turn: optionally move 0-2 pieces, then MUST push exactly once with a square piece.
- The anchor marks the last piece that pushed. The opponent cannot move or push the anchored piece.
- Win by pushing opponent's round piece off the board, OR pushing 2 of their square pieces off.
- Lose if you push your own piece off, or have no legal push at the start of your turn.

RULES:
1. Answer ONLY from the provided rules and game state. Never invent pieces, rules, or sections.
2. Use the actual piece names: sleeve, lapel, belt, neck, joint. Never say "Push piece" or "Player piece".
3. When citing rules, use the section titles from the provided context (e.g., "Pushing Rules and Restrictions").
4. Keep answers under 100 words. Be direct and factual.
5. For yes/no questions, start with "Yes" or "No" immediately."""

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
            return "\n\n".join(doc.page_content for doc in docs)

        self.chain = (
            {
                "context": itemgetter("question") | self.retriever | format_docs,
                "game_state": itemgetter("game_state"),
                "question": itemgetter("question")
            }
            | prompt
            | llm
            | StrOutputParser()
        )

    def ask(self, question: str, game_state_info: str) -> str:
        """
        Ask a question about the current game.
        
        Args:
            question: The user's query.
            game_state_info: A string representation of the board/game (JSON or ASCII).
        """
        return self.chain.invoke({
            "question": question,
            "game_state": game_state_info
        })