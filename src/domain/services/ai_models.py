"""
AI Model Integration Module

Provides real AI/ML model integration for:
- Incident prediction
- Risk scoring
- Document classification
- Anomaly detection
- NLP analysis
- ISO clause mapping and evidence analysis (Genspark.ai + OpenAI + Anthropic)

Supported backends:
- Genspark.ai  (OpenAI-compatible proxy; model: claude-opus-4-6-1m / claude-sonnet-4-6)
- OpenAI GPT-4
- Azure OpenAI
- Anthropic Claude
- Local models (Sentence Transformers)
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================


class AIProvider(Enum):
    """Available AI providers."""

    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GENSPARK = "genspark"
    LOCAL = "local"


@dataclass
class AIConfig:
    """AI service configuration."""

    provider: AIProvider = AIProvider.OPENAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-opus-20240229"
    # Genspark.ai — OpenAI-compatible proxy at https://api.genspark.ai
    # Primary model: claude-opus-4-6-1m (deep reasoning for ISO analysis)
    # Fast model:    claude-sonnet-4-6   (quick classification tasks)
    genspark_api_key: str = ""
    genspark_model: str = "claude-opus-4-6-1m"
    genspark_fast_model: str = "claude-sonnet-4-6"
    local_model_path: str = ""
    embedding_model: str = "text-embedding-3-small"

    @classmethod
    def from_env(cls) -> "AIConfig":
        """Load configuration from environment variables."""
        provider_str = os.getenv("AI_PROVIDER", "openai")
        # Auto-upgrade to Genspark if a key is present and provider not explicitly set
        genspark_key = os.getenv("GENSPARK_API_KEY", "")
        if genspark_key and provider_str == "openai" and not os.getenv("OPENAI_API_KEY"):
            provider_str = "genspark"

        try:
            provider = AIProvider(provider_str)
        except ValueError:
            provider = AIProvider.GENSPARK if genspark_key else AIProvider.OPENAI

        return cls(
            provider=provider,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_openai_key=os.getenv("AZURE_OPENAI_KEY", ""),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
            genspark_api_key=genspark_key,
            genspark_model=os.getenv("GENSPARK_MODEL", "claude-opus-4-6-1m"),
            genspark_fast_model=os.getenv("GENSPARK_FAST_MODEL", "claude-sonnet-4-6"),
            local_model_path=os.getenv("LOCAL_MODEL_PATH", ""),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )


# ============================================================================
# AI Provider Clients
# ============================================================================


class AIClient(ABC):
    """Abstract base class for AI clients."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text completion."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate text embedding."""
        pass

    @abstractmethod
    async def analyze(
        self,
        text: str,
        analysis_type: str,
    ) -> dict[str, Any]:
        """Perform structured analysis on text."""
        pass


class OpenAIClient(AIClient):
    """OpenAI API client."""

    def __init__(self, config: AIConfig):
        self.config = config
        self.api_key = config.openai_api_key
        self.model = config.openai_model
        self.embedding_model = config.embedding_model

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate completion using OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.embedding_model,
                    "input": text,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    async def analyze(
        self,
        text: str,
        analysis_type: str,
    ) -> dict[str, Any]:
        """Perform structured analysis."""
        prompts = {
            "sentiment": "Analyze the sentiment of the following text and return a JSON object with 'sentiment' (positive/negative/neutral), 'confidence' (0-1), and 'key_phrases' (list of important phrases).",
            "classification": "Classify the following incident/report into categories and return a JSON object with 'category', 'subcategory', 'severity' (low/medium/high/critical), and 'confidence' (0-1).",
            "root_cause": "Analyze the following incident description and suggest potential root causes. Return a JSON object with 'primary_cause', 'contributing_factors' (list), and 'recommendations' (list).",
            "risk_assessment": "Assess the risk level of the following scenario. Return a JSON object with 'likelihood' (1-5), 'impact' (1-5), 'risk_score' (1-25), 'risk_level' (low/medium/high/critical), and 'mitigation_suggestions' (list).",
        }

        system_prompt = prompts.get(analysis_type, prompts["classification"])

        result = await self.complete(
            prompt=f"Text to analyze:\n\n{text}\n\nProvide your analysis in valid JSON format only.",
            system_prompt=system_prompt,
            temperature=0.3,
        )

        # Parse JSON from response
        try:
            # Try to extract JSON from the response
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"raw_response": result, "parse_error": True}


class AnthropicClient(AIClient):
    """Anthropic Claude API client."""

    def __init__(self, config: AIConfig):
        self.config = config
        self.api_key = config.anthropic_api_key
        self.model = config.anthropic_model

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate completion using Claude."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system_prompt or "You are a helpful assistant.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def embed(self, text: str) -> list[float]:
        """Generate embedding (not natively supported, use OpenAI fallback)."""
        # Claude doesn't have native embeddings, use OpenAI
        if self.config.openai_api_key:
            openai_client = OpenAIClient(self.config)
            return await openai_client.embed(text)
        # Return empty for now
        return []

    async def analyze(
        self,
        text: str,
        analysis_type: str,
    ) -> dict[str, Any]:
        """Perform structured analysis using Claude."""
        # Similar to OpenAI implementation
        openai_client = OpenAIClient(self.config)
        # Override with Claude for completion
        result = await self.complete(
            prompt=f"Analyze the following text for {analysis_type}. Return a valid JSON object.\n\nText:\n{text}",
            system_prompt="You are an expert analyst. Always respond with valid JSON only.",
            temperature=0.3,
        )

        try:
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]
            else:
                json_str = result
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"raw_response": result, "parse_error": True}


# ============================================================================
# Genspark.ai Client
# ============================================================================


class GenspaarkClient(AIClient):
    """
    Genspark.ai AI client.

    Genspark exposes an OpenAI-compatible completions API at https://api.genspark.ai
    with authentication via 'Authorization: Bearer gsk_...' header.

    Default model: claude-opus-4-6-1m  (deep reasoning, ideal for ISO analysis)
    Fast model:    claude-sonnet-4-6    (rapid classification, auto-tagging)

    The '-search' suffix can be appended to any model name to enable real-time
    web-search augmentation (e.g. 'claude-sonnet-4-6-search' for ISO standard
    lookups).  We do NOT use it for evidence mapping to ensure deterministic,
    evidence-only outputs.
    """

    BASE_URL = "https://api.genspark.ai"
    COMPLETIONS_PATH = "/v1/chat/completions"

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.api_key = config.genspark_api_key
        self.model = config.genspark_model
        self.fast_model = config.genspark_fast_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> str:
        """Generate a completion via the Genspark OpenAI-compatible endpoint."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.BASE_URL}{self.COMPLETIONS_PATH}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def complete_fast(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Complete using the fast (sonnet) model for time-sensitive tasks."""
        return await self.complete(
            prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=2048,
            model=self.fast_model,
        )

    async def embed(self, text: str) -> list[float]:
        """Genspark does not expose an embeddings endpoint; return empty."""
        logger.debug("GenspaarkClient: embeddings not available, returning empty vector")
        return []

    async def analyze(
        self,
        text: str,
        analysis_type: str,
    ) -> dict[str, Any]:
        """Structured JSON analysis via Genspark."""
        result = await self.complete(
            prompt=f"Analyze the following text for {analysis_type}. Return a valid JSON object ONLY.\n\nText:\n{text}",
            system_prompt="You are an expert analyst. Always respond with valid JSON only.",
            temperature=0.2,
        )
        try:
            cleaned = result.strip()
            if cleaned.startswith("```"):
                import re

                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw_response": result, "parse_error": True}


# ============================================================================
# AI Service Factory
# ============================================================================


def get_ai_client(config: Optional[AIConfig] = None) -> AIClient:
    """
    Factory: return the best available AI client given the environment config.

    Priority:
      1. Genspark  — if GENSPARK_API_KEY is set  (richest ISO analysis capability)
      2. Anthropic  — if ANTHROPIC_API_KEY is set
      3. OpenAI     — if OPENAI_API_KEY is set
      4. OpenAI stub (will fail at HTTP time, but allows startup without a key)
    """
    config = config or AIConfig.from_env()

    if config.provider == AIProvider.GENSPARK and config.genspark_api_key:
        logger.info("AI client: Genspark.ai (model=%s)", config.genspark_model)
        return GenspaarkClient(config)

    if config.provider == AIProvider.ANTHROPIC and config.anthropic_api_key:
        logger.info("AI client: Anthropic (model=%s)", config.anthropic_model)
        return AnthropicClient(config)

    if config.provider == AIProvider.OPENAI and config.openai_api_key:
        logger.info("AI client: OpenAI (model=%s)", config.openai_model)
        return OpenAIClient(config)

    # Fallback: try any key that is available regardless of declared provider
    if config.genspark_api_key:
        logger.info("AI client: Genspark.ai (fallback, key present)")
        return GenspaarkClient(config)
    if config.anthropic_api_key:
        logger.info("AI client: Anthropic (fallback, key present)")
        return AnthropicClient(config)
    if config.openai_api_key:
        logger.info("AI client: OpenAI (fallback, key present)")
        return OpenAIClient(config)

    logger.warning("AI client: no API key found; returning OpenAI stub (calls will fail)")
    return OpenAIClient(config)


# ============================================================================
# High-Level AI Services
# ============================================================================


class IncidentAnalyzer:
    """AI-powered incident analysis."""

    def __init__(self, client: Optional[AIClient] = None):
        self.client = client or get_ai_client()

    async def predict_severity(
        self,
        title: str,
        description: str,
        location: Optional[str] = None,
    ) -> dict[str, Any]:
        """Predict incident severity based on description."""
        text = f"Title: {title}\nDescription: {description}"
        if location:
            text += f"\nLocation: {location}"

        return await self.client.analyze(text, "classification")

    async def suggest_root_causes(
        self,
        incident_description: str,
        incident_type: str,
    ) -> dict[str, Any]:
        """Suggest potential root causes for an incident."""
        text = f"Incident Type: {incident_type}\nDescription: {incident_description}"
        return await self.client.analyze(text, "root_cause")

    async def cluster_similar_incidents(
        self,
        incidents: list[dict],
    ) -> list[dict]:
        """Cluster similar incidents based on embeddings."""
        # Get embeddings for each incident
        embeddings = []
        for incident in incidents:
            text = f"{incident.get('title', '')} {incident.get('description', '')}"
            embedding = await self.client.embed(text)
            embeddings.append(
                {
                    "id": incident.get("id"),
                    "embedding": embedding,
                }
            )

        # Simple clustering would happen here (e.g., using sklearn)
        # For now, return with embeddings attached
        return embeddings


class RiskScorer:
    """AI-powered risk scoring."""

    def __init__(self, client: Optional[AIClient] = None):
        self.client = client or get_ai_client()

    async def score_risk(
        self,
        risk_description: str,
        context: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Score a risk using AI analysis."""
        text = f"Risk Description: {risk_description}"
        if context:
            text += f"\nContext: {json.dumps(context)}"

        return await self.client.analyze(text, "risk_assessment")

    async def recommend_controls(
        self,
        risk_description: str,
        current_controls: Optional[list[str]] = None,
    ) -> list[str]:
        """Recommend controls for a given risk."""
        prompt = f"Risk: {risk_description}"
        if current_controls:
            prompt += f"\nCurrent Controls: {', '.join(current_controls)}"

        result = await self.client.complete(
            prompt=prompt,
            system_prompt="You are a risk management expert. Suggest specific, actionable controls to mitigate the given risk. Return a JSON array of control recommendations.",
            temperature=0.4,
        )

        try:
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            else:
                json_str = result
            return json.loads(json_str)
        except json.JSONDecodeError:
            return [result]


class DocumentClassifier:
    """AI-powered document classification and tagging."""

    def __init__(self, client: Optional[AIClient] = None):
        self.client = client or get_ai_client()

    async def classify_document(
        self,
        content: str,
        title: Optional[str] = None,
    ) -> dict[str, Any]:
        """Classify a document and suggest tags."""
        text = content[:4000]  # Limit for API
        if title:
            text = f"Title: {title}\n\n{text}"

        result = await self.client.complete(
            prompt=f"Document:\n{text}",
            system_prompt="""Classify this document and return a JSON object with:
            - 'document_type': The type of document (policy, procedure, form, report, etc.)
            - 'iso_standards': List of relevant ISO standards (9001, 14001, 45001, 27001)
            - 'clauses': List of specific ISO clause references
            - 'tags': List of relevant tags
            - 'summary': Brief 2-sentence summary
            - 'confidence': Confidence score 0-1""",
            temperature=0.3,
        )

        try:
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            else:
                json_str = result
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"raw_response": result}

    async def extract_compliance_evidence(
        self,
        content: str,
        target_standard: str,
    ) -> dict[str, Any]:
        """Extract compliance evidence from document for a specific standard."""
        result = await self.client.complete(
            prompt=f"Document:\n{content[:4000]}\n\nTarget Standard: {target_standard}",
            system_prompt=f"""Extract compliance evidence for {target_standard} from this document.
            Return a JSON object with:
            - 'relevant_clauses': List of clause numbers this document provides evidence for
            - 'evidence_type': Type of evidence (policy, record, procedure, etc.)
            - 'evidence_strength': strong/moderate/weak
            - 'gaps_identified': Any compliance gaps noticed
            - 'recommendations': Suggestions for improvement""",
            temperature=0.3,
        )

        try:
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            else:
                json_str = result
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"raw_response": result}


class AuditAssistant:
    """AI-powered audit assistance."""

    def __init__(self, client: Optional[AIClient] = None):
        self.client = client or get_ai_client()

    async def generate_audit_questions(
        self,
        standard: str,
        clause: str,
        context: Optional[str] = None,
    ) -> list[str]:
        """Generate audit questions for a specific clause."""
        prompt = f"Standard: {standard}\nClause: {clause}"
        if context:
            prompt += f"\nContext: {context}"

        result = await self.client.complete(
            prompt=prompt,
            system_prompt="""Generate 5 audit questions for this ISO clause. 
            Questions should be:
            - Specific and measurable
            - Evidence-focused
            - Open-ended (not yes/no)
            Return a JSON array of question strings.""",
            temperature=0.4,
        )

        try:
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            else:
                json_str = result
            return json.loads(json_str)
        except json.JSONDecodeError:
            return [result]

    async def analyze_finding(
        self,
        finding_description: str,
        clause_reference: str,
    ) -> dict[str, Any]:
        """Analyze audit finding and suggest classification."""
        result = await self.client.complete(
            prompt=f"Finding: {finding_description}\nClause: {clause_reference}",
            system_prompt="""Analyze this audit finding and return a JSON object with:
            - 'classification': major_nc, minor_nc, observation, or opportunity_for_improvement
            - 'root_cause_category': People, Process, Technology, or Documentation
            - 'suggested_corrective_action': Recommended action to address the finding
            - 'verification_criteria': What would demonstrate the issue is resolved
            - 'risk_if_unaddressed': Potential consequence if not corrected""",
            temperature=0.3,
        )

        try:
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            else:
                json_str = result
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"raw_response": result}


# ============================================================================
# AI Service Registry
# ============================================================================


_ai_services: dict[str, Any] = {}


def get_incident_analyzer() -> IncidentAnalyzer:
    """Get singleton incident analyzer."""
    if "incident_analyzer" not in _ai_services:
        _ai_services["incident_analyzer"] = IncidentAnalyzer()
    return _ai_services["incident_analyzer"]


def get_risk_scorer() -> RiskScorer:
    """Get singleton risk scorer."""
    if "risk_scorer" not in _ai_services:
        _ai_services["risk_scorer"] = RiskScorer()
    return _ai_services["risk_scorer"]


def get_document_classifier() -> DocumentClassifier:
    """Get singleton document classifier."""
    if "document_classifier" not in _ai_services:
        _ai_services["document_classifier"] = DocumentClassifier()
    return _ai_services["document_classifier"]


def get_audit_assistant() -> AuditAssistant:
    """Get singleton audit assistant."""
    if "audit_assistant" not in _ai_services:
        _ai_services["audit_assistant"] = AuditAssistant()
    return _ai_services["audit_assistant"]
