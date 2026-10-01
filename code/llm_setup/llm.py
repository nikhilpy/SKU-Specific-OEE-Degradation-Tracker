import json
import os
import sys
import urllib.error
import urllib.request
from dotenv import load_dotenv

_CODE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _CODE_ROOT not in sys.path:
    sys.path.insert(0, _CODE_ROOT)

try:
    from misc.snowflake_client import get_connection
except ImportError:
    get_connection = None

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

LAST_USED_LLM = {
    "backend": "unknown",
    "model": "unknown",
    "reason": ""
}


def list_models():
    """
    Return the models currently pulled in the local Ollama server.
    """
    with urllib.request.urlopen(
        f"{OLLAMA_HOST}/api/tags", timeout=REQUEST_TIMEOUT
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return [model["name"] for model in payload.get("models", [])]


def chat(messages, model=None, temperature=0.2, format=None):
    """
    Send a chat conversation to Snowflake Cortex, falling back to local Ollama server.
    """
    global LAST_USED_LLM
    
    if get_connection:
        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cortex_model = 'llama3.1-70b'
                
                prompt_content = ""
                for m in messages:
                    prompt_content += f"{m['role'].capitalize()}: {m['content']}\n\n"
                    
                cursor.execute(
                    "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                    (cortex_model, prompt_content)
                )
                result = cursor.fetchone()
                
                text_response = result[0]
                if isinstance(text_response, str):
                    try:
                        text_response = json.loads(text_response)
                    except ValueError:
                        pass
                        
                LAST_USED_LLM["backend"] = "snowflake_cortex"
                LAST_USED_LLM["model"] = cortex_model
                LAST_USED_LLM["reason"] = "Successfully used Snowflake AI_COMPLETE"
                return text_response
            finally:
                cursor.close()
        except Exception as e:
            print(f"[LLM] Snowflake CORTEX.COMPLETE failed: {e}. Falling back to Ollama.")
            LAST_USED_LLM["reason"] = f"Snowflake failed ({e}), fell back to Ollama"
    else:
        LAST_USED_LLM["reason"] = "misc.snowflake_client not found, fell back to Ollama"

    # --- Ollama Fallback ---
    LAST_USED_LLM["backend"] = "ollama_local"
    LAST_USED_LLM["model"] = model or DEFAULT_MODEL

    body = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature}
    }

    if format:
        body["format"] = format

    request = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. "
            f"Start it with 'ollama serve'."
        ) from e

    return payload["message"]["content"]


def complete(prompt, model=None, temperature=0.2, format=None):
    """
    Single-turn completion. Uses chat() to try Snowflake AI_COMPLETE first, falling back to Ollama.
    """
    return chat(
        [{"role": "user", "content": prompt}],
        model=model,
        temperature=temperature,
        format=format
    )


def ask_json(prompt, model=None, temperature=0.2, retries=3):
    """
    Ask for JSON and return it already parsed.
    """
    last_err = None
    for attempt in range(retries):
        response = complete(
            prompt,
            model=model,
            temperature=temperature,
            format="json"
        )

        if isinstance(response, dict):
            return response

        if isinstance(response, str):
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            try:
                return json.loads(cleaned)
            except ValueError as e:
                import re
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    # Clean trailing commas
                    json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                    try:
                        return json.loads(json_str)
                    except ValueError as e2:
                        last_err = e2
                else:
                    last_err = e
        else:
            try:
                return json.loads(response)
            except Exception as e:
                last_err = e
                
        # If we reach here, we failed to parse. Add error to prompt for next retry.
        prompt += f"\n\nPrevious attempt failed with error: {last_err}. Ensure your response is strictly valid JSON."

    raise ValueError(f"Failed to parse JSON after {retries} attempts. Last error: {last_err}. Raw output: {response}")


def chat_with_tools(messages, tools, model=None, temperature=0.2):
    """
    Tries Snowflake AI_COMPLETE first by formatting the tools into the prompt.
    Falls back to Ollama with native tool calling if Snowflake fails.
    """
    global LAST_USED_LLM
    
    if get_connection:
        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cortex_model = 'llama3.1-70b'
                
                # Format messages into a single prompt for Cortex
                prompt_content = ""
                for m in messages:
                    prompt_content += f"{m['role'].capitalize()}: {m['content']}\n\n"
                
                cortex_prompt = (
                    f"{prompt_content}"
                    f"You have access to the following tools:\n{json.dumps(tools, indent=2)}\n"
                    f"To use a tool, output a JSON object EXACTLY matching this format and nothing else:\n"
                    f"{{\"tool_calls\": [{{\"function\": {{\"name\": \"<tool_name>\", \"arguments\": {{\"<arg_name>\": \"<arg_value>\"}}}}]}}\n"
                )
                
                cursor.execute(
                    "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                    (cortex_model, cortex_prompt)
                )
                result = cursor.fetchone()
                
                LAST_USED_LLM["backend"] = "snowflake_cortex"
                LAST_USED_LLM["model"] = cortex_model
                LAST_USED_LLM["reason"] = "Successfully used Snowflake AI_COMPLETE"
                
                text_response = result[0]
                
                import re
                # Try to extract JSON block
                match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if "tool_calls" in parsed:
                        return parsed["tool_calls"]
                
                return []
            finally:
                cursor.close()
        except Exception as e:
            print(f"[LLM] Snowflake CORTEX.COMPLETE failed: {e}. Falling back to Ollama.")
            LAST_USED_LLM["reason"] = f"Snowflake failed ({e}), fell back to Ollama"
    else:
        LAST_USED_LLM["reason"] = "misc.snowflake_client not found, fell back to Ollama"

    LAST_USED_LLM["backend"] = "ollama_local"
    LAST_USED_LLM["model"] = model or DEFAULT_MODEL
    
    body = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "tools": tools,
        "stream": False,
        "options": {"temperature": temperature}
    }
    
    request = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_HOST}.") from e
        
    return payload.get("message", {}).get("tool_calls", [])


if __name__ == "__main__":
    print(f"Ollama host: {OLLAMA_HOST}")
    print(f"Default model: {DEFAULT_MODEL}")

    print("\nAvailable models:")
    for name in list_models():
        print(f"  {name}")

    print("\nTest completion:")
    print(
        complete(
            "Reply with exactly one word: the capital of France."
        )
    )
