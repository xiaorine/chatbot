import os
import sys
import time
import yaml
import json
import logging
import random
import threading
from dotenv import load_dotenv

# Add the project root to python path to ensure imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.browser import MessengerBrowser
from src.llm_gateway import generate_response
from src.logic import is_whitelisted, format_messages_for_llm, calculate_delay, log_sent_message

# Global event to stop the chatbot thread cleanly from external servers
STOP_EVENT = threading.Event()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("chatbot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("Chatbot.Main")

# Load environment variables
load_dotenv()

def load_settings() -> dict:
    """Load configuration from settings.yaml."""
    config_path = os.path.join("config", "settings.yaml")
    if not os.path.exists(config_path):
        logger.error(f"Settings file not found at {config_path}")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_whitelist() -> dict:
    """Load whitelist from whitelist.json."""
    whitelist_path = os.path.join("config", "whitelist.json")
    if not os.path.exists(whitelist_path):
        logger.warning(f"Whitelist file not found at {whitelist_path}, allowing all by default.")
        return {"allow_all": True}
    with open(whitelist_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception as e:
            logger.error(f"Error parsing whitelist.json: {e}")
            return {"allow_all": False}

def merge_env_into_config(config: dict) -> dict:
    """Merge environment variable overrides into config dict."""
    # LLM keys are handled directly by litellm via env variables
    
    # GPM/CDP Overrides
    if os.getenv("GPM_DEBUG_PORT"):
        config["gpm_debug_port"] = int(os.getenv("GPM_DEBUG_PORT"))
    if os.getenv("GPM_API_URL"):
        config["gpm_api_url"] = os.getenv("GPM_API_URL")
    if os.getenv("GPM_PROFILE_ID"):
        config["gpm_profile_id"] = os.getenv("GPM_PROFILE_ID")
        
    return config

def main():
    logger.info("==============================================")
    logger.info("Starting Messenger Chatbot with GPM & LiteLLM")
    logger.info("==============================================")
    
    # Reset STOP_EVENT when starting
    STOP_EVENT.clear()
    
    config = load_settings()
    config = merge_env_into_config(config)
    
    if not config:
        logger.error("Configuration is empty. Exiting.")
        sys.exit(1)
        
    # Check if we have at least one API key set
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    xiaomimimo_key = os.getenv("XIAOMIMIMO_API_KEY")
    
    if not any([gemini_key, openai_key, deepseek_key, xiaomimimo_key]):
        logger.warning("WARNING: No AI API keys found in environmental variables. LLM completions may fail.")
        
    bot_settings = config.get("chatbot", {})
    poll_interval = bot_settings.get("poll_interval", 2.0)
    history_limit = bot_settings.get("context_history_limit", 10)
    
    human_settings = config.get("human_like", {})
    min_delay = human_settings.get("min_delay", 2.0)
    max_delay = human_settings.get("max_delay", 5.0)
    typing_speed = human_settings.get("typing_speed_wpm", 80)
    
    llm_settings = config.get("llm", {})
    default_model = llm_settings.get("default_model", "gemini/gemini-2.5-flash")
    fallbacks = llm_settings.get("fallbacks", [])
    system_prompt = llm_settings.get("system_prompt", "")
    
    # Initialize and connect browser
    browser = MessengerBrowser(config)
    try:
        browser.connect()
    except Exception as e:
        logger.critical(f"Failed to connect browser: {e}. Exiting.")
        sys.exit(1)
        
    logger.info("Chatbot connected and entering main loop. Listening for incoming messages...")
    
    try:
        while not STOP_EVENT.is_set():
            try:
                # Load latest whitelist dynamically each loop to allow hot-reloading
                whitelist = load_whitelist()
                
                # Check for unread threads
                unread_threads = browser.get_unread_threads()
                if unread_threads and not STOP_EVENT.is_set():
                    logger.info(f"Found {len(unread_threads)} unread thread(s).")
                    
                    for thread in unread_threads:
                        if STOP_EVENT.is_set():
                            break
                            
                        thread_id = thread["thread_id"]
                        sender_name = thread["name"]
                        
                        logger.info(f"Processing thread '{sender_name}' (ID: {thread_id})...")
                        
                        # Validate against whitelist
                        if is_whitelisted(thread_id, sender_name, whitelist):
                            # Click thread to open it
                            browser.select_thread(thread_id)
                            
                            # Scrape history
                            raw_history = browser.get_chat_history()
                            
                            # Format for LLM and check if we should reply
                            formatted_msgs, should_reply = format_messages_for_llm(raw_history, history_limit)
                            
                            if should_reply:
                                # Debounce: wait for user to finish sending consecutive messages
                                wait_seconds = bot_settings.get("wait_for_user_finish_seconds", 5.0)
                                logger.info(f"New message detected. Waiting {wait_seconds}s for user to finish consecutive messages...")
                                
                                stable = False
                                while not stable and not STOP_EVENT.is_set():
                                    last_msg_count = len(raw_history)
                                    last_msg_text = raw_history[-1].get("text") if raw_history else ""
                                    
                                    # Wait on stop event instead of hard sleep
                                    if STOP_EVENT.wait(wait_seconds):
                                        break
                                        
                                    # Refresh history
                                    raw_history = browser.get_chat_history()
                                    new_msg_count = len(raw_history)
                                    new_msg_text = raw_history[-1].get("text") if raw_history else ""
                                    
                                    if new_msg_count == last_msg_count and new_msg_text == last_msg_text:
                                        stable = True
                                    else:
                                        logger.info("User sent another message. Resetting wait timer...")
                                        formatted_msgs, should_reply = format_messages_for_llm(raw_history, history_limit)
                                        if not should_reply:
                                            logger.info("Chat state changed or already replied. Aborting response.")
                                            break
                                            
                                if not should_reply or STOP_EVENT.is_set():
                                    continue
                                    
                                logger.info(f"User finished typing. Generating response...")
                                
                                # Call LLM Gateway
                                result = generate_response(
                                    messages=formatted_msgs,
                                    default_model=default_model,
                                    fallbacks=fallbacks,
                                    system_prompt=system_prompt
                                )
                                
                                if result["success"] and not STOP_EVENT.is_set():
                                    reply_text = result["text"]
                                    model_used = result["model_used"]
                                    logger.info(f"Generated reply via {model_used}: '{reply_text}'")
                                    
                                    # Simulate thinking time before typing
                                    thinking_time = random.uniform(min_delay, max_delay)
                                    logger.info(f"Hesitating/Thinking for {thinking_time:.2f} seconds...")
                                    if STOP_EVENT.wait(thinking_time):
                                        break
                                        
                                    # Calculate remaining dynamic typing speed delay
                                    # typing speed delay in seconds
                                    word_count = max(1, len(reply_text) / 5.0)
                                    typing_delay = (word_count / typing_speed) * 60.0
                                    logger.info(f"Simulating human typing for {typing_delay:.2f} seconds...")
                                    
                                    # Send the message (this function types character by character)
                                    browser.send_message(reply_text)
                                    
                                    # Save to sent messages local log
                                    log_sent_message(sender_name, reply_text, model_used)
                                    
                                    logger.info(f"Successfully replied to '{sender_name}'!")
                                else:
                                    if not STOP_EVENT.is_set():
                                        logger.error(f"Failed to generate response: {result.get('error')}")
                            else:
                                logger.info(f"Last message in thread was sent by us. No response needed.")
                        else:
                            # Thread is not whitelisted.
                            # We select it once to clear the unread badge, preventing endless scans.
                            logger.info(f"Thread '{sender_name}' (ID: {thread_id}) is not whitelisted. Marking as read.")
                            browser.select_thread(thread_id)
                            STOP_EVENT.wait(1.0)
                            
                # Idle poll delay
                STOP_EVENT.wait(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Program interrupted by user. Exiting main loop...")
                break
            except Exception as loop_err:
                logger.error(f"Error in main loop iteration: {loop_err}", exc_info=True)
                # Brief sleep before retrying to prevent rapid error cycling
                STOP_EVENT.wait(5.0)
                
    finally:
        logger.info("Shutting down chatbot browser...")
        try:
            browser.close()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
        logger.info("Chatbot stopped.")

if __name__ == "__main__":
    main()
