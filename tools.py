import os
import subprocess
from googlesearch import search
import requests
from bs4 import BeautifulSoup

def x_search(query: str, num_results: int = 1) -> list[dict]:
    """
    Searches x.com for a given query.
    """
    return site_search(f"{query} site:x.com", num_results=num_results)

def site_search(query: str, num_results: int = 1) -> list[dict]:
    """
    Searches the web for a given query and returns the top results with their content.

    Args:
        query (str): The search query.
        num_results (int): The number of results to return.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains
                    'url' and 'content' of a search result.
    """
    results = []
    try:
        # Using the google_search tool provided by the environment
        search_results = search(query, num_results=num_results)
        for url in search_results:
            content = fetch_url(url)
            if "Error" in content:
                print(f"Error fetching {url}: {content}")
            results.append({"url": url, "content": content[:4000]}) # Limit content size
    except Exception as e:
        print(f"An error occurred during web search: {e}")
        return [{"url": "", "content": f"An error occurred during web search: {e}"}]
    return results

def create_artifact(filename: str, content: str) -> str:
    """
    Creates a file with the given content in the 'artifacts' directory.

    Args:
        filename (str): The name of the file to create.
        content (str): The content to write to the file.

    Returns:
        str: A message indicating the path to the created file or an error.
    """
    try:
        # Basic sanitization to prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return "Error: Invalid filename. For security, filenames cannot contain '..', '/', or '\\'."

        artifacts_dir = "artifacts"
        if not os.path.exists(artifacts_dir):
            os.makedirs(artifacts_dir)

        filepath = os.path.join(artifacts_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: Artifact '{filename}' was created and is available for download."
    except Exception as e:
        return f"Error: Could not create artifact. Reason: {e}"

def execute_python(code: str) -> str:
    """
    Executes Python code using a subprocess with a timeout.

    Args:
        code (str): The Python code to execute.

    Returns:
        str: The stdout and stderr from the executed code.
    """
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=120  # 120-second timeout
        )
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        if not output:
            return "Code executed successfully with no output."
        return output
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out after 120 seconds."
    except Exception as e:
        return f"An error occurred during Python execution: {e}"

def fetch_url(url: str) -> str:
    """
    Fetches the textual content of a given URL.

    Args:
        url (str): The URL to fetch.

    Returns:
        str: The text content of the URL, or an error message.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        lines = (line.strip() for line in soup.get_text().splitlines())
        return " ".join(line for line in lines if line)
    except requests.exceptions.RequestException as e:
        return f"Error fetching content from {url}: {e}"
