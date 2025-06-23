import streamlit as st
import requests
import json
import io
import base64
import numpy as np
import wave
from datetime import datetime

# --- Configuration ---
# Default FastAPI server URL. Users can change this in the sidebar.
DEFAULT_FASTAPI_URL = "http://localhost:8000" 

# --- Session State Initialization ---
if 'messages' not in st.session_state:
    st.session_state.messages = [] # Stores chat history

if 'fastapi_url' not in st.session_state:
    st.session_state.fastapi_url = DEFAULT_FASTAPI_URL

if 'customer_id' not in st.session_state:
    st.session_state.customer_id = "user_" + datetime.now().strftime("%Y%m%d%H%M%S") # Unique ID for session

# --- Helper Functions ---

def send_query_to_rag(query: str, customer_id: str) -> dict:
    """Sends a text query to the FastAPI RAG /query endpoint."""
    url = f"{st.session_state.fastapi_url}/query"
    payload = {"query": query, "customer_id": customer_id}
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.Timeout:
        st.error("The request timed out. The FastAPI server might be slow or unresponsive.")
        return {"response": "Error: Request timed out.", "sources": [], "confidence": 0.0}
    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to FastAPI server at {url}. Please check the URL and ensure the server is running.")
        return {"response": "Error: Could not connect to server.", "sources": [], "confidence": 0.0}
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while calling the RAG API: {e}")
        return {"response": f"Error: API call failed - {e}", "sources": [], "confidence": 0.0}

def process_voice_input(audio_bytes: bytes, customer_id: str) -> dict:
    """
    Sends audio bytes to the FastAPI /voice endpoint and returns the full JSON response,
    including transcription, agent text, and base64 audio.
    """
    url = f"{st.session_state.fastapi_url}/voice"
    files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
    data = {'customer_id': customer_id} # Pass customer_id as form data
    
    st.info("Sending audio for processing (STT + RAG + TTS)...")
    try:
        response = requests.post(url, files=files, data=data, timeout=180) # Increased timeout for full voice processing
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Voice processing timed out. The FastAPI server might be slow or unresponsive.")
        return {"error": "Voice processing timed out."}
    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to FastAPI server at {url} for voice processing. Check server URL.")
        return {"error": "Voice server unreachable."}
    except requests.exceptions.HTTPError as e:
        st.error(f"FastAPI returned an error for voice processing: {e.response.status_code} - {e.response.json().get('detail', 'Unknown error')}")
        return {"error": f"API error: {e.response.json().get('detail', 'Unknown error')}"}
    except requests.exceptions.RequestException as e:
        st.error(f"An unexpected error occurred during voice processing: {e}")
        return {"error": f"Unexpected error: {e}"}

def synthesize_speech_from_text(text: str) -> bytes:
    """Sends text to the FastAPI /text-to-speech endpoint and returns audio bytes."""
    url = f"{st.session_state.fastapi_url}/text-to-speech"
    payload = {"query": text, "customer_id": st.session_state.customer_id} # Reusing QueryRequest model
    st.info("Synthesizing speech...")
    try:
        # Using stream=True for potentially large audio responses
        response = requests.post(url, json=payload, timeout=120, stream=True)
        response.raise_for_status()
        
        # Read the audio content directly from the response stream
        audio_data = b"".join(response.iter_content(chunk_size=8192))
        return audio_data
    except requests.exceptions.Timeout:
        st.error("Text-to-speech synthesis timed out. The FastAPI server might be slow or unresponsive.")
        return b""
    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to FastAPI server at {url} for TTS. Check server URL.")
        return b""
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred during text-to-speech: {e}")
        return {"error": f"An error occurred during text-to-speech: {e}"} # Return error dict for consistency

def save_uploaded_audio_to_wav(uploaded_file):
    """Reads uploaded file content."""
    # For simplicity, assuming uploaded audio is already WAV.
    # In a real app, you might use pydub to convert.
    return uploaded_file.read()

def display_chat_message(role, content, sources=None, confidence=None, audio_data=None):
    """Displays a chat message with optional sources, confidence, and audio playback."""
    with st.chat_message(role):
        st.write(content)
        if sources:
            with st.expander("Sources"):
                for source in sources:
                    st.write(f"- Content: {source.get('content', 'N/A')}")
                    st.write(f"  Metadata: {source.get('metadata', 'N/A')}")
                    st.write(f"  Relevance: {source.get('relevance_score', 'N/A'):.2f}")
        if confidence is not None:
            st.markdown(f"**Confidence**: {confidence:.2f}")
        
        if audio_data:
            # Decode base64 audio if provided
            if isinstance(audio_data, str):
                try:
                    audio_data = base64.b64decode(audio_data)
                except Exception as e:
                    st.error(f"Error decoding audio data: {e}")
                    audio_data = None # Invalidate if decoding fails
            
            if audio_data:
                st.audio(audio_data, format="audio/wav", start_time=0)

# --- Streamlit UI ---
st.set_page_config(page_title="Voice-Enabled RAG Agent", layout="centered")

st.title("📞 Voice-Enabled RAG Call Center Agent")
st.markdown("Interact with the AI agent using text or speech!")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    st.session_state.fastapi_url = st.text_input(
        "FastAPI Server URL", 
        st.session_state.fastapi_url, 
        help="Enter the URL where your FastAPI application is running (e.g., http://localhost:8000)"
    )
    st.session_state.customer_id = st.text_input(
        "Customer ID (for session tracking)", 
        st.session_state.customer_id,
        help="This ID helps the RAG pipeline track your conversation history."
    )
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun() # Changed from st.experimental_rerun() to st.rerun()


# Display chat messages from history
for message in st.session_state.messages:
    display_chat_message(
        message["role"], 
        message["content"], 
        message.get("sources"), 
        message.get("confidence"),
        message.get("audio_data") # Pass audio data (might be base64 string or bytes)
    )

# --- Input Section ---
st.markdown("---")
col1, col2 = st.columns([3, 1])

with col1:
    user_text_query = st.text_area("Type your question here:", key="text_input_area", height=100)
    uploaded_audio = st.file_uploader("Or upload a WAV audio file:", type=["wav"], key="audio_uploader")

with col2:
    st.write(" ") # Spacer for alignment
    send_text_button = st.button("Ask (Text)", use_container_width=True)
    send_speech_button = st.button("Ask (Speech via Upload)", use_container_width=True)
    speak_last_response_button = st.button("🔊 Speak Last Response", use_container_width=True)


# --- Handle Text Query ---
if send_text_button and user_text_query:
    st.session_state.messages.append({"role": "user", "content": user_text_query})
    display_chat_message("user", user_text_query)

    with st.spinner("Getting response..."):
        response_data = send_query_to_rag(user_text_query, st.session_state.customer_id)
        rag_response = response_data.get("response", "No response from agent.")
        sources = response_data.get("sources", [])
        confidence = response_data.get("confidence", 0.0)

        st.session_state.messages.append({
            "role": "assistant",
            "content": rag_response,
            "sources": sources,
            "confidence": confidence
        })
        display_chat_message("assistant", rag_response, sources, confidence)

# --- Handle Speech Query (using the unified /voice endpoint) ---
if send_speech_button and uploaded_audio:
    # First, show the user's audio input in the chat
    st.session_state.messages.append({"role": "user", "content": "Audio Input (Processing...)"})
    display_chat_message("user", "Audio Input (Processing...)")

    audio_bytes = save_uploaded_audio_to_wav(uploaded_audio)
    
    with st.spinner("Sending audio for full voice processing..."):
        voice_response = process_voice_input(audio_bytes, st.session_state.customer_id)
        
        if "error" in voice_response:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Error processing audio: {voice_response['error']}",
                "sources": [], "confidence": 0.0
            })
            display_chat_message("assistant", f"Error processing audio: {voice_response['error']}")
        else:
            customer_transcription = voice_response.get("customer_transcription", "No transcription available.")
            agent_response_text = voice_response.get("agent_response_text", "No agent response text.")
            agent_audio_response_base64 = voice_response.get("agent_audio_response_base64")
            sources = voice_response.get("sources", [])
            confidence = voice_response.get("confidence", 0.0)

            # Update the user's message with the transcribed text
            st.session_state.messages[-1]["content"] = f"Audio Input: \"{customer_transcription}\""
            display_chat_message("user", st.session_state.messages[-1]["content"])

            # Add the assistant's response to chat history
            st.session_state.messages.append({
                "role": "assistant",
                "content": agent_response_text,
                "sources": sources,
                "confidence": confidence,
                "audio_data": agent_audio_response_base64 # Store base64 string
            })
            # Display the assistant's response (will automatically play audio if audio_data is present)
            display_chat_message("assistant", agent_response_text, sources, confidence, agent_audio_response_base64)


# --- Speak Last Response ---
if speak_last_response_button:
    if st.session_state.messages:
        last_agent_message = None
        # Find the last message from the assistant
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                last_agent_message = msg
                break
        
        if last_agent_message and last_agent_message.get("content"):
            response_text_to_speak = last_agent_message["content"]
            # If audio_data is already stored, just play it
            if last_agent_message.get("audio_data"):
                st.audio(base64.b64decode(last_agent_message["audio_data"]), format="audio/wav", start_time=0)
                st.success("Playing last response from cache.")
            else:
                # Otherwise, synthesize speech from text
                with st.spinner("Generating speech for the last response..."):
                    audio_response_bytes = synthesize_speech_from_text(response_text_to_speak)
                    if audio_response_bytes and not isinstance(audio_response_bytes, dict): # Check for error dict
                        st.audio(audio_response_bytes, format="audio/wav", start_time=0)
                        st.success("Playing last response.")
                        # Optionally, store this newly generated audio in session state
                        last_agent_message["audio_data"] = base64.b64encode(audio_response_bytes).decode('utf-8')
                        st.session_state.messages[-1] = last_agent_message # Update message in session state
                    else:
                        st.error("Could not generate audio for the last response. Check FastAPI logs.")
        else:
            st.info("No assistant response to speak yet.")
    else:
        st.info("No conversation history yet.")
