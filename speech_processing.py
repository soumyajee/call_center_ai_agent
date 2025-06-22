import whisper
import pyttsx3
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def transcribe_audio(audio_path: str) -> str:
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        logger.info(f"Transcribed audio: {result['text']}")
        return result["text"]
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise

def generate_speech(text: str, output_path: str):
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        logger.info(f"Generated speech at: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise

def speech_to_text(audio_path: str) -> str:
    return transcribe_audio(audio_path)

def text_to_speech(text: str) -> str:
    output_path = f"data/output_{hash(text)}.wav"
    return generate_speech(text, output_path)