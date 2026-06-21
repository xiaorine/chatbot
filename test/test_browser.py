import os
import sys
import yaml
import logging
from dotenv import load_dotenv

# Ensure import paths work (parent folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.browser import MessengerBrowser

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("TestBrowser")

# Load environment from parent folder
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

def load_settings() -> dict:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "settings.yaml")
    if not os.path.exists(config_path):
        logger.error(f"Config file not found at: {config_path}")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def main():
    logger.info("Starting Browser CDP connection test...")
    
    config = load_settings()
    
    # Merge env overrides
    if os.getenv("GPM_DEBUG_PORT"):
        config["gpm_debug_port"] = int(os.getenv("GPM_DEBUG_PORT"))
    if os.getenv("GPM_API_URL"):
        config["gpm_api_url"] = os.getenv("GPM_API_URL")
    if os.getenv("GPM_PROFILE_ID"):
        config["gpm_profile_id"] = os.getenv("GPM_PROFILE_ID")
        
    logger.info(f"Configuration: Mode={config.get('connection', {}).get('mode')}, Port={config.get('gpm_debug_port', 9222)}")
    
    browser = MessengerBrowser(config)
    try:
        browser.connect()
        logger.info("Successfully connected to the browser!")
        
        # Print open tabs
        logger.info("--- Current Browser Tabs ---")
        for i, page in enumerate(browser.context.pages):
            logger.info(f"Tab {i+1}: {page.title()} | URL: {page.url}")
            
        if browser.page:
            logger.info(f"Active Messenger Page Found: {browser.page.url}")
            
            # Try to grab unread threads
            logger.info("Scanning for unread threads (heurstics)...")
            unread = browser.get_unread_threads()
            logger.info(f"Unread threads found: {len(unread)}")
            for item in unread:
                logger.info(f" - Name: {item['name']} | ID: {item['thread_id']}")
                
            # Take a test screenshot of the messenger page
            screenshot_path = "messenger_test.png"
            logger.info(f"Taking a screenshot of the Messenger tab -> {screenshot_path}")
            browser.page.screenshot(path=screenshot_path)
            logger.info("Screenshot taken successfully!")
            
    except Exception as e:
        logger.error(f"Test failed! Error details: {e}", exc_info=True)
        logger.error("Please make sure that:")
        logger.error("1. Chrome is open and running with --remote-debugging-port=9222 (or the port set in GPM_DEBUG_PORT).")
        logger.error("2. If using GPM API, the GPM server is running and the GPM_PROFILE_ID is correct.")
    finally:
        logger.info("Closing browser connection...")
        try:
            browser.close()
        except Exception:
            pass
        logger.info("Test finished.")

if __name__ == "__main__":
    main()
