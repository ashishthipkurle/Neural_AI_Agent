"""
FAISS Snapshot Checksum & Schema Validator.

Architecture:
    - Protects the quantitative engine from corrupted or poisoned index binaries.
    - Mathematically proves consistency of restored states.
    - Validates: SHA-256 checksums, schema_versions, vector counts, centroid constraints.
"""
import os
import json
import logging
import hashlib
from typing import Dict, Any

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class SnapshotValidator:
    """
    Gatekeeper that strictly refuses to load compromised or mismatched FAISS snapshots.
    """

    def __init__(self, current_feature_schema: str) -> None:
        self.logger = logging.getLogger("SnapshotValidator")
        self.current_feature_schema = current_feature_schema

    def _generate_sha256(self, filepath: str) -> str:
        """Calculate cryptographically secure hash of the index binary."""
        h = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except FileNotFoundError:
            return ""

    def validate_and_load(self, index_filepath: str, metadata_filepath: str) -> Any:
        """
        Validates all consistency constraints. Returns the loaded FAISS index if valid.
        Raises ValueError if ANY check fails.
        """
        if not os.path.exists(index_filepath):
            raise ValueError(f"Index file missing: {index_filepath}")
        if not os.path.exists(metadata_filepath):
            raise ValueError(f"Metadata file missing: {metadata_filepath}")

        with open(metadata_filepath, 'r') as f:
            metadata = json.load(f)

        self.logger.info(f"Validating snapshot {metadata.get('snapshot_id')}...")

        # 1. SHA-256 Checksum Match
        actual_hash = self._generate_sha256(index_filepath)
        expected_hash = metadata.get("sha256")
        if actual_hash != expected_hash:
            self.logger.critical(f"INTEGRITY FAILURE: SHA-256 mismatch.\nExpected: {expected_hash}\nActual: {actual_hash}")
            raise ValueError("SHA-256 checksum validation failed.")

        # 2. Feature Schema Compatibility Match
        snapshot_schema = metadata.get("feature_schema_version")
        if snapshot_schema != self.current_feature_schema:
            self.logger.critical(f"SCHEMA FAILURE: Engine expects schema {self.current_feature_schema}, Snapshot uses {snapshot_schema}.")
            raise ValueError("Feature Schema Version mismatch.")

        # 3. Load Index binary safely
        if not FAISS_AVAILABLE:
            raise ValueError("FAISS not installed. Cannot load binary index.")
            
        try:
            index = faiss.read_index(index_filepath)
        except Exception as e:
            self.logger.critical(f"FAISS Deserialization Error: {e}")
            raise ValueError(f"Binary load failed: {e}")

        # 4. Vector Count Consistency
        expected_vectors = metadata.get("total_vectors", 0)
        actual_vectors = index.ntotal
        if expected_vectors != actual_vectors:
            self.logger.critical(f"VECTOR COUNT FAILURE: Metadata declares {expected_vectors}, Binary has {actual_vectors}.")
            raise ValueError("Vector count inconsistency.")

        # 5. Centroid Constraints (If IVF)
        if hasattr(index, 'nlist'):
            # Must have at least 1 centroid, or more depending on training config
            if index.nlist <= 0:
                self.logger.critical(f"CENTROID FAILURE: IVF Index has {index.nlist} centroids (Must be > 0).")
                raise ValueError("Centroid count inconsistency.")

        self.logger.info("Validation passed successfully. Snapshot is pristine and safe for deployment.")
        return index
