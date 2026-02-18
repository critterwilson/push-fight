import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.rag.rag_engine import PushFightRAG

class TestPushFightRAG(unittest.TestCase):
    @patch('app.rag.rag_engine.Chroma')
    @patch('app.rag.rag_engine.OllamaEmbeddings')
    @patch('app.rag.rag_engine.ChatOllama')
    @patch('app.rag.rag_engine.MarkdownHeaderTextSplitter')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="# Rules")
    @patch('os.path.exists')
    def test_initialization_new_db(self, mock_exists, mock_open, mock_splitter, mock_chat, mock_embeddings, mock_chroma):
        """Test RAG initialization when no DB exists (ingestion path)."""
        # Setup mocks
        # We want persist_dir (./chroma_db) to return False (not found)
        # We want rules_path to return True (found)
        def exists_side_effect(path):
            if "chroma_db" in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect
        
        # Setup Splitter mock
        mock_splitter_instance = mock_splitter.return_value
        mock_splitter_instance.split_text.return_value = ["chunk1", "chunk2"]
        
        # Setup Chroma mock
        mock_chroma_instance = MagicMock()
        mock_chroma.from_documents.return_value = mock_chroma_instance
        
        # Initialize RAG
        rag = PushFightRAG(rules_path="dummy_rules.md")
        
        # Verify embeddings init
        mock_embeddings.assert_called_once()
        
        # Verify file read
        mock_open.assert_called_with("dummy_rules.md", "r")
        
        # Verify splitting
        mock_splitter_instance.split_text.assert_called()
        
        # Verify Chroma creation from documents
        mock_chroma.from_documents.assert_called_once()
        
    @patch('app.rag.rag_engine.Chroma')
    @patch('app.rag.rag_engine.OllamaEmbeddings')
    @patch('app.rag.rag_engine.ChatOllama')
    @patch('os.path.exists')
    def test_initialization_existing_db(self, mock_exists, mock_chat, mock_embeddings, mock_chroma):
        """Test RAG initialization when DB already exists (loading path)."""
        # persist_dir exists
        mock_exists.return_value = True
        
        rag = PushFightRAG()
        
        # Verify Chroma loaded from disk, not created from docs
        mock_chroma.assert_called_once()
        mock_chroma.from_documents.assert_not_called()

    @patch('app.rag.rag_engine.Chroma')
    @patch('app.rag.rag_engine.OllamaEmbeddings')
    @patch('app.rag.rag_engine.ChatOllama')
    @patch('os.path.exists')
    def test_ask(self, mock_exists, mock_chat, mock_embeddings, mock_chroma):
        """Test the ask method invokes the chain correctly."""
        mock_exists.return_value = True
        
        rag = PushFightRAG()
        
        # Mock the chain invocation
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