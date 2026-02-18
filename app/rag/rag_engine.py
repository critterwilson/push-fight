import os
from operator import itemgetter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

class PushFightRAG:
    def __init__(self, rules_path="assets/rules.md", model_name="llama3"):
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
            
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})

    def _build_chain(self):
        """Constructs the RAG chain."""
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        llm = ChatOllama(model=self.model_name, base_url=ollama_host)

        # The Prompt: Combines Rules (Context), Game State, and Question
        template = """You are the official AI Referee for the board game Push Fight.
        Your job is to enforce the rules strictly and explain strategic possibilities based on the current board state.
        
        ### Official Rules Context:
        {context}
        
        ### Current Game State:
        {game_state}
        
        ### User Question: 
        {question}
        
        ### Instructions:
        1. Answer based ONLY on the provided rules and game state.
        2. If a move is illegal, cite the specific rule section (e.g., "Section 3: Movement Restrictions").
        3. Be concise and authoritative.
        """
        
        prompt = ChatPromptTemplate.from_template(template)

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