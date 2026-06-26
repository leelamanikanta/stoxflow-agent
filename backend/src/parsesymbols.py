import json
import os
from dotenv import load_dotenv
import litellm

load_dotenv()

# Map GOOGLE_API_KEY to GEMINI_API_KEY for LiteLLM
if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

def load_symbols():
    # Load the symbols database from data/NSE_MIS.json relative to the root directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(base_dir, 'data', 'NSE_MIS.json')
    with open(file_path, 'r') as f:
        upstox_symbols = json.load(f)
    return upstox_symbols

# Define default models
DEFAULT_LOCAL_MODEL = os.getenv("LOCAL_LLM_MODEL", "ollama/qwen2.5:3b")
DEFAULT_CLOUD_MODEL = os.getenv("CLOUD_LLM_MODEL", "gemini/gemini-2.5-flash-lite")

def parse_symbols(symbol: str, model_name: str = None) -> str:
    """
    Parses a string of symbols into a list of individual symbols using the specified model.
    """
    upstox_symbols = load_symbols()
    # Pre-filter the list so we don't overflow the LLM's context window with the entire file
    filtered_matches = [s for s in upstox_symbols if symbol.upper() in s.get('name', '').upper() or symbol.upper() in s.get('trading_symbol', '').upper()]

    # If model_name is provided and doesn't have the provider prefix, and matches default local model name (e.g. "qwen2.5:3b"), prepend "ollama/"
    local_model = model_name or DEFAULT_LOCAL_MODEL
    if local_model and "/" not in local_model:
        local_model = f"ollama/{local_model}"

    cloud_model = DEFAULT_CLOUD_MODEL

    system_prompt = f"""
    You are a stock research assistant. Your task is to extract the exact matching symbol for: "{symbol}" from the provided list.

    Available matches:
    {json.dumps(filtered_matches[:50], indent=2)}

    Please return ONLY a JSON list of matching symbols matching this structure:
    here is an example of the expected output:
    [
      {{
        "instrument_key": "NSE_EQ|INE144J01027",
        "name": "20 MICRONS LTD",
        "input_symbol": "20MICRONS",
        "trading_symbol": "20MICRONS"
      }}
    ]
    """

    content = None
    # 1. Attempt Local LLM via LiteLLM
    try:
        print(f"Attempting local LLM symbol resolution for: {symbol} using {local_model}")
        # LiteLLM completion call
        response = litellm.completion(
            model=local_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Find matches for: {symbol}"}
            ],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        
        # Validate that content is a valid JSON list
        cleaned = content
        if cleaned.startswith("```json"):
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            if isinstance(parsed, dict):
                # If wrapped in a dictionary, try to extract the inner list
                for k, v in parsed.items():
                    if isinstance(v, list):
                        content = json.dumps(v)
                        break
                else:
                    if "instrument_key" in parsed or "trading_symbol" in parsed:
                        content = json.dumps([parsed])
                    else:
                        raise ValueError("JSON returned is an object, not a list.")
            else:
                raise ValueError("JSON returned is not a list.")
                
    except Exception as e:
        print(f"Warning: Local LLM symbol resolution failed or returned invalid JSON ({e}). Falling back to cloud model ({cloud_model})...")
        
        # 2. Fallback to Cloud model via LiteLLM
        try:
            response = litellm.completion(
                model=cloud_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Find matches for: {symbol}"}
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
        except Exception as ex:
            print(f"Error: Cloud LLM symbol resolution failed: {ex}")
            # If all LLMs fail, build a basic heuristic fallback list from filtered_matches to prevent crash
            if filtered_matches:
                basic_match = [{
                    "instrument_key": filtered_matches[0].get("instrument_key", ""),
                    "name": filtered_matches[0].get("name", ""),
                    "input_symbol": symbol,
                    "trading_symbol": filtered_matches[0].get("trading_symbol", "")
                }]
                return json.dumps(basic_match)
            raise ex

    return content
