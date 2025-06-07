import requests
import trafilatura
from bs4 import BeautifulSoup
import re


def _manual_fallback_scraper(html_content: str, url: str) -> str:
    """
    A robust manual fallback scraper that tries several strategies to find main content.
    This is called by universal_scraper if trafilatura fails.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Get page title for context
    page_title = soup.title.string.strip() if soup.title else 'No Title'

    # 2. Aggressively decompose irrelevant tags
    for tag in soup(['nav', 'header', 'footer', 'aside', 'form', 'script', 'style', 'button', 'iframe']):
        tag.decompose()
    # Also remove common noise containers by class/id (using CSS selectors)
    for selector in [".sidebar", "#sidebar", ".comments", "#comments", ".share", ".social", ".ad", "#ads"]:
        for element in soup.select(selector):
            element.decompose()

    # 3. Find the primary content container using a list of common selectors
    main_content = None
    # More comprehensive list of potential content containers
    selectors = [
        'main', 'article', 'div[class*="post"]', 'div[id="content"]',
        'div[class*="content"]', 'div[id="main"]', 'div[class*="main"]',
        'div[class*="entry-content"]'
    ]
    for selector in selectors:
        main_content = soup.select_one(selector)
        if main_content:
            break

    # 4. If no specific container is found, use the whole body as a last resort
    if not main_content:
        main_content = soup.body
        if not main_content:
            return ""  # Return empty if there's no body

    # 5. Extract structured text from the chosen container
    content_parts = []
    # Find all relevant tags: headings, paragraphs, code blocks, and list items
    for element in main_content.find_all(['h1', 'h2', 'h3', 'p', 'pre', 'li'], recursive=True):
        text = ''
        if element.name.startswith('h'):
            # Add extra newlines around headings for readability
            text = f"\n\n{element.get_text(strip=True)}\n"
        elif element.name == 'pre':
            # Preserve code formatting and add markers
            text = f"\n```\n{element.get_text()}\n```\n"
        else:  # 'p' and 'li'
            text = element.get_text(strip=True)

        # Filter out short, non-substantive text blocks
        if len(text.split()) > 4:
            content_parts.append(text)

    # 6. Join, clean, and format the final output
    full_text = "\n".join(content_parts)
    # Normalize whitespace and excessive newlines
    clean_text = re.sub(r'\n{3,}', '\n\n', full_text).strip()

    return f"Source: {url}\nTitle: {page_title}\n\n{clean_text}"


def universal_scraper(url: str, timeout: int = 10, max_chars: int = 8192) -> str:
    """
    A highly robust and universal web scraper for LLMs.

    It uses a hybrid approach:
    1. Tries the specialized 'trafilatura' library for fast and accurate extraction.
    2. If that fails, it uses a smart manual fallback with BeautifulSoup heuristics.

    Args:
        url (str): The URL to scrape.
        timeout (int): Request timeout in seconds.
        max_chars (int): Max characters to return to respect LLM context windows.

    Returns:
        A clean, formatted string of the website's main content, or None on failure.
    """
    try:
        # Download the webpage once
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        html_content = response.text

        # --- Tier 1: Try Trafilatura (The Gold Standard) ---
        extracted_text = trafilatura.extract(
            html_content,
            include_comments=False,
            include_links=False,
            include_tables=False,  # Tables can be noisy
            favor_precision=True  # Be stricter about what is considered main content
        )

        if extracted_text and len(extracted_text) > 250:  # Check if it returned substantial content
            page_title = trafilatura.extract_metadata(html_content).title or "No Title"
            formatted_content = f"Source: {url}\nTitle: {page_title}\n\n{extracted_text}"
            return formatted_content[:max_chars]

        # --- Tier 2: Manual Fallback Scraper ---
        # If Trafilatura fails, our robust manual scraper gets its chance.
        manual_content = _manual_fallback_scraper(html_content, url)
        if manual_content:
            return manual_content[:max_chars]

        return ""  # Return empty string if both methods fail

    except requests.exceptions.RequestException as e:
        print(f"[Scraper Error] Request failed for {url}: {e}")
        return None
    except Exception as e:
        print(f"[Scraper Error] An unexpected error occurred for {url}: {e}")
        return None


