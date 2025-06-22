from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
from datasets import Dataset
import logging
import json
import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fine_tune_llama():
    try:
        model_name = "meta-llama/Llama-3-8b"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
        
        # Prepare dataset (example: 100 QA pairs)
        with open("data/call_center_dataset.json", "r") as f:
            data = json.load(f)
        dataset = Dataset.from_dict({
            "text": [f"Q: {item['question']}\nA: {item['answer']}" for item in data]
        })
        
        def tokenize_function(examples):
            return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=512)
        
        tokenized_dataset = dataset.map(tokenize_function, batched=True)
        
        training_args = TrainingArguments(
            output_dir="data/fine_tuned_llama",
            num_train_epochs=3,
            per_device_train_batch_size=2,
            save_steps=500,
            save_total_limit=2,
            logging_dir="data/logs",
            logging_steps=100,
        )
        
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset,
        )
        
        trainer.train()
        model.save_pretrained("data/fine_tuned_llama")
        tokenizer.save_pretrained("data/fine_tuned_llama")
        logger.info("LLaMA 3 fine-tuning completed")
    except Exception as e:
        logger.error(f"Error fine-tuning LLaMA: {str(e)}")
        raise

if __name__ == "__main__":
    fine_tune_llama()