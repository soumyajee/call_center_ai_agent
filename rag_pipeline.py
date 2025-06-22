import logging
import os
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from io import BytesIO
from langchain_chroma import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from retrying import retry
import redis
import json
import wave
import numpy as np
import traceback
import re
import base64 # <-- ADD THIS IMPORT

try:
    from langchain_groq import ChatGroq
    from groq import Groq as GroqClient
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Install Groq: pip install langchain-groq groq")

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("Install speech_recognition: pip install SpeechRecognition")

try:
    import torch
    import torchaudio
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Install torch and torchaudio: pip install torch torchaudio")

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Call Center RAG API")

class QueryRequest(BaseModel):
    query: str
    customer_id: str = "anonymous"

# --- HELPER FUNCTION FOR TEXT CHUNKING ---
def split_text_into_chunks(text: str, max_chunk_len: int = 450) -> list[str]:
    """
    Splits text into chunks by sentences, trying to keep chunks below max_chunk_len.
    This helps prevent TTS models from failing on overly long inputs.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text) 
    
    chunks = []
    current_chunk_sentences = []
    current_chunk_len = 0

    for sentence in sentences:
        if current_chunk_len + len(sentence) + (1 if current_chunk_sentences else 0) <= max_chunk_len:
            current_chunk_sentences.append(sentence)
            current_chunk_len += len(sentence) + (1 if current_chunk_sentences else 0)
        else:
            if current_chunk_sentences:
                chunks.append(" ".join(current_chunk_sentences).strip())
            
            current_chunk_sentences = [sentence]
            current_chunk_len = len(sentence)

    if current_chunk_sentences:
        chunks.append(" ".join(current_chunk_sentences).strip())
        
    return chunks
# --- END OF HELPER FUNCTION ---


class GroqRAGPipeline:
    """RAG Pipeline optimized for Groq with Groq STT and Silero TTS."""
    
    def __init__(self, model_name: str = "llama3-8b-8192", api_key: str = None):
        if not GROQ_AVAILABLE:
            raise ImportError("Groq not available. Install with: pip install langchain-groq groq")
        
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY environment variable or pass api_key.")
        logger.debug(f"Using Groq API key: {self.api_key[:4]}...{self.api_key[-4:]}")
        
        self.model_name = model_name
        self.embeddings = None
        self.vector_store = None
        self.llm = None
        self.qa_chain = None
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="result"
        )
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=6379,
            db=0,
            decode_responses=True
        )
        # Initialize Silero TTS
        self.silero_model = None
        self.silero_speaker = 'en_0'
        if TORCH_AVAILABLE:
            try:
                silero = torch.hub.load('snakers4/silero-models', 'silero_tts', language='en', speaker='v3_en')
                self.silero_model = silero[0]
                logger.info("Silero TTS initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Silero TTS: {str(e)}\n{traceback.format_exc()}")
        
        # Initialize Groq client for STT
        self.groq_stt_client = None
        if GROQ_AVAILABLE:
            try:
                self.groq_stt_client = GroqClient(api_key=self.api_key)
                logger.info("Groq STT client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Groq STT client: {str(e)}\n{traceback.format_exc()}")
        
        self.initialize_components()
    
    def initialize_components(self):
        logger.info(f"Initializing Groq RAG Pipeline with model: {self.model_name}")
        
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            logger.info("Embeddings initialized")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}\n{traceback.format_exc()}")
            raise
        
        try:
            self.llm = ChatGroq(
                groq_api_key=self.api_key,
                model_name=self.model_name,
                temperature=0.7,
                max_tokens=300, # Constrain LLM output
                model_kwargs={"top_p": 0.9},
                streaming=False
            )
            logger.info("Groq LLM initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Groq LLM: {e}\n{traceback.format_exc()}")
            raise
        
        self.load_vector_store()
        self.initialize_qa_chain()
        logger.info("Groq RAG Pipeline initialized successfully")
    
    def load_vector_store(self):
        persist_directory = "data/embeddings"
        
        if os.path.exists(persist_directory):
            try:
                self.vector_store = Chroma(
                    persist_directory=persist_directory,
                    embedding_function=self.embeddings,
                    collection_name="knowledge_base"
                )
                doc_count = len(self.vector_store.get()["ids"])
                logger.info(f"Loaded vector store with {doc_count} documents")
                if doc_count == 0:
                    logger.warning("Vector store is empty. Run data ingestion.")
            except Exception as e:
                logger.error(f"Failed to load vector store: {e}\n{traceback.format_exc()}")
                self.vector_store = None
        else:
            logger.warning("Vector store directory not found. Run data ingestion.")
            self.vector_store = None
    
    def initialize_qa_chain(self):
        if not self.vector_store:
            logger.error("Cannot initialize QA chain without vector store")
            return
        
        prompt_template = """You are a professional call center agent. Use the provided context to answer the customer's question accurately and helpfully. If no context is available, provide a general response and offer further assistance.

Context Information:
{context}

Customer Question: {question}

Instructions:
- Be concise and to the point. Aim for answers that are no more than 2-3 sentences. # Refined prompt
- Use a friendly, professional tone.
- If the context doesn't contain the answer, say so politely.
- Offer to help further if needed.

Response:"""
        
        try:
            PROMPT = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )
            
            retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 6}
            )
            
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                chain_type_kwargs={"prompt": PROMPT},
                return_source_documents=True
            )
            logger.info("Groq QA chain initialized")
        except Exception as e:
            logger.error(f"Failed to initialize QA chain: {e}\n{traceback.format_exc()}")
            self.qa_chain = None
    
    @retry(stop_max_attempt_number=5, wait_exponential_multiplier=2000)
    def invoke_llm(self, prompt):
        return self.llm.invoke(prompt)
    
    def process_query(self, query: str, customer_id: str = "anonymous", min_score: float = 0.2) -> Dict[str, Any]:
        cache_key = f"query:{query}:{customer_id}"
        cached = None
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.info("Cache hit")
                return json.loads(cached)
        except redis.ConnectionError as e:
            logger.warning(f"Redis unavailable, skipping cache: {e}")
            cached = None
        
        if not self.qa_chain:
            logger.error("QA chain not initialized")
            return {
                "response": "System not ready. Please ensure knowledge base is loaded.",
                "sources": [],
                "confidence": 0.0,
                "model": self.model_name
            }
        
        try:
            logger.info(f"Processing query: {query}")
            docs_with_scores = self.vector_store.similarity_search_with_score(query, k=6)
            logger.info(f"Raw scores: {[score for _, score in docs_with_scores]}")
            filtered_docs = [doc for doc, score in docs_with_scores if (1 - score) >= min_score]
            normalized_scores = [1 - score for _, score in docs_with_scores if (1 - score) >= min_score]
            logger.info(f"Retrieved {len(docs_with_scores)} documents, {len(filtered_docs)} after score filter (min_score={min_score})")
            
            result = self.qa_chain.invoke({"query": query})
            response = result["result"]
            source_docs = result.get("source_documents", [])
            
            sources = []
            for doc in source_docs:
                score = next((1 - s for d, s in docs_with_scores if d.page_content == doc.page_content), 0.0)
                if score >= min_score:
                    sources.append({
                        "content": doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content,
                        "metadata": doc.metadata,
                        "relevance_score": score
                    })
            
            confidence = min(len(sources) * 0.25, 1.0)
            if sources:
                avg_score = sum(source["relevance_score"] for source in sources) / len(sources)
                confidence = max(confidence, min(avg_score, 1.0))
            
            result_dict = {
                "response": response,
                "sources": sources,
                "confidence": confidence,
                "model": self.model_name,
                "provider": "groq",
                "tokens_used": getattr(result, 'token_usage', {})
            }
            
            if not cached:
                try:
                    self.redis_client.setex(cache_key, 3600, json.dumps(result_dict))
                except redis.ConnectionError as e:
                    logger.warning(f"Failed to cache result: {e}")
            
            return result_dict
            
        except Exception as e:
            error_detail = f"Groq processing error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_detail)
            return {
                "response": "I apologize, but I'm experiencing technical difficulties. Please try again.",
                "sources": [],
                "confidence": 0.0,
                "model": self.model_name,
                "error": error_detail
            }
    
    def stream_response(self, query: str, customer_id: str = "anonymous", min_score: float = 0.2):
        if not self.qa_chain:
            yield "data: System not ready.\n\n"
            return
        
        try:
            logger.info(f"Streaming response for query: {query}")
            self.llm.streaming = True
            
            docs_with_scores = self.vector_store.similarity_search_with_score(query, k=3)
            logger.info(f"Raw scores: {[score for _, score in docs_with_scores]}")
            filtered_docs = [doc for doc, score in docs_with_scores if (1 - score) >= min_score]
            context = "\n".join([doc.page_content for doc in filtered_docs])
            logger.info(f"Retrieved {len(docs_with_scores)} documents, {len(filtered_docs)} after score filter for streaming")
            
            prompt = f"""Context: {context}
            
Customer Question: {query}

Response:"""
            
            for chunk in self.llm.stream(prompt):
                yield f"data: {chunk.content}\n\n"
                
        except Exception as e:
            error_detail = f"Streaming error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_detail)
            yield f"data: Error: {error_detail}\n\n"
    
    def speech_to_text(self, audio: bytes) -> str:
        if not self.groq_stt_client:
            raise HTTPException(
                status_code=503,
                detail="Speech-to-text unavailable: Groq STT client not initialized."
            )
        
        try:
            audio_file_like = BytesIO(audio)
            audio_file_like.name = "audio.wav"
            
            transcription = self.groq_stt_client.audio.transcriptions.create(
                file=audio_file_like,
                model="whisper-large-v3-turbo" 
            )
            
            result_text = transcription.text
            logger.info(f"Transcribed audio with Groq Whisper: {result_text}")
            return result_text
        except Exception as e:
            error_detail = f"Groq STT error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_detail)
            raise HTTPException(status_code=500, detail=error_detail)
    
    def text_to_speech(self, text: str, speaker: str = None) -> bytes:
        if not self.silero_model:
            raise HTTPException(status_code=503, detail="Text-to-speech unavailable: Silero model not initialized.")
        
        try:
            speaker = speaker or self.silero_speaker
            supported_sample_rate = 24000 
            
            silero_max_chars = 450 
            
            if len(text) > silero_max_chars:
                text_chunks = split_text_into_chunks(text, max_chunk_len=silero_max_chars)
                logger.info(f"Text too long ({len(text)} chars), splitting into {len(text_chunks)} chunks for TTS.")
            else:
                text_chunks = [text]
            
            full_audio_buffer = BytesIO() 
            
            with wave.open(full_audio_buffer, "wb") as wav_writer:
                wav_writer.setnchannels(1)
                wav_writer.setsampwidth(2)
                wav_writer.setframerate(supported_sample_rate)

                for i, chunk in enumerate(text_chunks):
                    if not chunk.strip():
                        continue
                    logger.debug(f"Generating TTS for chunk {i+1}/{len(text_chunks)} (length: {len(chunk)}): '{chunk[:70]}...'")
                    
                    try:
                        chunk_audio = self.silero_model.apply_tts(
                            text=chunk, 
                            speaker=speaker, 
                            sample_rate=supported_sample_rate
                        )
                        audio_np = (chunk_audio * 32767).numpy().astype(np.int16)
                        wav_writer.writeframes(audio_np.tobytes())
                    except Exception as chunk_e:
                        logger.error(f"Silero TTS failed for chunk '{chunk[:50]}...': {str(chunk_e)}")
                        raise Exception(f"Failed to generate speech for a segment: {str(chunk_e)}") from chunk_e

            logger.info(f"Generated complete speech for text: {text[:50]}... (total audio length: {full_audio_buffer.tell()} bytes)")
            return full_audio_buffer.getvalue()

        except Exception as e:
            error_detail = f"Speech generation error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_detail)
            raise HTTPException(status_code=500, detail=error_detail)
    
    def health_check(self) -> Dict[str, Any]:
        groq_llm_status = False
        try:
            test_response = self.invoke_llm("Hello")
            groq_llm_status = True
            logger.info("Groq LLM connection test successful")
        except Exception as e:
            logger.error(f"Groq LLM health check failed: {str(e)}\n{traceback.format_exc()}")

        groq_stt_status = False
        if self.groq_stt_client:
            try:
                groq_stt_status = True 
                logger.info("Groq STT client available")
            except Exception as e:
                logger.error(f"Groq STT client health check failed: {str(e)}\n{traceback.format_exc()}")
        
        doc_count = 0
        if self.vector_store:
            try:
                doc_count = len(self.vector_store.get()["ids"])
            except Exception as e:
                logger.error(f"Failed to get document count: {e}\n{traceback.format_exc()}")
                doc_count = "unknown"
        
        redis_status = False
        try:
            self.redis_client.ping()
            redis_status = True
            logger.info("Redis connection test successful")
        except redis.ConnectionError as e:
            logger.warning(f"Redis health check failed: {e}")
        
        return {
            "groq_llm_connection": groq_llm_status,
            "groq_stt_connection": groq_stt_status and GROQ_AVAILABLE,
            "vector_store": self.vector_store is not None,
            "qa_chain": self.qa_chain is not None,
            "tts_available": self.silero_model is not None and TORCH_AVAILABLE,
            "stt_available": self.groq_stt_client is not None,
            "redis_connection": redis_status,
            "model": self.model_name,
            "document_count": doc_count,
            "api_key_set": bool(self.api_key),
            "all_systems_operational": all([
                groq_llm_status,
                groq_stt_status,
                self.vector_store is not None,
                self.qa_chain is not None,
                doc_count != 0
            ])
        }

# FastAPI Endpoints
@app.post("/query")
async def query_endpoint(request: QueryRequest):
    rag = GroqRAGPipeline(model_name="llama3-8b-8192") 
    result = rag.process_query(request.query, request.customer_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.post("/stream")
async def stream_endpoint(request: QueryRequest):
    rag = GroqRAGPipeline(model_name="llama3-8b-8192")
    return StreamingResponse(
        rag.stream_response(request.query, request.customer_id),
        media_type="text/event-stream"
    )

@app.post("/voice")
async def voice_endpoint(file: UploadFile = File(...), customer_id: str = "anonymous"):
    if file.content_type != "audio/wav":
        raise HTTPException(status_code=400, detail="Only WAV files supported for now. Groq Whisper supports more.")
    
    rag = GroqRAGPipeline(model_name="llama3-8b-8192")
    health = rag.health_check()
    if not health["stt_available"]:
        raise HTTPException(
            status_code=503,
            detail="Speech-to-text is unavailable. Ensure Groq client is initialized and API key is valid."
        )
    if not health["tts_available"]:
        raise HTTPException(
            status_code=503,
            detail="Text-to-speech is unavailable. Ensure torch and torchaudio are installed."
        )
    
    audio_input_bytes = await file.read() # Read the incoming audio file
    try:
        # 1. Transcribe the customer's audio input
        customer_transcription = rag.speech_to_text(audio_input_bytes)
        
        # 2. Process the transcribed query with the RAG pipeline
        rag_response = rag.process_query(customer_transcription, customer_id)
        
        if "error" in rag_response:
            raise HTTPException(status_code=500, detail=rag_response["error"])
        
        # 3. Get the textual response from the RAG pipeline
        llm_response_text = rag_response["response"]
        
        # 4. Convert the RAG's textual response to audio
        agent_audio_response_bytes = rag.text_to_speech(llm_response_text)
        
        # 5. Encode the agent's audio response to base64
        agent_audio_response_base64 = base64.b64encode(agent_audio_response_bytes).decode('utf-8')
        
        # 6. Return a JSON response with both transcription and base64 audio
        return {
            "customer_transcription": customer_transcription,
            "agent_response_text": llm_response_text,
            "agent_audio_response_base64": agent_audio_response_base64,
            "sources": rag_response["sources"],
            "confidence": rag_response["confidence"]
        }
        
    except HTTPException as e:
        # Re-raise FastAPI HTTPExceptions directly
        raise e
    except Exception as e:
        error_detail = f"Voice processing error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)

# Groq Model Recommendations
GROQ_MODELS = {
    "production": "gemma2-9b-it",
    "fast": "llama3-8b-8192",
    "quality": "llama3-70b-8192",
    "balanced": "gemma2-9b-it"
}

if __name__ == "__main__":
    import uvicorn
    os.environ["GROQ_API_KEY"] = "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" 
    try:
        rag_instance = GroqRAGPipeline(model_name=GROQ_MODELS["fast"])
        health = rag_instance.health_check()
        print("Health Status:", health)
        if health["all_systems_operational"]:
            response = rag_instance.process_query("How do I return an item?")
            print(f"\nResponse: {response['response']}")
            print(f"Confidence: {response['confidence']}")
            print(f"Sources: {len(response['sources'])}")
            
            uvicorn.run(app, host="0.0.0.0", port=8000)
        else:
            print("System not ready. Check API key, vector store, or document count.")
            if not health["api_key_set"]:
                print("Make sure your GROQ_API_KEY is correctly set.")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}\n{traceback.format_exc()}")