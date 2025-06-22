Call Center RAG API
This is a FastAPI-based application that implements a Retrieval-Augmented Generation (RAG) pipeline for a call center, leveraging Groq for LLM and STT, Silero for TTS, and Chroma for vector storage. The API supports text queries, streaming responses, and voice interactions.
Prerequisites

Python 3.9+
Redis server running locally or accessible remotely
A valid Groq API key (obtain from xAI)
Access to a GPU (optional, for faster Silero TTS processing)

Setup Instructions

Clone the Repository
git clone <repository-url>
cd <repository-directory>


Create a Virtual Environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install Dependencies
Ensure you have a requirements.txt file with the necessary dependencies (see below for an example). Install them using:
pip install -r requirements.txt


Set Up Environment Variables
Create a .env file in the project root directory and add the following:
GROQ_API_KEY=your_groq_api_key_here
REDIS_HOST=localhost

Replace your_groq_api_key_here with your actual Groq API key. Adjust REDIS_HOST if your Redis server is not running locally.

Prepare the Vector Store
The application uses a Chroma vector store located at data/embeddings. You need to ingest documents into the vector store before running the API. If the directory does not exist or is empty, follow these steps:

Create a script to ingest documents (not provided in the code but required).
Run the ingestion script to populate the vector store.

Example placeholder command (replace with actual ingestion script):
python ingest_documents.py


Run the Application
Start the FastAPI server using Uvicorn:
uvicorn rag_pipeline:app --host 0.0.0.0 --port 8000

The API will be accessible at http://localhost:8000.


Example requirements.txt
Create a requirements.txt file with the following dependencies:
fastapi==0.115.0
uvicorn==0.30.6
langchain-chroma==0.1.4
langchain-huggingface==0.1.0
langchain-groq==0.2.0
groq==0.11.0
speechrecognition==3.10.4
torch==2.4.1
torchaudio==2.4.1
redis==5.0.8
pydantic==2.9.2
retrying==1.3.4
python-dotenv==1.0.1
numpy==1.26.4

Save this as requirements.txt in the project root.
API Endpoints

POST /query

Request: { "query": "your question", "customer_id": "optional_id" }
Response: JSON with response, sources, confidence, and model details
Example:curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "How do I return an item?", "customer_id": "user123"}'




POST /stream

Request: Same as /query
Response: Streaming text/event-stream
Example:curl -X POST http://localhost:8000/stream -H "Content-Type: application/json" -d '{"query": "How do I return an item?"}'




POST /voice

Request: Multipart form with a WAV audio file and optional customer_id
Response: JSON with transcription, agent response text, and base64-encoded audio response
Example:curl -X POST http://localhost:8000/voice -F "file=@sample.wav" -F "customer_id=user123"





Health Check
To verify the system status, run the following command after starting the server:
python main.py

This will initialize the pipeline, perform a health check, and print the status. Ensure all components (Groq LLM, STT, vector store, Redis) are operational before using the API.
Troubleshooting

Groq API Key Error: Ensure GROQ_API_KEY is set correctly in the .env file or environment.
Empty Vector Store: Run the document ingestion script to populate data/embeddings.
Redis Connection Error: Verify Redis is running and REDIS_HOST is correct.
TTS/STT Unavailable: Install torch, torchaudio, and speechrecognition as specified in requirements.txt.

Notes

The application uses the llama3-8b-8192 model by default for fast responses. For production, consider using gemma2-9b-it (see GROQ_MODELS in the code).
The vector store must be pre-populated with documents for the RAG pipeline to function.
Audio input for the /voice endpoint must be in WAV format.
Silero TTS requires significant memory; a GPU is recommended for performance.

License
This project is licensed under the MIT License.
