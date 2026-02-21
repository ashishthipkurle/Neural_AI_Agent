import os
import logging
import json
import hashlib
from datetime import datetime

# Attempt to import the network wrapper's download function; fallback if unavailable
try:
    from network_wrapper import download_with_retry
except ImportError:
    # Simple fallback implementation using requests with urllib3 retry logic
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    def download_with_retry(url, dest_path, retries=3, backoff_factor=1.0, timeout=10):
        session = requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        response = session.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return dest_path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEST_DIR = os.path.join(BASE_DIR, 'network_resilience_test')
os.makedirs(TEST_DIR, exist_ok=True)
LOG_FILE = os.path.join(TEST_DIR, 'network_resilience.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NetworkResilienceTest')

# URLs and expected checksum (placeholder values)
PRIMARY_URL = 'https://example.com/sample_file.bin'
FALLBACK_URL = 'https://fallback.example.com/sample_file.bin'
EXPECTED_SHA256 = 'd2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2'
DEST_PATH = os.path.join(TEST_DIR, 'downloaded_file.bin')

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def compute_sha256(file_path):
    """Return the hex SHA‑256 digest of *file_path*.
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def append_to_ltm(summary):
    """Append *summary* dict to the LTM JSON file under agent_data.
    """
    ltm_path = os.path.abspath(os.path.join(BASE_DIR, '..', 'agent_data', 'ltm_resilience.json'))
    os.makedirs(os.path.dirname(ltm_path), exist_ok=True)
    if os.path.exists(ltm_path):
        try:
            with open(ltm_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []
    else:
        data = []
    data.append(summary)
    with open(ltm_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# ---------------------------------------------------------------------------
# Main test logic
# ---------------------------------------------------------------------------
def main():
    logger.info('=== Network Resilience Test Started ===')
    success = False

    # Attempt primary download
    try:
        logger.info(f'Attempting primary URL: {PRIMARY_URL}')
        download_with_retry(PRIMARY_URL, DEST_PATH, retries=3, backoff_factor=1.0)
        success = True
        logger.info('Primary download succeeded')
    except Exception as e:
        logger.warning(f'Primary download failed: {e}')
        # Fallback with more aggressive retry/back‑off
        try:
            logger.info(f'Attempting fallback URL: {FALLBACK_URL}')
            download_with_retry(FALLBACK_URL, DEST_PATH, retries=5, backoff_factor=2.0)
            success = True
            logger.info('Fallback download succeeded')
        except Exception as e2:
            logger.error(f'Fallback download also failed: {e2}')
            success = False

    # Verify checksum if we have a file
    checksum_match = False
    if success and os.path.exists(DEST_PATH):
        actual_hash = compute_sha256(DEST_PATH)
        checksum_match = actual_hash.lower() == EXPECTED_SHA256.lower()
        if checksum_match:
            logger.info('Checksum validation passed')
        else:
            logger.error(f'Checksum mismatch – expected {EXPECTED_SHA256}, got {actual_hash}')
    else:
        logger.error('File not present – skipping checksum validation')

    # Record the outcome in LTM
    summary = {
        'timestamp': datetime.now().isoformat(),
        'test_dir': TEST_DIR,
        'download_success': success,
        'checksum_match': checksum_match,
        'downloaded_file': DEST_PATH if success else None,
        'log_file': LOG_FILE,
    }
    append_to_ltm(summary)
    logger.info('Resilience summary written to LTM')
    logger.info('=== Network Resilience Test Completed ===')

if __name__ == '__main__':
    main()
