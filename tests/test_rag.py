"""
Tests for the PushFightRAG retrieval-augmented generation engine (app.rag.rag_engine).

The RAG system provides an AI "referee" that answers player questions about
Push Fight rules. It uses LangChain with Ollama embeddings, a Chroma vector
store, and ChatOllama for LLM responses. The RAG engine has two initialization
paths:
  1. **New DB** (ingestion): reads a rules Markdown file, splits it into chunks,
     creates embeddings, and persists a new Chroma database.
  2. **Existing DB** (loading): loads the previously persisted Chroma database
     from disk, skipping the ingestion step.

Testing strategy:
  - All external dependencies (Chroma, OllamaEmbeddings, ChatOllama,
    MarkdownHeaderTextSplitter, file I/O, os.path.exists) are fully mocked.
    No Ollama server, no Chroma database, and no filesystem access is needed.
  - The ingestion path is tested by making os.path.exists return False for
    the chroma_db directory, forcing the RAG to read and split the rules file.
  - The loading path is tested by making os.path.exists return True,
    verifying that Chroma is loaded from disk (not from_documents).
  - The ask() method is tested by mocking the LangChain chain invocation
    and verifying it receives the correct question and game_state arguments.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure we can import from app regardless of CWD.
sys.path.append(os.getcwd())

from app.rag.rag_engine import PushFightRAG


class TestPushFightRAG(unittest.TestCase):
    """Tests for PushFightRAG initialization (ingestion vs. loading) and
    the ask() query method.

    Every test in this class uses @patch decorators to mock all external
    dependencies, ensuring tests run fast and offline.
    """

    @patch('app.rag.rag_engine.Chroma')
    @patch('app.rag.rag_engine.OllamaEmbeddings')
    @patch('app.rag.rag_engine.ChatOllama')
    @patch('app.rag.rag_engine.MarkdownHeaderTextSplitter')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="# Rules")
    @patch('os.path.exists')
    def test_initialization_new_db(self, mock_exists, mock_open, mock_splitter, mock_chat, mock_embeddings, mock_chroma):
        """Test the ingestion path: when no Chroma DB exists on disk, the RAG
        engine must read the rules file, split it into chunks, create embeddings,
        and build a new Chroma database from documents.

        Mocks:
          - os.path.exists: returns False for chroma_db paths, True otherwise.
          - builtins.open: returns "# Rules" as the rules file content.
          - MarkdownHeaderTextSplitter: returns two dummy chunks.
          - Chroma.from_documents: captures the creation call.
        """
        # os.path.exists returns False for chroma_db (triggers ingestion),
        # True for the rules file path.
        def exists_side_effect(path):
            if "chroma_db" in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect

        # Configure the text splitter to return dummy chunks
        mock_splitter_instance = mock_splitter.return_value
        mock_splitter_instance.split_text.return_value = ["chunk1", "chunk2"]

        # Configure Chroma mock
        mock_chroma_instance = MagicMock()
        mock_chroma.from_documents.return_value = mock_chroma_instance

        # Initialize RAG — should trigger ingestion
        rag = PushFightRAG(rules_path="dummy_rules.md")

        # Verify the full ingestion pipeline was executed
        mock_embeddings.assert_called_once()
        mock_open.assert_called_with("dummy_rules.md", "r")
        mock_splitter_instance.split_text.assert_called()
        mock_chroma.from_documents.assert_called_once()

    @patch('app.rag.rag_engine.Chroma')
    @patch('app.rag.rag_engine.OllamaEmbeddings')
    @patch('app.rag.rag_engine.ChatOllama')
    @patch('os.path.exists')
    def test_initialization_existing_db(self, mock_exists, mock_chat, mock_embeddings, mock_chroma):
        """Test the loading path: when a Chroma DB already exists on disk,
        the RAG engine must load it directly without re-ingesting the rules.

        Mocks:
          - os.path.exists: returns True (DB exists).
        """
        mock_exists.return_value = True

        rag = PushFightRAG()

        # Chroma constructor called (loading from disk), but from_documents NOT called
        mock_chroma.assert_called_once()
        mock_chroma.from_documents.assert_not_called()

    @patch('app.rag.rag_engine.Chroma')
    @patch('app.rag.rag_engine.OllamaEmbeddings')
    @patch('app.rag.rag_engine.ChatOllama')
    @patch('os.path.exists')
    def test_ask(self, mock_exists, mock_chat, mock_embeddings, mock_chroma):
        """Test that ask() passes the question and game_state to the LangChain
        chain and returns the chain's response verbatim.

        Mocks:
          - rag.chain.invoke: returns a canned "AI Response" string.
        """
        mock_exists.return_value = True

        rag = PushFightRAG()

        # Replace the chain with a mock and verify invocation
        rag.chain = MagicMock()
        rag.chain.invoke.return_value = "AI Response"

        response = rag.ask("Question", "Game State")

        rag.chain.invoke.assert_called_with({
            "question": "Question",
            "game_state": "Game State"
        })
        self.assertEqual(response, "AI Response")


if __name__ == '__main__':
    unittest.main()