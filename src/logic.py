import os
import json
import random
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("Chatbot.Logic")

def is_whitelisted(
    thread_id: str,
    sender_name: str,
    whitelist: Dict[str, Any]
) -> bool:
    """
    Check if a chat thread or sender is in the whitelist.
    
    Args:
        thread_id: The ID of the thread (usually numeric or vanity string from URL)
        sender_name: The display name of the sender (scraped from page)
        whitelist: The parsed whitelist.json content
        
    Returns:
        bool: True if allowed to reply, False otherwise
    """
    if whitelist.get("allow_all", False):
        return True
        
    # Check thread ID
    allowed_threads = whitelist.get("allowed_threads", [])
    if thread_id and str(thread_id) in [str(t) for t in allowed_threads]:
        logger.info(f"Thread ID '{thread_id}' is whitelisted.")
        return True
        
    # Check sender name
    allowed_names = whitelist.get("allowed_names", [])
    if sender_name:
        sender_name_lower = sender_name.strip().lower()
        for name in allowed_names:
            if name.strip().lower() == sender_name_lower:
                logger.info(f"Sender name '{sender_name}' is whitelisted.")
                return True
                
    logger.info(f"Access denied: Thread ID '{thread_id}', Sender '{sender_name}' not in whitelist.")
    return False


def format_messages_for_llm(
    raw_history: List[Dict[str, Any]],
    limit: int = 10
) -> Tuple[List[Dict[str, str]], bool]:
    """
    Format scraped history into standard OpenAI/LiteLLM format:
    [{"role": "user"|"assistant", "content": "..."}]
    
    Also determines if we should reply (i.e. the last message was NOT sent by us).
    
    Args:
        raw_history: List of messages, ordered from oldest to newest.
                    Format: [{"sender": "me"|"them", "text": "...", "sender_name": "..."}]
        limit: Max number of history messages to include
        
    Returns:
        Tuple[List[Dict[str, str]], bool]: (formatted_messages, should_reply)
    """
    if not raw_history:
        return [], False
        
    # Check if the last message was sent by "me" (ourselves)
    last_msg = raw_history[-1]
    if last_msg.get("sender") == "me":
        # Already replied or we initiated the message, do not reply
        return [], False
        
    # Slice the history to get the last `limit` messages
    recent_history = raw_history[-limit:]
    
    formatted = []
    for msg in recent_history:
        role = "assistant" if msg.get("sender") == "me" else "user"
        text = msg.get("text", "").strip()
        if text:
            # We can optionally include the sender name in the message text for context (useful for groups)
            # In group chats, knowing who said what is very helpful
            sender_name = msg.get("sender_name", "")
            if role == "user" and sender_name and len(raw_history) > 1: # only if we have sender names
                content = f"{sender_name}: {text}"
            else:
                content = text
            formatted.append({"role": role, "content": content})
            
    return formatted, True


def calculate_delay(
    response_text: str,
    min_delay: float = 2.0,
    max_delay: float = 5.0,
    typing_speed_wpm: float = 80.0
) -> float:
    """
    Calculate a human-like delay before sending a message.
    It combines a random hesitation delay with a typing simulation delay based on text length.
    
    Args:
        response_text: The text to be typed
        min_delay: Minimum base delay in seconds
        max_delay: Maximum base delay in seconds
        typing_speed_wpm: Typing speed in words per minute
        
    Returns:
        float: Delay in seconds
    """
    # 1. Base random delay (thinking time)
    base_delay = random.uniform(min_delay, max_delay)
    
    # 2. Typing speed delay
    # Average word length is assumed to be 5 characters
    word_count = max(1, len(response_text) / 5.0)
    # typing delay in minutes = word_count / speed
    # typing delay in seconds = (word_count / speed) * 60
    typing_delay = (word_count / typing_speed_wpm) * 60.0
    
    total_delay = base_delay + typing_delay
    logger.info(f"Calculated delay: {total_delay:.2f}s (thinking: {base_delay:.2f}s, typing: {typing_delay:.2f}s for {len(response_text)} chars)")
    return total_delay


def log_sent_message(recipient: str, reply: str, model: str):
    """Log sent messages to a local JSON file for GUI/history tracking."""
    log_file = os.path.join("config", "sent_messages.json")
    history = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
            
    history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": recipient,
        "reply": reply,
        "model": model
    })
    
    # Keep last 50 messages
    history = history[-50:]
    
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving sent messages log: {e}")
