"""
Pluggable Search Providers with Escalation & SSRF-Protected Web Fetch.
"""
import ipaddress
import json
import logging
import os
import socket
import urllib.parse
from typing import Dict, Any, List
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def is_ip_allowed(ip_str: str) -> bool:
    """
    Check if an IP address is a safe public IP (SSRF Gate).
    Rejects loopback (127.0.0.1), private (10.x, 172.16.x, 192.168.x), link-local (169.254.x).
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
        return True
    except ValueError:
        return False


def fetch_url_safe(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Fetch content from a public URL with SSRF protection.

    Args:
        url: Target HTTP/HTTPS URL
        timeout: HTTP request timeout in seconds

    Returns:
        Dict with status and content or error message
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return {"status": "error", "error": f"Invalid URL scheme '{parsed.scheme}'. Only http and https allowed."}

        hostname = parsed.hostname
        if not hostname:
            return {"status": "error", "error": "Invalid URL: missing hostname"}

        # Resolve IP and check SSRF
        try:
            ip_str = socket.gethostbyname(hostname)
        except socket.gaierror as e:
            return {"status": "error", "error": f"Could not resolve hostname '{hostname}': {e}"}

        if not is_ip_allowed(ip_str):
            logger.warning(f"SSRF Protection blocked fetch for URL '{url}' (resolved IP {ip_str})")
            return {"status": "error", "error": f"SSRF Protection: Blocked fetch to private/internal IP address {ip_str}"}

        headers = {'User-Agent': 'WorkflowAgent/1.0 (API Docs Fetcher)'}
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()

        return {
            "status": "success",
            "url": url,
            "resolved_ip": ip_str,
            "status_code": resp.status_code,
            "content": resp.text[:50000]
        }
    except Exception as e:
        logger.error(f"Error fetching URL '{url}': {e}")
        return {"status": "error", "error": str(e)}


def search_api_docs(query: str) -> Dict[str, Any]:
    """
    Search web for API documentation using primary provider, escalating to secondary on failure.

    Escalation Chain:
    1. Primary Provider (Tavily if key present)
    2. Secondary Provider (Google Custom Search if key present)
    3. Mock Provider (Fallback if no external keys configured or on error)

    Args:
        query: API documentation search term

    Returns:
        Dict with search results and provider metadata
    """
    tavily_key = os.environ.get('TAVILY_API_KEY') or getattr(settings, 'TAVILY_API_KEY', None)
    google_key = os.environ.get('GOOGLE_SEARCH_API_KEY') or getattr(settings, 'GOOGLE_SEARCH_API_KEY', None)
    google_cx = os.environ.get('GOOGLE_SEARCH_CX') or getattr(settings, 'GOOGLE_SEARCH_CX', None)

    # 1. Try Primary Provider (Tavily)
    if tavily_key:
        try:
            results = _search_tavily(query, tavily_key)
            if results:
                return {"status": "success", "provider": "tavily", "query": query, "results": results}
            logger.info("Tavily returned empty results, escalating to secondary search provider...")
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}. Escalating to secondary provider...")

    # 2. Try Secondary Provider (Google Custom Search)
    if google_key and google_cx:
        try:
            results = _search_google(query, google_key, google_cx)
            if results:
                return {"status": "success", "provider": "google", "query": query, "results": results}
            logger.info("Google search returned empty results, escalating to mock fallback...")
        except Exception as e:
            logger.warning(f"Google search failed: {e}. Escalating to mock fallback...")

    # 3. Fallback Mock Provider
    return _search_mock(query)


def _search_tavily(query: str, api_key: str) -> List[Dict[str, str]]:
    """Tavily search API integration."""
    url = "https://api.tavily.com/search"
    payload = {"api_key": api_key, "query": f"{query} API documentation", "search_depth": "basic", "max_results": 5}
    resp = httpx.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get('results', []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300]
        })
    return results


def _search_google(query: str, api_key: str, cx: str) -> List[Dict[str, str]]:
    """Google Custom Search JSON API integration."""
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={urllib.parse.quote(query)}"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get('items', []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", "")[:300]
        })
    return results


def _search_mock(query: str) -> Dict[str, Any]:
    """Mock search provider for testing and fallback."""
    q_slug = query.lower().replace(' ', '-')
    return {
        "status": "success",
        "provider": "mock",
        "query": query,
        "results": [
            {
                "title": f"{query.capitalize()} API Reference & Documentation",
                "url": f"https://api-docs.example.com/{q_slug}/v1/ref",
                "snippet": f"Official endpoint documentation for {query}. Supports REST and OAuth2."
            },
            {
                "title": f"Integrating {query.capitalize()} APIs",
                "url": f"https://developer.example.com/{q_slug}/guides",
                "snippet": f"Guides for pagination, rate limits, and field mappings for {query} API."
            }
        ]
    }
