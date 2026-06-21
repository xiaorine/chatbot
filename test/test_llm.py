import os
import sys
import logging
from dotenv import load_dotenv

# Ensure import paths work (parent folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_gateway import generate_response

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("TestLLM")

# Load environment
# Load from parent directory where .env sits
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

def run_test():
    logger.info("Starting LiteLLM Gateway Test...")
    
    # Define a simple test history
    messages = [
        {"role": "user", "content": "Xin chào! Bạn có thể dịch từ 'Hello' sang tiếng Việt một cách ngắn gọn nhất được không?"}
    ]
    
    # Load settings defaults or define test targets
    default_model = "openai/mimo-v2.5-pro"
    fallbacks = [
        "gemini/gemini-2.5-flash",
        "openai/gpt-4o-mini",
        "deepseek/deepseek-chat"
    ]
    
    system_prompt = "Bạn là trợ lý dịch thuật ngắn gọn."
    
    logger.info("Executing completion request...")
    result = generate_response(
        messages=messages,
        default_model=default_model,
        fallbacks=fallbacks,
        system_prompt=system_prompt
    )
    
    logger.info("================ Test Results ================")
    if result["success"]:
        logger.info(f"Success! Model Used: {result['model_used']}")
        logger.info(f"Response: {result['text']}")
    else:
        logger.error(f"Failed! Error details: {result['error']}")
    logger.info("===============================================")

if __name__ == "__main__":
    run_test()
