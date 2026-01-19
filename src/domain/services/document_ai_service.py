"""AI-Powered Document Processing Service.

Enterprise-grade document analysis using Claude AI for:
- Content extraction and summarization
- Auto-tagging and categorization
- Entity extraction (contacts, assets, procedures)
- Semantic chunking for RAG
- Quality and compliance checking
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentAnalysis:
    """Result of AI document analysis."""

    summary: str
    document_type: str
    category: str
    tags: list[str]
    keywords: list[str]
    topics: list[str]
    entities: dict[str, list]  # {contacts: [], assets: [], procedures: []}
    sensitivity: str
    confidence: float
    page_count: Optional[int] = None
    has_tables: bool = False
    has_images: bool = False
    effective_date: Optional[str] = None
    review_date: Optional[str] = None


@dataclass
class DocumentChunk:
    """A semantic chunk of document content."""

    content: str
    index: int
    heading: Optional[str]
    page_number: Optional[int]
    token_count: int
    char_start: int
    char_end: int


class DocumentAIService:
    """AI service for document processing using Claude."""

    SYSTEM_PROMPT = """You are an enterprise document analyst for a Quality Governance Platform.
Your role is to analyze documents and extract structured metadata for governance, compliance, and search.

When analyzing documents:
1. Identify the document type (policy, procedure, SOP, form, manual, guideline, FAQ, template, record)
2. Extract key topics and keywords for search optimization
3. Identify entities: contacts, assets/equipment, procedures referenced
4. Assess sensitivity level (public, internal, confidential, restricted)
5. Find governance dates (effective, review, expiry)
6. Generate a concise summary (2-3 sentences)
7. Suggest relevant tags for categorization

Always respond with valid JSON matching the requested schema."""

    def __init__(self):
        self.api_key = getattr(settings, "anthropic_api_key", None) or getattr(settings, "ANTHROPIC_API_KEY", None)
        self.model = "claude-sonnet-4-20250514"
        self.base_url = "https://api.anthropic.com/v1"

    async def analyze_document(self, content: str, file_name: str, file_type: str) -> DocumentAnalysis:
        """Analyze document content and extract metadata."""

        if not self.api_key:
            logger.warning("No Anthropic API key configured, using fallback analysis")
            return self._fallback_analysis(content, file_name)

        prompt = f"""Analyze this document and extract metadata.

Document: {file_name}
Type: {file_type}

Content:
---
{content[:50000]}  # Limit to ~50k chars
---

Respond with JSON matching this schema:
{{
    "summary": "2-3 sentence summary",
    "document_type": "policy|procedure|sop|form|manual|guideline|faq|template|record|other",
    "category": "category name",
    "tags": ["tag1", "tag2"],
    "keywords": ["keyword1", "keyword2"],
    "topics": ["topic1", "topic2"],
    "entities": {{
        "contacts": [{{"name": "", "role": "", "email": "", "phone": ""}}],
        "assets": ["asset1", "asset2"],
        "procedures": ["procedure1", "procedure2"],
        "standards": ["ISO 9001", "ISO 14001"]
    }},
    "sensitivity": "public|internal|confidential|restricted",
    "confidence": 0.95,
    "effective_date": "2024-01-01 or null",
    "review_date": "2025-01-01 or null",
    "has_tables": true|false,
    "has_images": true|false
}}"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 2000,
                        "system": self.SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=60.0,
                )
                response.raise_for_status()

                data = response.json()
                ai_response = data["content"][0]["text"]

                # Parse JSON from response
                json_match = re.search(r"\{[\s\S]*\}", ai_response)
                if json_match:
                    result = json.loads(json_match.group())
                    return DocumentAnalysis(
                        summary=result.get("summary", ""),
                        document_type=result.get("document_type", "other"),
                        category=result.get("category", ""),
                        tags=result.get("tags", []),
                        keywords=result.get("keywords", []),
                        topics=result.get("topics", []),
                        entities=result.get("entities", {}),
                        sensitivity=result.get("sensitivity", "internal"),
                        confidence=result.get("confidence", 0.0),
                        has_tables=result.get("has_tables", False),
                        has_images=result.get("has_images", False),
                        effective_date=result.get("effective_date"),
                        review_date=result.get("review_date"),
                    )

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")

        return self._fallback_analysis(content, file_name)

    def _fallback_analysis(self, content: str, file_name: str) -> DocumentAnalysis:
        """Fallback analysis when AI is unavailable."""

        # Extract keywords using simple frequency analysis
        words = re.findall(r"\b[a-zA-Z]{4,}\b", content.lower())
        word_freq = {}
        for word in words:
            if word not in {
                "that",
                "this",
                "with",
                "from",
                "have",
                "been",
                "will",
                "would",
                "could",
                "should",
            }:
                word_freq[word] = word_freq.get(word, 0) + 1

        keywords = sorted(word_freq.keys(), key=lambda x: word_freq[x], reverse=True)[:10]

        # Detect document type from filename/content
        doc_type = "other"
        file_lower = file_name.lower()
        if "policy" in file_lower:
            doc_type = "policy"
        elif "procedure" in file_lower or "proc" in file_lower:
            doc_type = "procedure"
        elif "sop" in file_lower:
            doc_type = "sop"
        elif "form" in file_lower:
            doc_type = "form"
        elif "manual" in file_lower:
            doc_type = "manual"
        elif "guide" in file_lower:
            doc_type = "guideline"
        elif "faq" in file_lower:
            doc_type = "faq"

        # Simple summary (first 200 chars)
        summary = content[:200].replace("\n", " ").strip() + "..."

        return DocumentAnalysis(
            summary=summary,
            document_type=doc_type,
            category="",
            tags=[],
            keywords=keywords,
            topics=[],
            entities={"contacts": [], "assets": [], "procedures": [], "standards": []},
            sensitivity="internal",
            confidence=0.3,
            has_tables="table" in content.lower() or "|" in content,
            has_images=False,
        )

    async def generate_chunks(
        self, content: str, max_chunk_size: int = 1000, overlap: int = 100
    ) -> list[DocumentChunk]:
        """Split document into semantic chunks for vector embedding."""

        chunks = []

        # Try to split by sections/headings first
        sections = self._split_by_sections(content)

        if len(sections) > 1:
            # Document has clear sections
            char_pos = 0
            for idx, section in enumerate(sections):
                heading, section_content = section

                # If section is too large, split further
                if len(section_content) > max_chunk_size:
                    sub_chunks = self._split_by_size(section_content, max_chunk_size, overlap)
                    for sub_idx, sub_content in enumerate(sub_chunks):
                        chunks.append(
                            DocumentChunk(
                                content=sub_content,
                                index=len(chunks),
                                heading=heading,
                                page_number=None,
                                token_count=len(sub_content.split()),
                                char_start=char_pos,
                                char_end=char_pos + len(sub_content),
                            )
                        )
                        char_pos += len(sub_content)
                else:
                    chunks.append(
                        DocumentChunk(
                            content=section_content,
                            index=len(chunks),
                            heading=heading,
                            page_number=None,
                            token_count=len(section_content.split()),
                            char_start=char_pos,
                            char_end=char_pos + len(section_content),
                        )
                    )
                    char_pos += len(section_content)
        else:
            # No clear sections, split by size
            sub_chunks = self._split_by_size(content, max_chunk_size, overlap)
            char_pos = 0
            for idx, chunk_content in enumerate(sub_chunks):
                chunks.append(
                    DocumentChunk(
                        content=chunk_content,
                        index=idx,
                        heading=None,
                        page_number=None,
                        token_count=len(chunk_content.split()),
                        char_start=char_pos,
                        char_end=char_pos + len(chunk_content),
                    )
                )
                char_pos += len(chunk_content)

        return chunks

    def _split_by_sections(self, content: str) -> list[tuple[str, str]]:
        """Split content by markdown/document headings."""

        # Match markdown headings or uppercase lines
        heading_pattern = r"^(#{1,3}\s+.+|[A-Z][A-Z\s]{5,}[A-Z])$"

        lines = content.split("\n")
        sections = []
        current_heading = None
        current_content = []

        for line in lines:
            if re.match(heading_pattern, line.strip()):
                if current_content:
                    sections.append((current_heading, "\n".join(current_content)))
                current_heading = line.strip().lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append((current_heading, "\n".join(current_content)))

        return sections if len(sections) > 1 else [(None, content)]

    def _split_by_size(self, content: str, max_size: int, overlap: int) -> list[str]:
        """Split content into fixed-size chunks with overlap."""

        chunks = []

        # Try to split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", content)

        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks


class EmbeddingService:
    """Service for generating document embeddings."""

    def __init__(self):
        self.voyage_api_key = getattr(settings, "voyage_api_key", None) or getattr(settings, "VOYAGE_API_KEY", None)
        self.model = "voyage-large-2"
        self.base_url = "https://api.voyageai.com/v1"

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""

        if not self.voyage_api_key:
            logger.warning("No Voyage API key configured, embeddings disabled")
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.voyage_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": texts, "input_type": "document"},
                    timeout=60.0,
                )
                response.raise_for_status()

                data = response.json()
                return [item["embedding"] for item in data.get("data", [])]

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return []

    async def generate_query_embedding(self, query: str) -> Optional[list[float]]:
        """Generate embedding for a search query."""

        if not self.voyage_api_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.voyage_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": [query], "input_type": "query"},
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                if data.get("data"):
                    return data["data"][0]["embedding"]

        except Exception as e:
            logger.error(f"Query embedding failed: {e}")

        return None


class VectorSearchService:
    """Service for semantic search using Pinecone."""

    def __init__(self):
        self.api_key = getattr(settings, "pinecone_api_key", None) or getattr(settings, "PINECONE_API_KEY", None)
        self.index_name = getattr(settings, "pinecone_index", "qgp-documents")
        self.environment = getattr(settings, "pinecone_environment", "gcp-starter")
        self.embedding_service = EmbeddingService()

    async def upsert_chunks(self, document_id: int, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> bool:
        """Upsert document chunks to Pinecone."""

        if not self.api_key or not embeddings:
            return False

        try:
            vectors = []
            for chunk, embedding in zip(chunks, embeddings):
                vectors.append(
                    {
                        "id": f"doc_{document_id}_chunk_{chunk.index}",
                        "values": embedding,
                        "metadata": {
                            "document_id": document_id,
                            "chunk_index": chunk.index,
                            "heading": chunk.heading or "",
                            "page_number": chunk.page_number or 0,
                            "content_preview": chunk.content[:200],
                        },
                    }
                )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.index_name}-{self.environment}.svc.pinecone.io/vectors/upsert",
                    headers={
                        "Api-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={"vectors": vectors},
                    timeout=60.0,
                )
                response.raise_for_status()
                return True

        except Exception as e:
            logger.error(f"Vector upsert failed: {e}")
            return False

    async def search(self, query: str, top_k: int = 10, filter_dict: Optional[dict] = None) -> list[dict]:
        """Semantic search for documents."""

        if not self.api_key:
            return []

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_query_embedding(query)
        if not query_embedding:
            return []

        try:
            body = {
                "vector": query_embedding,
                "topK": top_k,
                "includeMetadata": True,
            }
            if filter_dict:
                body["filter"] = filter_dict

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.index_name}-{self.environment}.svc.pinecone.io/query",
                    headers={
                        "Api-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                return data.get("matches", [])

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def delete_document_vectors(self, document_id: int) -> bool:
        """Delete all vectors for a document."""

        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.index_name}-{self.environment}.svc.pinecone.io/vectors/delete",
                    headers={
                        "Api-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={"filter": {"document_id": document_id}},
                    timeout=30.0,
                )
                response.raise_for_status()
                return True

        except Exception as e:
            logger.error(f"Vector deletion failed: {e}")
            return False
