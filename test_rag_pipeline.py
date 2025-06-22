import unittest
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import wave
from rag_pipeline import GroqRAGPipeline, QueryRequest, app, SPEECH_RECOGNITION_AVAILABLE, TORCH_AVAILABLE

class TestGroqRAGPipeline(unittest.TestCase):
    def setUp(self):
        # Set environment variable for Groq API key
        os.environ["GROQ_API_KEY"] = "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"
        
        # Mock external dependencies
        self.mock_groq = patch("rag_pipeline.ChatGroq").start()
        self.mock_groq_instance = MagicMock()
        self.mock_groq.return_value = self.mock_groq_instance
        self.mock_groq_instance.invoke.return_value = MagicMock(content="Mocked response")
        
        self.mock_redis = patch("rag_pipeline.redis.Redis").start()
        self.mock_redis_instance = MagicMock()
        self.mock_redis.return_value = self.mock_redis_instance
        
        self.mock_chroma = patch("rag_pipeline.Chroma").start()
        self.mock_chroma_instance = MagicMock()
        self.mock_chroma.return_value = self.mock_chroma_instance
        self.mock_chroma_instance.similarity_search_with_score.return_value = [
            (MagicMock(page_content="Test document", metadata={"source": "faqs.txt"}), 0.15)
        ]
        self.mock_chroma_instance.get.return_value = {"ids": ["doc_1"]}
        
        self.mock_speech_recognizer = patch("rag_pipeline.sr.Recognizer").start()
        self.mock_speech_recognizer_instance = MagicMock()
        self.mock_speech_recognizer.return_value = self.mock_speech_recognizer_instance
        self.mock_speech_recognizer_instance.recognize_google.return_value = "Test query"
        
        self.mock_torch_hub = patch("rag_pipeline.torch.hub.load").start()
        self.mock_silero_model = MagicMock()
        self.mock_torch_hub.return_value = [self.mock_silero_model]
        self.mock_silero_model.apply_tts.return_value = MagicMock(numpy=MagicMock(return_value=MagicMock(tobytes=MagicMock(return_value=b"audio_data"))))
        
        # Initialize pipeline and FastAPI client
        self.rag = GroqRAGPipeline(model_name="llama3-8b-8192")
        self.client = TestClient(app)
        
        # Create temporary directories
        os.makedirs("data/embeddings", exist_ok=True)
        os.makedirs("data/fine_tuned_embeddings", exist_ok=True)
    
    def tearDown(self):
        # Clean up mocks
        patch.stopall()
        
        # Remove temporary files
        if os.path.exists("test.wav"):
            os.remove("test.wav")
        if os.path.exists("data/embeddings"):
            import shutil
            shutil.rmtree("data/embeddings")
        if os.path.exists("data/fine_tuned_embeddings"):
            import shutil
            shutil.rmtree("data/fine_tuned_embeddings")
    
    def test_health_check(self):
        """Test health check endpoint and component status."""
        with self.subTest("Health check structure"):
            health = self.rag.health_check()
            self.assertIsInstance(health, dict)
            self.assertIn("groq_connection", health)
            self.assertIn("vector_store", health)
            self.assertIn("qa_chain", health)
            self.assertIn("redis_connection", health)
            self.assertIn("tts_available", health)
            self.assertIn("stt_available", health)
        
        with self.subTest("Health endpoint"):
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertIsInstance(response.json(), dict)
    
    def test_process_query(self):
        """Test query processing with various inputs."""
        test_cases = [
            ("How do I return an item?", "test_user", 200, True),
            ("", "test_user", 200, False),  # Empty query
            ("How do I return an item?", "", 200, True),  # Empty customer ID
        ]
        
        for query, customer_id, expected_status, expect_response in test_cases:
            with self.subTest(query=query, customer_id=customer_id):
                result = self.rag.process_query(query, customer_id)
                self.assertIsInstance(result, dict)
                self.assertIn("response", result)
                self.assertIn("sources", result)
                self.assertIn("confidence", result)
                if expect_response:
                    self.assertGreater(len(result["response"]), 0)
                else:
                    self.assertIn("error", result)
    
    def test_query_endpoint(self):
        """Test /query endpoint with valid and invalid inputs."""
        test_cases = [
            ({"query": "How do I return an item?", "customer_id": "test_user"}, 200),
            ({"query": "", "customer_id": "test_user"}, 200),  # Empty query
            ({"query": "Test"}, 422),  # Missing customer_id
        ]
        
        for payload, expected_status in test_cases:
            with self.subTest(payload=payload):
                response = self.client.post("/query", json=payload)
                self.assertEqual(response.status_code, expected_status)
                if expected_status == 200:
                    self.assertIn("response", response.json())
    
    def test_stream_endpoint(self):
        """Test /stream endpoint for streaming responses."""
        payload = {"query": "How do I return an item?", "customer_id": "test_user"}
        response = self.client.post("/stream", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.startswith("data:"))
        
        # Test empty query
        response = self.client.post("/stream", json={"query": "", "customer_id": "test_user"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("data: System not ready", response.text)
    
    def test_speech_to_text(self):
        """Test speech-to-text functionality with valid and invalid audio."""
        if SPEECH_RECOGNITION_AVAILABLE:
            # Create a dummy WAV file
            with wave.open("test.wav", "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\x00" * 16000)
            
            with open("test.wav", "rb") as f:
                audio = f.read()
            
            with self.subTest("Valid audio"):
                text = self.rag.speech_to_text(audio)
                self.assertIsInstance(text, str)
                self.assertEqual(text, "Test query")
            
            with self.subTest("Invalid audio"):
                with self.assertRaises(Exception):
                    self.rag.speech_to_text(b"invalid_audio")
            
            os.remove("test.wav")
    
    def test_text_to_speech(self):
        """Test text-to-speech functionality with valid and invalid text."""
        if TORCH_AVAILABLE and self.rag.silero_model:
            with self.subTest("Valid text"):
                audio = self.rag.text_to_speech("Test response")
                self.assertIsInstance(audio, bytes)
                self.assertGreater(len(audio), 0)
            
            with self.subTest("Empty text"):
                with self.assertRaises(Exception):
                    self.rag.text_to_speech("")
    
    def test_fine_tuned_embeddings(self):
        """Test initialization with fine-tuned embeddings."""
        # Simulate fine-tuned embeddings directory
        with open("data/fine_tuned_embeddings/config.json", "w") as f:
            json.dump({"model_name": "fine_tuned_model"}, f)
        
        rag = GroqRAGPipeline(model_name="llama3-8b-8192")
        self.assertIsNotNone(rag.embeddings)
        self.assertIsNotNone(rag.vector_store)
    
    def test_redis_cache(self):
        """Test Redis caching behavior."""
        query = "How do I return an item?"
        customer_id = "test_user"
        cache_key = f"query:{query}:{customer_id}"
        mock_result = {"response": "Cached response", "sources": [], "confidence": 0.8}
        
        # Simulate cache hit
        self.mock_redis_instance.get.return_value = json.dumps(mock_result)
        result = self.rag.process_query(query, customer_id)
        self.assertEqual(result["response"], "Cached response")
        
        # Simulate cache miss
        self.mock_redis_instance.get.return_value = None
        result = self.rag.process_query(query, customer_id)
        self.mock_redis_instance.setex.assert_called_with(cache_key, 3600, json.dumps(result))
    
    def test_error_handling(self):
        """Test error handling for invalid API key and empty vector store."""
        with self.subTest("Invalid API key"):
            os.environ["GROQ_API_KEY"] = ""
            with self.assertRaises(ValueError):
                GroqRAGPipeline(model_name="llama3-8b-8192")
        
        with self.subTest("Empty vector store"):
            self.mock_chroma_instance.get.return_value = {"ids": []}
            rag = GroqRAGPipeline(model_name="llama3-8b-8192")
            result = rag.process_query("Test query", "test_user")
            self.assertIn("System not ready", result["response"])

if __name__ == "__main__":
    unittest.main()