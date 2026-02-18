import threading
from app.rag.rag_engine import PushFightRAG
from app.rag.state_formatter import format_game_state

class AIInterface:
    """
    Singleton interface for the UI to interact with the RAG engine asynchronously.
    Ensures the UI main loop is never blocked by heavy LLM operations.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIInterface, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.rag_engine = None
        self.is_ready = False
        self.loading_error = None
        self._initialized = True
        
        # Start loading in a separate thread to avoid blocking UI startup
        self.load_thread = threading.Thread(target=self._load_engine, daemon=True)
        self.load_thread.start()

    def _load_engine(self):
        try:
            # Initialize the heavy RAG engine
            self.rag_engine = PushFightRAG()
            self.is_ready = True
        except Exception as e:
            self.loading_error = str(e)
            print(f"Error loading AI Engine: {e}")

    def ask_question(self, game_state, question, callback):
        """
        Submits a question to the AI.
        
        Args:
            game_state: The current GameState object.
            question (str): The user's question.
            callback (func): A function that accepts a string (the answer).
                             This will be called from a background thread when ready.
        """
        if not self.is_ready:
            if self.loading_error:
                callback(f"System Error: AI failed to initialize. {self.loading_error}")
            else:
                callback("System: AI is warming up... please try again in a moment.")
            return

        def _query_task():
            try:
                context = format_game_state(game_state)
                answer = self.rag_engine.ask(question, context)
                callback(answer)
            except Exception as e:
                callback(f"System Error: Failed to get answer. {e}")

        # Run query in background thread
        query_thread = threading.Thread(target=_query_task, daemon=True)
        query_thread.start()