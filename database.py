import sqlite3
import json
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# Simple database path - choose one of these options:

# Option 1: Database in the same directory as the script
DB_PATH = "Data/callcenter.db"

# Option 2: Database in current working directory
# DB_PATH = "./callcenter.db"

# Option 3: Database in a simple data folder (will be created if not exists)
# DB_PATH = "data/callcenter.db"

def get_db_connection():
    """Connect to SQLite database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {DB_PATH}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error for {DB_PATH}: {str(e)}")
        raise

def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Error checking table {table_name}: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def initialize_db():
    """Initialize database tables."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query TEXT,
                response TEXT,
                metadata TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def log_conversation(query: str, response: str, customer_id: str = "anonymous"):
    """Log conversation to database."""
    conn = None
    cursor = None
    try:
        if not check_table_exists("conversations"):
            logger.warning("Conversations table missing, initializing database")
            initialize_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (customer_id, query, response, metadata) VALUES (?, ?, ?, ?)",
            (customer_id, query, response, json.dumps({"source": "rag_pipeline"}))
        )
        conn.commit()
        logger.info("Conversation logged")
    except sqlite3.Error as e:
        logger.error(f"Error logging conversation: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def store_raw_data(content: str, metadata: dict):
    """Store raw data in database."""
    conn = None
    cursor = None
    try:
        if not check_table_exists("knowledge_base"):
            logger.warning("Knowledge_base table missing, initializing database")
            initialize_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO knowledge_base (content, metadata) VALUES (?, ?)",
            (content, json.dumps(metadata))
        )
        conn.commit()
        logger.info("Raw data stored")
    except sqlite3.Error as e:
        logger.error(f"Error storing raw data: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()