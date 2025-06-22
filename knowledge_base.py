from langchain.vectorstores import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from database import store_raw_data
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Ensure data directory exists
def ensure_data_directory():
    """Create data directory if it doesn't exist."""
    if not os.path.exists("data"):
        os.makedirs("data")
        logger.info("Created data directory")

def create_session_with_retries():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def scrape_data(url: str = None, local: bool = False) -> list:
    ensure_data_directory()
    
    if local:
        try:
            html_file = "data/sample_faq.html"
            if not os.path.exists(html_file):
                logger.warning("Local FAQ file not found, using fallback")
                return load_fallback_data()
            with open(html_file, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
            faqs = soup.find_all("p")
            data = [
                {
                    "content": faq.get_text(strip=True),
                    "metadata": {"source": "local", "category": "faq"}
                }
                for faq in faqs if faq.get_text(strip=True)
            ]
            if not data:
                logger.warning("No data scraped from local file, using fallback")
                return load_fallback_data()
            logger.info(f"Scraped {len(data)} items from local FAQ file")
            return data
        except Exception as e:
            logger.error(f"Error scraping local file: {str(e)}")
            return load_fallback_data()

    if not url:
        logger.warning("No URL provided, using fallback")
        return load_fallback_data()

    try:
        session = create_session_with_retries()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # Adjust parsing for Zendesk help center
        faqs = soup.find_all("article") or soup.find_all("div", class_="article-body") or soup.find_all("p")
        data = [
            {
                "content": faq.get_text(strip=True),
                "metadata": {"source": url, "category": "faq"}
            }
            for faq in faqs if faq.get_text(strip=True)
        ]
        if not data:
            logger.warning(f"No data scraped from {url}, using fallback")
            return load_fallback_data()
        logger.info(f"Scraped {len(data)} items from {url}")
        return data
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        return load_fallback_data()

def load_fallback_data() -> list:
    ensure_data_directory()
    
    fallback_file = "data/fallback_data.json"
    if os.path.exists(fallback_file):
        with open(fallback_file, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} items from fallback data")
        return [{"content": item["content"], "metadata": {"source": "fallback", "category": "faq"}} for item in data]
    
    # Create fallback data file if it doesn't exist
    default_data = [
        {"content": "How to return an item? Visit the returns page and follow the instructions.", "metadata": {"source": "fallback", "category": "faq"}},
        {"content": "What is the shipping policy? Free shipping on orders over $25.", "metadata": {"source": "fallback", "category": "faq"}},
        {"content": "How to track my order? Use the tracking link in your confirmation email.", "metadata": {"source": "fallback", "category": "faq"}}
    ]
    
    # Save default data to file for future use
    with open(fallback_file, "w") as f:
        json.dump([{"content": item["content"]} for item in default_data], f, indent=2)
    logger.info("Created fallback data file with default FAQs")
    
    return default_data

def preprocess_data(item: dict) -> dict:
    content = item["content"]
    content = re.sub(r"\s+", " ", content).strip()
    content = re.sub(r"[^\x00-\x7F]+", "", content)
    return {
        "content": content,
        "metadata": item["metadata"]
    }

def store_embeddings(data: list):
    ensure_data_directory()
    
    try:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        texts = [item["content"] for item in data if item["content"]]
        metadatas = [item["metadata"] for item in data if item["content"]]
        if not texts:
            logger.warning("No valid texts for embedding")
            return
        vector_store = Chroma.from_texts(
            texts=texts,
            embedding=embeddings,
            metadatas=metadatas,
            collection_name="knowledge_base",
            persist_directory="data/embeddings"
        )
        vector_store.persist()
        logger.info(f"Stored {len(texts)} embeddings in Chroma")
    except Exception as e:
        logger.error(f"Error storing embeddings: {str(e)}")
        raise