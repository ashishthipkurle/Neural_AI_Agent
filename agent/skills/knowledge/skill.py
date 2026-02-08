"""
Knowledge Base Skill - RAG-style document retrieval.

Provides:
- Document ingestion (PDF, TXT, MD, HTML)
- Chunking and embedding
- Semantic search
- Contextual Q&A
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


@dataclass
class Document:
    """A document in the knowledge base."""
    id: str
    path: str
    title: str
    chunks: List[str]
    embeddings: List[Any]  # numpy arrays
    metadata: Dict[str, Any]


class KnowledgeBaseSkill(BaseSkill):
    """
    RAG-style knowledge base skill.
    
    Actions:
    - ingest: Add document to knowledge base
    - search: Semantic search across documents
    - ask: Ask a question (RAG-style)
    - list: List all documents
    - remove: Remove document
    - clear: Clear entire knowledge base
    """
    
    KB_DIR = Path("agent/data/knowledge")
    
    def __init__(self):
        super().__init__()
        self._documents: Dict[str, Document] = {}
        self._embedder = None
        self._index = None
    
    @property
    def name(self) -> str:
        return "knowledge"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="knowledge",
            version="1.0.0",
            description="RAG-style document retrieval and Q&A",
            actions=["ingest", "search", "ask", "list", "remove", "clear"],
            requires=["sentence-transformers", "faiss-cpu", "PyPDF2"],
            permissions=["filesystem", "memory"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize knowledge base."""
        self.KB_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load embedder
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            self.logger.info("Knowledge base: Embedder loaded")
        except (OSError, ImportError, Exception) as e:
            self.logger.warning(f"Embedder not available: {e}")
            self.logger.warning("RAG features will be disabled due to memory or dependency issues.")
            self._embedder = None
        
        # Load existing index
        self._load_index()
        
        super().on_load()
        self.logger.info(f"Knowledge base loaded: {len(self._documents)} documents")
    
    def on_unload(self) -> None:
        """Save index."""
        self._save_index()
        super().on_unload()
    
    def _load_index(self):
        """Load saved index and documents."""
        index_file = self.KB_DIR / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    data = json.load(f)
                    for doc_id, doc_data in data.get("documents", {}).items():
                        self._documents[doc_id] = Document(
                            id=doc_id,
                            path=doc_data["path"],
                            title=doc_data["title"],
                            chunks=doc_data["chunks"],
                            embeddings=[],  # Regenerate on demand
                            metadata=doc_data.get("metadata", {})
                        )
            except Exception as e:
                self.logger.warning(f"Failed to load index: {e}")
    
    def _save_index(self):
        """Save index to disk."""
        index_file = self.KB_DIR / "index.json"
        data = {
            "documents": {
                doc_id: {
                    "path": doc.path,
                    "title": doc.title,
                    "chunks": doc.chunks,
                    "metadata": doc.metadata
                }
                for doc_id, doc in self._documents.items()
            }
        }
        
        try:
            with open(index_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save index: {e}")
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        if any(x in intent_lower for x in ["knowledge base", "from my documents", "in my docs"]):
            return 0.9
        
        if any(x in intent_lower for x in ["ingest", "add document", "load pdf"]):
            return 0.85
        
        if "based on" in intent_lower and "file" in intent_lower:
            return 0.8
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a knowledge base action."""
        
        handlers = {
            "ingest": self._action_ingest,
            "search": self._action_search,
            "ask": self._action_ask,
            "list": self._action_list,
            "remove": self._action_remove,
            "clear": self._action_clear,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            result = handler(params, context or {})
            if action in ["ingest", "remove", "clear"]:
                self._save_index()
            return result
        except Exception as e:
            self.logger.error(f"Knowledge action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== ACTIONS ====================
    
    def _action_ingest(self, params: Dict, context: Dict) -> SkillResult:
        """Ingest a document into the knowledge base."""
        path = params.get("path")
        
        if not path:
            return SkillResult(success=False, error="Document path required")
        
        path = Path(path)
        if not path.exists():
            return SkillResult(success=False, error=f"File not found: {path}")
        
        # Generate document ID
        doc_id = hashlib.md5(str(path).encode()).hexdigest()[:12]
        
        # Extract text based on file type
        text = self._extract_text(path)
        if not text:
            return SkillResult(success=False, error=f"Could not extract text from: {path}")
        
        # Chunk text
        chunks = self._chunk_text(text)
        
        # Generate embeddings
        embeddings = []
        if self._embedder:
            embeddings = self._embedder.encode(chunks).tolist()
        
        # Create document
        doc = Document(
            id=doc_id,
            path=str(path),
            title=path.stem,
            chunks=chunks,
            embeddings=embeddings,
            metadata={"file_type": path.suffix}
        )
        
        self._documents[doc_id] = doc
        
        return SkillResult(
            success=True,
            data={"document_id": doc_id, "chunks": len(chunks)},
            message=f"Ingested {path.name} ({len(chunks)} chunks)"
        )
    
    def _extract_text(self, path: Path) -> str:
        """Extract text from a file."""
        suffix = path.suffix.lower()
        
        if suffix == ".pdf":
            try:
                import PyPDF2
                with open(path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    return text
            except Exception as e:
                self.logger.error(f"PDF extraction failed: {e}")
                return ""
        
        elif suffix in [".txt", ".md", ".html", ".py", ".js", ".json"]:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                return ""
        
        else:
            self.logger.warning(f"Unsupported file type: {suffix}")
            return ""
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        words = text.split()
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def _action_search(self, params: Dict, context: Dict) -> SkillResult:
        """Semantic search across documents."""
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        
        if not query:
            return SkillResult(success=False, error="Search query required")
        
        if not self._embedder:
            return SkillResult(success=False, error="Embedder not available")
        
        if not self._documents:
            return SkillResult(success=True, data={"results": []}, message="Knowledge base is empty")
        
        # Embed query
        query_embedding = self._embedder.encode([query])[0]
        
        # Search all chunks
        import numpy as np
        results = []
        
        for doc in self._documents.values():
            if not doc.embeddings:
                # Re-embed if needed
                doc.embeddings = self._embedder.encode(doc.chunks).tolist()
            
            for i, chunk_emb in enumerate(doc.embeddings):
                # Cosine similarity
                chunk_emb = np.array(chunk_emb)
                similarity = np.dot(query_embedding, chunk_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb)
                )
                
                results.append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "chunk_index": i,
                    "text": doc.chunks[i][:500],
                    "score": float(similarity)
                })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]
        
        return SkillResult(
            success=True,
            data={"results": results},
            message=f"Found {len(results)} relevant chunks"
        )
    
    def _action_ask(self, params: Dict, context: Dict) -> SkillResult:
        """Ask a question using RAG."""
        question = params.get("question", "")
        
        if not question:
            return SkillResult(success=False, error="Question required")
        
        # Search for relevant context
        search_result = self._action_search({"query": question, "top_k": 3}, context)
        
        if not search_result.success:
            return search_result
        
        results = search_result.data.get("results", [])
        
        if not results:
            return SkillResult(
                success=True,
                message="I don't have enough information in my knowledge base to answer that."
            )
        
        # Build context from top results
        context_text = "\n\n".join([
            f"[From {r['title']}]: {r['text']}"
            for r in results
        ])
        
        # Try to use LLM for answering
        try:
            from agent.core.llm.local_runtime import LocalLLMRuntime
            llm = LocalLLMRuntime()
            
            prompt = f"""Based on the following context, answer the question.

Context:
{context_text}

Question: {question}

Answer:"""
            
            result = llm.generate(prompt)
            answer = result.text if hasattr(result, 'text') else str(result)
            
            return SkillResult(
                success=True,
                data={"answer": answer, "sources": [r["title"] for r in results]},
                message=answer
            )
        except Exception as e:
            # Fallback: just return the context
            return SkillResult(
                success=True,
                data={"context": context_text},
                message=f"Found relevant information:\n{context_text[:1000]}"
            )
    
    def _action_list(self, params: Dict, context: Dict) -> SkillResult:
        """List all documents."""
        docs = [
            {
                "id": doc.id,
                "title": doc.title,
                "path": doc.path,
                "chunks": len(doc.chunks)
            }
            for doc in self._documents.values()
        ]
        
        return SkillResult(
            success=True,
            data={"documents": docs},
            message=f"{len(docs)} documents in knowledge base"
        )
    
    def _action_remove(self, params: Dict, context: Dict) -> SkillResult:
        """Remove a document."""
        doc_id = params.get("document_id")
        
        if not doc_id:
            return SkillResult(success=False, error="Document ID required")
        
        if doc_id in self._documents:
            del self._documents[doc_id]
            return SkillResult(success=True, message=f"Removed document {doc_id}")
        
        return SkillResult(success=False, error=f"Document not found: {doc_id}")
    
    def _action_clear(self, params: Dict, context: Dict) -> SkillResult:
        """Clear knowledge base."""
        confirmed = params.get("confirmed", False)
        
        if not confirmed:
            return SkillResult(
                success=False,
                error="Confirmation required. Set confirmed=True"
            )
        
        count = len(self._documents)
        self._documents.clear()
        
        return SkillResult(success=True, message=f"Cleared {count} documents")
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check knowledge base health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._embedder:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview knowledge base action."""
        if action == "ingest":
            return f"Would ingest: {params.get('path', 'unknown')}"
        if action == "search":
            return f"Would search for: {params.get('query', 'unknown')}"
        if action == "ask":
            return f"Would answer: {params.get('question', 'unknown')}"
        return f"Would execute knowledge.{action}"
