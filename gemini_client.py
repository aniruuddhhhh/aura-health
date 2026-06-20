
import os
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_TEMPERATURE, DEBUG_MODE

MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-pro",
]


GEMINI_AVAILABLE = False
_gemini_model = None
_active_model_name = None
_init_error = None


def _initialize_gemini():
    """Initialize Gemini with detailed logging."""
    global GEMINI_AVAILABLE, _gemini_model, _active_model_name, _init_error
    
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    
    # CRITICAL: Log to stdout so Streamlit Cloud captures it
    if not api_key:
        _init_error = "GEMINI_API_KEY not found in environment"
        print(f"[Gemini] ERROR: {_init_error}")
        print(f"[Gemini]        Check that GEMINI_API_KEY is set in:")
        print(f"[Gemini]        - Local: .env file")
        print(f"[Gemini]        - Streamlit Cloud: App Settings > Secrets")
        return False
    
    print(f"[Gemini] API key found ({api_key[:6]}...{api_key[-4:]})")
    
    try:
        genai.configure(api_key=api_key)
        print(f"[Gemini] Configured successfully")
    except Exception as e:
        _init_error = f"genai.configure() failed: {e}"
        print(f"[Gemini] ERROR: {_init_error}")
        return False
    
    # List available models
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace("models/", "")
                available_models.append(name)
        
        print(f"[Gemini] Found {len(available_models)} available models")
        if DEBUG_MODE and available_models:
            print(f"[Gemini] Sample models:")
            for m in available_models[:5]:
                print(f"         - {m}")
    except Exception as e:
        print(f"[Gemini] Could not list models: {e}")
    
    # Try preferred models
    for model_name in MODELS_TO_TRY:
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
                print(f"[Gemini] SUCCESS: Active model = {model_name}")
                return True
                
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Gemini] Tried {model_name}: failed")
            continue
    
    # Try available models from account
    if available_models:
        print(f"[Gemini] Trying models from account...")
        for model_name in available_models:
            if 'flash' in model_name.lower() or 'pro' in model_name.lower():
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
                        print(f"[Gemini] SUCCESS: Active model = {model_name}")
                        return True
                except Exception:
                    continue
    
    _init_error = "No working models found"
    print(f"[Gemini] ERROR: {_init_error}")
    return False


_initialize_gemini()


def call_gemini(prompt: str, temperature: float = None, max_retries: int = 2) -> str:
    """Call Gemini with the given prompt."""
    if not GEMINI_AVAILABLE or _gemini_model is None:
        print(f"[Gemini] call_gemini() called but Gemini unavailable: {_init_error}")
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
                print(f"[Gemini] Attempt {attempt+1} failed: {str(e)[:200]}")
            if attempt == max_retries - 1:
                return ""
    
    return ""


def is_gemini_available() -> bool:
    return GEMINI_AVAILABLE


def get_active_model() -> str:
    return _active_model_name or "none"


def get_init_error() -> str:
    """Return the initialization error message if any."""
    return _init_error or ""


if __name__ == "__main__":
    print(f"\nGemini available: {is_gemini_available()}")
    print(f"Active model: {get_active_model()}")
    
    if not is_gemini_available():
        print(f"Init error: {get_init_error()}")
    else:
        print("\nTesting...")
        response = call_gemini("Say 'Hello AURA!' in exactly 3 words.")
        print(f"Response: {response}")