Call Center Chatbot Requirements
1.1 Functional Requirements

Text Query Processing: Handle customer text queries via a /query endpoint, retrieving relevant answers from a knowledge base using RAG.
Voice Query Processing: Support voice input/output via a /voice endpoint, converting audio to text (STT) and responses to audio (TTS).
Streaming Responses: Provide real-time response streaming via a /stream endpoint for text queries.
Knowledge Base: Store and retrieve FAQs/documents in a vector database (Chroma) for RAG.
Caching: Cache query results in Redis to reduce latency for repeated queries.
Context-Aware Responses: Use conversation history (via ConversationBufferMemory) for contextual responses.
Fine-Tuning: Fine-tune the embedding model (sentence-transformers/all-MiniLM-L6-v2) to improve retrieval accuracy for call center-specific queries.
Health Check: Provide a /health endpoint to verify system status (Groq, Redis, Chroma, STT, TTS).

1.2 Non-Functional Requirements

Performance: Response time < 2 seconds for text queries, < 5 seconds for voice queries.
Scalability: Handle up to 100 concurrent users.
Reliability: 99.9% uptime, with retry logic for API failures.
Security: Validate Groq API key and secure Redis connections.
Portability: Run on Windows (e.g., C:\Users\Asus\Downloads\call_center_agent) with Python 3.8+.
Maintainability: Modular code with logging and unit tests.

1.3 Constraints

Use Groq API for LLM (e.g., llama3-8b-8192).
Use speech_recognition for STT (replacing Vosk due to model path errors).
Use Silero for TTS, fixing tuple error.
Use Redis for caching and Chroma for vector storage.
Fine-tune embeddings locally or on a cloud platform with limited GPU resources.
