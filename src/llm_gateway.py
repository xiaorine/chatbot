import logging
import litellm
from litellm import completion
from typing import List, Dict, Any, Optional

# Disable litellm's verbose logging unless we want it for debug
litellm.telemetry = False

logger = logging.getLogger("Chatbot.LLMGateway")

def generate_response(
    messages: List[Dict[str, str]],
    default_model: str,
    fallbacks: List[str],
    system_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate response using LiteLLM.
    If the default model fails, it tries fallback models in sequence.
    
    Args:
        messages: List of message dicts (e.g. [{"role": "user", "content": "hello"}])
        default_model: The primary model to use (e.g. 'gemini/gemini-2.5-flash')
        fallbacks: List of fallback models to try if default fails.
        system_prompt: Optional system prompt to prepend.
        
    Returns:
        Dict containing:
            - "success": bool
            - "text": str (response text)
            - "model_used": str
            - "error": str (if failed)
    """
    # Construct complete message history
    history = []
    if system_prompt:
        history.append({"role": "system", "content": system_prompt})
    history.extend(messages)
    
    # List of models to try (default model followed by fallbacks)
    models_to_try = [default_model] + [f for f in fallbacks if f != default_model]
    
    import os
    for idx, model in enumerate(models_to_try):
        logger.info(f"Attempting to generate response using model: {model}...")
        try:
            # Set up completion arguments
            completion_kwargs = {
                "model": model,
                "messages": history,
                "timeout": 30.0
            }
            
            # Dynamic routing for XiaomiMiMo models
            if "mimo-" in model:
                if not model.startswith("openai/"):
                    completion_kwargs["model"] = f"openai/{model}"
                
                mimo_key = os.getenv("XIAOMIMIMO_API_KEY")
                mimo_base = os.getenv("XIAOMIMIMO_API_BASE")
                
                if mimo_key:
                    completion_kwargs["api_key"] = mimo_key
                if mimo_base:
                    completion_kwargs["api_base"] = mimo_base
                    
            # LiteLLM completion call
            response = completion(**completion_kwargs)
            
            # Extract reply text
            reply_text = response.choices[0].message.content
            logger.info(f"Success! Model {model} responded successfully.")
            return {
                "success": True,
                "text": reply_text,
                "model_used": model,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Model {model} failed. Error: {str(e)}")
            # If there are more models to try, continue. Otherwise, return failure.
            if idx == len(models_to_try) - 1:
                logger.error("All configured LLM models failed.")
                return {
                    "success": False,
                    "text": "",
                    "model_used": None,
                    "error": str(e)
                }
            logger.info("Retrying with the next fallback model...")
            
    return {
        "success": False,
        "text": "",
        "model_used": None,
        "error": "No models were tried."
    }
