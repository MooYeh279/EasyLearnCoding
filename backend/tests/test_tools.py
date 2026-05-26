import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ── web_search tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_search_duckduckgo():
    """web_search should call DuckDuckGo and return formatted results."""
    from services.tools import web_search, _format_search_results

    raw = [
        {"title": "Python asyncio", "href": "https://docs.python.org/3/library/asyncio.html", "body": "asyncio is a library..."},
    ]
    mock_results = _format_search_results("asyncio", raw, 3)

    with patch("services.tools._get_search_provider", return_value="duckduckgo"), \
         patch("services.tools.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = mock_results
        results = await web_search("asyncio", max_results=3)
        assert len(results) == 1
        assert results[0]["title"] == "Python asyncio"
        assert results[0]["url"] == "https://docs.python.org/3/library/asyncio.html"
        assert "snippet" in results[0]


@pytest.mark.asyncio
async def test_web_search_handles_errors():
    """web_search should return empty list on DuckDuckGo error."""
    from services.tools import web_search

    with patch("services.tools._get_search_provider", return_value="duckduckgo"), \
         patch("services.tools.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = []
        results = await web_search("asyncio")
        assert results == []


# ── web_fetch tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_fetch_cross_domain_blocked():
    """web_fetch should block cross-domain redirects."""
    from services.tools import web_fetch

    with patch("services.tools.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.url = "https://evil.com/page"
        mock_response.text = "<html><body>evil</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html"}

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await web_fetch("https://trusted.com/page", max_chars=100)
        assert "Blocked cross-domain redirect" in result


@pytest.mark.asyncio
async def test_web_fetch_html_extract():
    """web_fetch should extract readable text from HTML using readability."""
    from services.tools import web_fetch

    with patch("services.tools.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.url = "https://example.com/page"
        mock_response.text = "<html><head><title>Test</title></head><body><p>Hello World</p></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html"}

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await web_fetch("https://example.com/page", max_chars=500)
        assert "Hello World" in result


@pytest.mark.asyncio
async def test_web_fetch_json_content():
    """web_fetch should return formatted JSON for application/json responses."""
    from services.tools import web_fetch

    with patch("services.tools.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.url = "https://api.example.com/data"
        mock_response.text = '{"key": "value"}'
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "application/json"}

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await web_fetch("https://api.example.com/data", max_chars=500)
        assert "key" in result
        assert "value" in result


@pytest.mark.asyncio
async def test_web_fetch_error():
    """web_fetch should return failure message on error."""
    from services.tools import web_fetch

    with patch("services.tools.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("timeout")

        result = await web_fetch("https://example.com/page")
        assert "[Failed to fetch content" in result or "timeout" in result


@pytest.mark.asyncio
async def test_web_fetch_same_domain_redirect():
    """web_fetch should follow same-domain redirects."""
    from services.tools import web_fetch

    with patch("services.tools.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.url = "https://example.com/other-page"
        mock_response.text = "<html><body>redirected content</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html"}

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await web_fetch("https://example.com/page", max_chars=500)
        assert "redirected content" in result


# ── HTML helper tests ──────────────────────────────────────────────────

def test_strip_tags():
    """_strip_tags should remove HTML tags and decode entities."""
    from services.tools import _strip_tags
    assert _strip_tags("<p>Hello &amp; World</p>") == "Hello & World"
    assert _strip_tags("<script>var x=1;</script><p>Content</p>") == "Content"


def test_normalize():
    """_normalize should collapse whitespace."""
    from services.tools import _normalize
    assert _normalize("  hello   world  ") == "hello world"
    assert _normalize("a\n\n\n\nb") == "a\n\nb"


def test_validate_url():
    """_validate_url should check scheme and domain."""
    from services.tools import _validate_url
    assert _validate_url("https://example.com")[0] is True
    assert _validate_url("ftp://example.com")[0] is False
    assert _validate_url("not-a-url")[0] is False


def test_html_to_markdown():
    """_html_to_markdown should convert basic HTML to markdown."""
    from services.tools import _html_to_markdown
    html = '<h1>Title</h1><p>Paragraph</p><a href="https://example.com">Link</a>'
    md = _html_to_markdown(html)
    assert "# Title" in md
    assert "[Link](https://example.com)" in md


def test_extract_html_with_readability():
    """_extract_html should use readability for main content extraction."""
    from services.tools import _extract_html
    html = """
    <html><head><title>Test Page</title></head>
    <body><nav>Navigation</nav><article><p>Main content here</p></article></body></html>
    """
    result = _extract_html(html)
    assert "Main content here" in result


def test_extract_html_fallback():
    """_extract_html should fall back to tag stripping when readability fails."""
    from services.tools import _extract_html
    with patch("readability.Document", side_effect=Exception("parse error")):
        result = _extract_html("<html><body>Fallback text</body></html>")
        assert "Fallback text" in result
