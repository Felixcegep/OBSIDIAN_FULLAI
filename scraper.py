import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse


def scrape(url, delay=1, timeout=10):
    """
    Improved web scraper with better error handling and performance

    Args:
        url (str): The URL to scrape
        delay (float): Delay between requests to be respectful
        timeout (int): Request timeout in seconds

    Returns:
        str: Extracted text content or empty string if failed
    """
    try:
        # Add headers to appear more like a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Make request with timeout and headers
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements for cleaner text
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract text from multiple elements, not just paragraphs
        content_parts = []

        # Get text from various content elements
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div']):
            text = element.get_text(strip=True)
            if text and len(text) > 10:  # Only include substantial text
                content_parts.append(text)

        # Join with newlines and clean up
        content = '\n'.join(content_parts)

        # Be respectful - add delay
        time.sleep(delay)

        return content.strip()

    except requests.exceptions.RequestException as e:
        print(f"Request failed for {url}: {e}")
        return ""
    except Exception as e:
        print(f"Parsing failed for {url}: {e}")
        return ""