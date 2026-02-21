import requests

class NETWORK_ERROR(Exception):
    """Custom exception to simulate network errors on initial attempts."""
    pass

# Module-level counter to track number of download attempts
_attempt_counter = 0
_MAX_INJECTED_ERRORS = 2

def download(url, **kwargs):
    """Download content from the given URL using requests.get.

    On the first two calls, raises NETWORK_ERROR to simulate a network failure.
    Subsequent calls behave normally.
    """
    global _attempt_counter
    _attempt_counter += 1
    if _attempt_counter <= _MAX_INJECTED_ERRORS:
        raise NETWORK_ERROR(f"Simulated network error on attempt {_attempt_counter} for URL: {url}")
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response.content

def reset_counter():
    """Reset the internal attempt counter (useful for testing)."""
    global _attempt_counter
    _attempt_counter = 0
