import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

_CODE_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if _CODE_ROOT not in sys.path:
    sys.path.insert(0, _CODE_ROOT)

from misc.snowflake_client import get_connection


load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

# def list_models():
#     """
#     Return the models currently pulled in the local Ollama server.
#     """
#     with urllib.request.urlopen(
#         f"{OLLAMA_HOST}/api/tags", timeout=REQUEST_TIMEOUT
#     ) as response:
#         payload = json.loads(response.read().decode("utf-8"))

#     return [model["name"] for model in payload.get("models", [])]


# def chat(messages, model=None, temperature=0.2, format=None):
#     """
#     Send a chat conversation to the local Ollama server.

#     messages: list of {"role": ..., "content": ...} dicts
#     format:   "json" to force structured output, None for plain text
#     """
#     model = model or DEFAULT_MODEL

#     body = {
#         "model": model,
#         "messages": messages,
#         "stream": False,
#         "options": {"temperature": temperature}
#     }

#     if format:
#         body["format"] = format

#     request = urllib.request.Request(
#         f"{OLLAMA_HOST}/api/chat",
#         data=json.dumps(body).encode("utf-8"),
#         headers={"Content-Type": "application/json"},
#         method="POST"
#     )

#     try:
#         with urllib.request.urlopen(
#             request, timeout=REQUEST_TIMEOUT
#         ) as response:
#             payload = json.loads(response.read().decode("utf-8"))

#     except urllib.error.HTTPError as e:
#         detail = e.read().decode("utf-8", "replace")

#         raise RuntimeError(
#             f"Ollama rejected the request ({e.code}) for model "
#             f"{model!r}: {detail}. Check 'ollama list'."
#         ) from e

#     except urllib.error.URLError as e:
#         raise RuntimeError(
#             f"Cannot reach Ollama at {OLLAMA_HOST}. "
#             f"Start it with 'ollama serve'."
#         ) from e

#     return payload["message"]["content"]


def complete(prompt, model=None, temperature=0.2, format=None):
    """
    Single-turn completion via Snowflake AI_COMPLETE.

    Requires a non-trial account: trial accounts reject AI_COMPLETE
    with "AI function COMPLETE is not available for trial accounts".
    """

    print("In complete")
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT AI_COMPLETE(
                'llama3.1-8b',
                %s
            )
            """,
            (prompt,)
        )

        result = cursor.fetchone()

        return result[0]

    finally:
        cursor.close()
        conn.close()


# def complete(prompt, model=None, temperature=0.2, format=None):
#     """
#     Single-turn completion through the local Ollama server.
#     """
#     return chat(
#         [{"role": "user", "content": prompt}],
#         model=model,
#         temperature=temperature,
#         format=format
#     )


def ask_json(prompt, model=None, temperature=0.2):
    """
    Ask for JSON and return it already parsed.
    """
    response = complete(
        prompt,
        model=model,
        temperature=temperature,
        format="json"
    )

    return json.loads(response)


if __name__ == "__main__":
    print(f"Ollama host: {OLLAMA_HOST}")
    print(f"Default model: {DEFAULT_MODEL}")

    print("\nTest completion:")
    print(
        complete(
            "Reply with exactly one word: the capital of France."
        )
    )
