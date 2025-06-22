Database Design: Call Center Chatbot
2.1 Redis (Caching)

Purpose: Cache query results to reduce latency for repeated queries.
Host: localhost:6379 (configurable via REDIS_HOST).
Database: db=0.
Schema:
Key: query:{query}:{customer_id} (string)
Example: query:How do I return an item?:anonymous
Description: Unique identifier for query and customer.


Value: JSON string (serialized dictionary)
Structure:{
  "response": "string",
  "sources": [
    {
      "content": "string",
      "metadata": {"source": "string", "chunk_id": "string"},
      "relevance_score": float
    }
  ],
  "confidence": float,
  "model": "string",
  "provider": "string",
  "tokens_used": {}
}


Example:{
  "response": "To return an item, contact support within 30 days.",
  "sources": [
    {
      "content": "To return an item, contact support within 30 days...",
      "metadata": {"source": "faqs.txt", "chunk_id": "1"},
      "relevance_score": 0.85
    }
  ],
  "confidence": 0.85,
  "model": "llama3-8b-8192",
  "provider": "groq",
  "tokens_used": {}
}




TTL: 3600 seconds (1 hour).


Operations:
GET: Retrieve cached result.
SETEX: Store result with TTL.
PING: Check connection health.



2.2 Chroma (Vector Database)

Purpose: Store document embeddings for RAG retrieval.
Persist Directory: data/embeddings.
Collection: knowledge_base.
Schema:
Fields:
id: String (unique identifier, auto-generated).
Example: doc_1


embedding: Float vector (384 dimensions for sentence-transformers/all-MiniLM-L6-v2).
Example: [0.12, -0.45, ...]


document: String (text content).
Example: "To return an item, contact support within 30 days."


metadata: Dictionary.
Structure:{
  "source": "string",
  "chunk_id": "string"
}


Example:{
  "source": "faqs.txt",
  "chunk_id": "1"
}








Operations:
ADD: Insert documents with embeddings.
SIMILARITY_SEARCH_WITH_SCORE: Retrieve top-k documents (k=6) with relevance scores.
GET: Fetch all document IDs for health checks.


Indexing: Chroma handles vector indexing internally (e.g., HNSW).

2.3 Notes

Redis: Fixed Error 10061 by ensuring Redis server is running (redis-server).
Chroma: Populated via ingest_data.py with fine-tuned embeddings.
Scalability: Redis supports clustering; Chroma can scale with sharding.
