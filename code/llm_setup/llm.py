import json
import os
import urllib.error
import urllib.request
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))


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
    Send a chat conversation to the local Ollama server.

    messages: list of {"role": ..., "content": ...} dicts
    format:   "json" to force structured output, None for plain text
    """
    model = model or DEFAULT_MODEL

    body = {
        "model": model,
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
    Single-turn completion, without chat templating.
    """
    return chat(
        [{"role": "user", "content": prompt}],
        model=model,
        temperature=temperature,
        format=format
    )


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

    print("\nAvailable models:")
    for name in list_models():
        print(f"  {name}")

    print("\nTest completion:")
    print(
        complete(
            "Reply with exactly one word: the capital of France."
        )
    )
