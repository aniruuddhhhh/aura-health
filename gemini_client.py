"""
Now prioritizes the better Gemini 2.x models
that are actually available in current accounts.
"""

import os
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_TEMPERATURE, DEBUG_MODE

MODELS_TO_TRY = [
    "gemini-2.5-flash",            
    "gemini-2.5-pro",              
    
    "gemini-2.0-flash",            
    "gemini-2.0-flash-001",        
    
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-lite-001",
    "gemini-flash-lite-latest",
    
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-pro",
]

GEMINI_AVAILABLE = False
_gemini_model = None
_active_model_name = None

def _initialize_gemini():
    """Initialize Gemini and find a working model."""
    global GEMINI_AVAILABLE, _gemini_model, _active_model_name
    
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        if DEBUG_MODE:
            print("[Gemini] WARNING: No API key found.")
            print("        Set GEMINI_API_KEY in .env or environment.")
            print("        Get free key: https://makersuite.google.com/app/apikey")
        return False
    
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        if DEBUG_MODE:
            print(f"[Gemini] Failed to configure: {e}")
        return False
    
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace("models/", "")
                available_models.append(name)
        
        if DEBUG_MODE:
            print(f"[Gemini] Available models in your account:")
            for m in available_models[:8]:
                print(f"        - {m}")
    except Exception as e:
        if DEBUG_MODE:
            print(f"[Gemini] Could not list models: {e}")
    
    candidates = MODELS_TO_TRY.copy()
    for model in available_models:
        if model not in candidates:
            if "flash" in model.lower() or "pro" in model.lower():
                candidates.append(model)
    
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            test_response = model.generate_content(
                "Hi",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=10,
                    temperature=0,
                )
            )
            
            if test_response and test_response.text:
                _gemini_model = model
                _active_model_name = model_name
                GEMINI_AVAILABLE = True
                if DEBUG_MODE:
                    print(f"[Gemini] OK: Using model: {model_name}")
                return True
                
        except Exception as e:
            if DEBUG_MODE:
                if model_name in MODELS_TO_TRY[:5]:
                    print(f"[Gemini] Tried {model_name}: failed")
            continue
    
    if DEBUG_MODE:
        print(f"[Gemini] ERROR: No working model found!")
    return False

_initialize_gemini()

def call_gemini(prompt: str, temperature: float = None, max_retries: int = 2) -> str:
    if not GEMINI_AVAILABLE or _gemini_model is None:
        return ""
    
    if temperature is None:
        temperature = GEMINI_TEMPERATURE
    
    for attempt in range(max_retries):
        try:
            response = _gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=1024,
                )
            )
            if response and response.text:
                return response.text.strip()
            return ""
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Gemini] Attempt {attempt+1} failed: {str(e)[:100]}")
            if attempt == max_retries - 1:
                return ""
    return ""

def is_gemini_available() -> bool:
    return GEMINI_AVAILABLE

def get_active_model() -> str:
    return _active_model_name or "none"

if __name__ == "__main__":
    print("Gemini Client Test")
    print(f"\nGemini available: {is_gemini_available()}")
    print(f"Active model: {get_active_model()}")
    
    if is_gemini_available():
        print("\nTesting with a simple prompt...")
        response = call_gemini("Say 'Hello AURA!' in exactly 3 words.")
        print(f"Response: {response}")
        
        print("\nTesting SQL generation...")
        response = call_gemini(
            "Generate a SQL query: select all from heart_rate where Id = 123. Just SQL, no explanation.",
            temperature=0
        )
        print(f"Response: {response}")
