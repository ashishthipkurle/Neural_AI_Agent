
import logging
import json
import os
import pickle
import uuid
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError:
    faiss = None
    SentenceTransformer = None

class VectorStore:
    """
    Long-term memory storage using FAISS and SentenceTransformers.
    
    Features:
    - Semantic search
    - Memory CRUD operations
    - User-editable entries
    - Deletion support
    """
    def __init__(self, db_path="agent/db/memory.index", model_name='all-MiniLM-L6-v2'):
        self.logger = logging.getLogger("VectorStore")
        self.db_path = db_path
        self.metadata_path = db_path.replace(".index", ".meta")
        self.model_name = model_name
        self.model = None
        self.index = None
        self.metadata: List[Dict[str, Any]] = []  # List of dicts matching index
        
        # Ensure db dir
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        if not faiss or not SentenceTransformer:
            self.logger.error("FAISS/SentenceTransformers not installed. Memory disabled.")
            return

        try:
            self.logger.info(f"Loading Embedding Model: {model_name}...")
            self.model = SentenceTransformer(model_name)
            self.logger.info("Model loaded.")
            
            self._load_index()
            
        except (OSError, ImportError, MemoryError, Exception) as e:
            self.logger.error(f"Failed to load VectorStore model (memory/dependency issue): {e}")
            self.logger.warning("Semantic memory features disabled to prevent crash.")
            self.model = None
            self.index = None

    def _load_index(self):
        if os.path.exists(self.db_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.db_path)
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                self.logger.info(f"Loaded Memory Index with {len(self.metadata)} items.")
            except Exception as e:
                self.logger.error(f"Index load failed, creating new: {e}")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        # dimension depends on model, MiniLM is 384
        dim = 384 
        self.index = faiss.IndexFlatL2(dim)
        self.metadata = []
        self.logger.info("Created new FAISS index.")

    def _save_index(self):
        if not self.index: return
        try:
            faiss.write_index(self.index, self.db_path)
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
        except Exception as e:
            self.logger.error(f"Failed to save index: {e}")

    def _generate_id(self) -> str:
        """Generate unique memory ID."""
        return f"mem_{uuid.uuid4().hex[:12]}"

    def add_memory(self, text: str, tags: list = None, type: str = "episodic") -> Optional[str]:
        """
        Add a text memory.
        
        Returns:
            Memory ID if successful, None otherwise.
        """
        if not self.model or not self.index: 
            return None
        
        memory_id = self._generate_id()
        embedding = self.model.encode([text])[0]
        self.index.add(np.array([embedding]).astype('float32'))
        
        meta = {
            "id": memory_id,
            "text": text,
            "tags": tags or [],
            "type": type,
            "timestamp": datetime.now().isoformat(),
            "edited": False
        }
        self.metadata.append(meta)
        self._save_index()
        self.logger.info(f"Memory saved: '{text[:30]}...' (ID: {memory_id})")
        return memory_id

    def search(self, query: str, k=3, threshold=1.5) -> List[Dict[str, Any]]:
        """
        Semantic search for memories.
        """
        if not self.model or not self.index or self.index.ntotal == 0:
            return []
            
        q_emb = self.model.encode([query])[0]
        D, I = self.index.search(np.array([q_emb]).astype('float32'), k)
        
        results = []
        for i, idx in enumerate(I[0]):
            distance = D[0][i]
            if idx < 0 or idx >= len(self.metadata): continue
            
            # Distance check (L2: lower is better)
            # Threshold is arbitrary, dependent on model
            self.logger.debug(f"Memory Match: {distance}")
            
            item = dict(self.metadata[idx])  # Copy to avoid mutation
            item['score'] = float(distance)
            item['index'] = int(idx)
            results.append(item)
            
        return results

    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        for i, meta in enumerate(self.metadata):
            if meta.get("id") == memory_id:
                result = dict(meta)
                result['index'] = i
                return result
        return None

    def update_memory(self, memory_id: str, new_text: str, new_tags: list = None) -> bool:
        """
        Update a memory's text and/or tags.
        
        Note: FAISS doesn't support updating embeddings in-place for IndexFlatL2,
        so we only update the metadata. For full text updates, delete and re-add.
        
        Args:
            memory_id: ID of memory to update.
            new_text: New text content.
            new_tags: New tags (optional).
        
        Returns:
            True if updated successfully.
        """
        for meta in self.metadata:
            if meta.get("id") == memory_id:
                meta["text"] = new_text
                if new_tags is not None:
                    meta["tags"] = new_tags
                meta["edited"] = True
                meta["edited_at"] = datetime.now().isoformat()
                self._save_index()
                self.logger.info(f"Memory updated: {memory_id}")
                return True
        
        self.logger.warning(f"Memory not found for update: {memory_id}")
        return False

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        
        Note: Due to FAISS limitations with IndexFlatL2, deletion requires
        rebuilding the index. For large stores, consider using IndexIDMap.
        
        Args:
            memory_id: ID of memory to delete.
        
        Returns:
            True if deleted successfully.
        """
        if not self.model or not self.index:
            return False
        
        # Find index of the memory
        idx_to_delete = None
        for i, meta in enumerate(self.metadata):
            if meta.get("id") == memory_id:
                idx_to_delete = i
                break
        
        if idx_to_delete is None:
            self.logger.warning(f"Memory not found for deletion: {memory_id}")
            return False
        
        # Remove from metadata
        del self.metadata[idx_to_delete]
        
        # Rebuild index (necessary for IndexFlatL2)
        if len(self.metadata) == 0:
            self._create_new_index()
        else:
            # Re-encode all remaining memories
            texts = [m["text"] for m in self.metadata]
            embeddings = self.model.encode(texts)
            
            dim = 384
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(np.array(embeddings).astype('float32'))
        
        self._save_index()
        self.logger.info(f"Memory deleted: {memory_id}")
        return True

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List all memories with pagination.
        
        Args:
            limit: Maximum number to return.
            offset: Starting position.
        
        Returns:
            List of memory metadata.
        """
        end = offset + limit
        results = []
        for i, meta in enumerate(self.metadata[offset:end], start=offset):
            item = dict(meta)
            item['index'] = i
            results.append(item)
        return results

    def get_count(self) -> int:
        """Get total number of memories."""
        return len(self.metadata)

    def clear_all(self, confirm: bool = False) -> bool:
        """
        Delete all memories.
        
        Args:
            confirm: Must be True to proceed.
        
        Returns:
            True if cleared.
        """
        if not confirm:
            self.logger.warning("clear_all called without confirmation")
            return False
        
        self._create_new_index()
        self._save_index()
        self.logger.warning("ALL MEMORIES CLEARED")
        return True

    def export_memories(self) -> List[Dict[str, Any]]:
        """Export all memories as list of dicts (for backup)."""
        return [dict(m) for m in self.metadata]

    def import_memories(self, memories: List[Dict[str, Any]], replace: bool = False) -> int:
        """
        Import memories from backup.
        
        Args:
            memories: List of memory dicts with 'text', 'tags', 'type'.
            replace: If True, clear existing memories first.
        
        Returns:
            Number of memories imported.
        """
        if replace:
            self.clear_all(confirm=True)
        
        count = 0
        for mem in memories:
            text = mem.get("text", "")
            if text:
                self.add_memory(
                    text=text,
                    tags=mem.get("tags", []),
                    type=mem.get("type", "episodic")
                )
                count += 1
        

# Alias for compatibility
VectorMemoryStore = VectorStore

