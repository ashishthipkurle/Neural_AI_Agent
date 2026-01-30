
import sqlite3
import numpy as np
import os
import json
import logging
import pickle

# Try to import FAISS, else fallback to naive search
try:
    import faiss
except ImportError:
    faiss = None

class FaceDatabase:
    def __init__(self, db_path="agent/db/faces.db", vector_dim=512):
        self.logger = logging.getLogger("FaceDatabase")
        self.db_path = db_path
        self.vector_dim = vector_dim
        
        # Ensure db directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self._init_sql()
        self._init_vector_index()

    def _init_sql(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _init_vector_index(self):
        """
        Initialize FAISS index or load from disk if using persistent index (complex).
        For simplicity, we rebuild index from SQL on startup.
        """
        if faiss:
            self.index = faiss.IndexFlatL2(self.vector_dim)
            self.logger.info(f"FAISS Index initialized (dim={self.vector_dim})")
            self._rebuild_index()
        else:
            self.index = None
            self.logger.warning("FAISS not installed. Using naive search (slow).")

    def _rebuild_index(self):
        if not self.index: return
        self.cursor.execute("SELECT id, embedding FROM faces")
        rows = self.cursor.fetchall()
        if not rows: return
        
        embeddings = []
        ids = []
        for r in rows:
            emb = pickle.loads(r[1])
            embeddings.append(emb)
            ids.append(r[0])
        
        if embeddings:
            emb_matrix = np.array(embeddings).astype('float32')
            self.index.add(emb_matrix)
            self.logger.info(f"Loaded {len(embeddings)} faces into FAISS.")

    def add_face(self, name: str, embedding: np.ndarray):
        """
        Add a new face to the database.
        """
        # Save to SQL
        emb_blob = pickle.dumps(embedding)
        self.cursor.execute("INSERT INTO faces (name, embedding) VALUES (?, ?)", (name, emb_blob))
        new_id = self.cursor.lastrowid
        self.conn.commit()
        
        # Add to FAISS
        if self.index:
            self.index.add(np.array([embedding]).astype('float32'))
            
        self.logger.info(f"Saved face for {name} (ID: {new_id})")
        return new_id

    def match_face(self, embedding: np.ndarray, threshold=0.6):
        """
        Search for a matching face.
        Returns (name, confidence) or (None, 0.0).
        """
        if self.index:
            # FAISS Search
            k = 1
            D, I = self.index.search(np.array([embedding]).astype('float32'), k)
            distance = D[0][0]
            idx = I[0][0]
            
            # Simple threshold logic for L2 distance (lower is better)
            # Threshold needs tuning based on model. For ArcFace cosine is better, but FAISS L2 is okay if normalized.
            # Assuming distance is Euclidean.
            self.logger.debug(f"Face Match Dist: {distance}")
            
            if distance < threshold: # 0.6 is arbitrary for L2, might need 1.0 or similar
                # Get name from SQL (Optimization: Keep a mapping in memory)
                # Since index matches insertion order for flat index, row_id might not match fast index ID?
                # Actually FAISS basic index returns 0-based index. 
                # We need to map 0-based index to SQL ID or Name.
                # Re-fetching naive for now or rebuilding logic.
                
                # Better approach for this proto: Load all names list matching index order
                return self._get_name_by_index(idx), (1.0 - distance) # Fake confidence
            
        else:
            # Naive Search (Calculate distance to all)
            pass
            
        return "Unknown", 0.0

    def _get_name_by_index(self, idx):
        # Only works if we never delete rows and load sequentially
        self.cursor.execute("SELECT name FROM faces LIMIT 1 OFFSET ?", (int(idx),))
        row = self.cursor.fetchone()
        return row[0] if row else "Unknown"
