"""ChromaDB vector store operations."""
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from pathlib import Path

from utils.logger import setup_logger
import config

logger = setup_logger(__name__)


class VectorStore:
    """Manages ChromaDB operations for chunk embeddings."""
    
    def __init__(self, chroma_path: Path = config.CHROMA_PATH):
        """Initialize ChromaDB client and embedding model.
        
        Args:
            chroma_path: Path to ChromaDB persistence directory
        """
        self.chroma_path = chroma_path
        self.client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Load embedding model
        logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        logger.info("Vector store initialized")
    
    def _get_collection_name(self, novel_id: str) -> str:
        """Get collection name for a novel.
        
        Args:
            novel_id: Novel UUID
            
        Returns:
            Collection name
        """
        # ChromaDB collection names have restrictions
        return f"novel_{novel_id.replace('-', '_')}"
    
    def collection_exists(self, novel_id: str) -> bool:
        """Check if a collection exists for a novel.
        
        Args:
            novel_id: Novel UUID
            
        Returns:
            True if collection exists
        """
        collection_name = self._get_collection_name(novel_id)
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False
    
    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        novel_id: str
    ) -> None:
        """Add narrative chunks to vector store.
        
        Args:
            chunks: List of chunk dictionaries with 'id', 'text', and metadata
            novel_id: Novel UUID
        """
        if not chunks:
            logger.warning("No chunks to add")
            return
        
        collection_name = self._get_collection_name(novel_id)
        
        # Create or get collection
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"novel_id": novel_id}
        )
        
        # Extract text and generate embeddings
        texts = [chunk['text'] for chunk in chunks]
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True).tolist()
        
        # Prepare metadata
        metadatas = [
            {
                "chunk_id": chunk['id'],
                "novel_id": novel_id,
                "chapter_number": str(chunk.get('chapter_number', 0)),
                "chunk_index": str(chunk.get('chunk_index', 0)),
                "token_count": str(chunk.get('token_count', 0))
            }
            for chunk in chunks
        ]
        
        # Add to collection
        ids = [chunk['id'] for chunk in chunks]
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(chunks)} chunks to vector store")
    
    def query(
        self,
        query_text: str,
        novel_id: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Query chunks by semantic similarity.
        
        Args:
            query_text: Query string
            novel_id: Novel UUID
            n_results: Number of results to return
            
        Returns:
            List of matching chunks with metadata
        """
        collection_name = self._get_collection_name(novel_id)
        
        try:
            collection = self.client.get_collection(collection_name)
        except Exception as e:
            logger.error(f"Collection not found: {collection_name}")
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query_text])[0].tolist()
        
        # Query collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Format results
        chunks = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                chunks.append({
                    'id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return chunks
    
    def delete_novel(self, novel_id: str) -> None:
        """Delete all embeddings for a novel.
        
        Args:
            novel_id: Novel UUID
        """
        collection_name = self._get_collection_name(novel_id)
        
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Could not delete collection {collection_name}: {e}")
