import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SAMURAI_API_KEY")
URL = "https://samuraiapi.in/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_grok_response(conversation):
    """
    Sends a conversation to the Grok API and gets a response.

    Args:
        conversation (list): A list of message dictionaries, e.g.,
                             [{"role": "user", "content": "Hello"}]

    Returns:
        str: The content of the AI's response, or an error message.
    """
    payload = {
        "model": "xai/grok-4",
        "messages": conversation,
        "temperature": 0.7,
        "max_tokens": 999999999
    }

    try:
        response = requests.post(URL, headers=HEADERS, json=payload)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return f"Sorry, I couldn't connect to the Grok API. Error: {e}"
    except KeyError:
        return "Sorry, I received an unexpected response from the Grok API."
