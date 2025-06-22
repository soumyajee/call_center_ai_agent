import json
import os
from datetime import datetime
from knowledge_base import scrape_data, preprocess_data, store_embeddings, store_raw_data
from database import initialize_db
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def save_raw_data_to_json(raw_data, filename=None):
    """Save raw scraped data to JSON file"""
    if filename is None:
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"raw_data_{timestamp}.json"
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    filepath = os.path.join("data", filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Raw data saved to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving raw data to JSON: {str(e)}")
        raise

def save_processed_data_to_json(processed_data, filename=None):
    """Save processed data to JSON file"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processed_data_{timestamp}.json"
    
    os.makedirs("data", exist_ok=True)
    filepath = os.path.join("data", filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Processed data saved to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving processed data to JSON: {str(e)}")
        raise

def main():
    try:
        # Ensure database is initialized
        logger.info("Initializing database")
        initialize_db()
        
        # Use Zendesk help center for call center-relevant FAQs
        url = "https://www.zendesk.com/help-center/"
        logger.info(f"Scraping data from {url}")
        raw_data = scrape_data(url)
        
        if not raw_data:
            logger.warning("No data scraped, falling back to local file")
            raw_data = scrape_data(local=True)
        
        # Save raw data to JSON
        if raw_data:
            save_raw_data_to_json(raw_data)
            print(f"Raw data contains {len(raw_data)} items")
        
        # Process the data
        processed_data = [preprocess_data(item) for item in raw_data]
        logger.info(f"Preprocessed {len(processed_data)} items")
        
        # Save processed data to JSON as well
        if processed_data:
            save_processed_data_to_json(processed_data)
        
        # Store in database
        for item in processed_data:
            store_raw_data(item["content"], item["metadata"])
        
        store_embeddings(processed_data)
        logger.info("Data pipeline completed")
        
    except Exception as e:
        logger.error(f"Error in data pipeline: {str(e)}")
        raise

if __name__ == "__main__":
    main()