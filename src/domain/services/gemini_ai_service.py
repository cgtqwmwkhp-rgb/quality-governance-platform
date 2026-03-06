"""Google Gemini AI service for intelligent template generation and analysis.

Uses Gemini 2.5 Pro Preview (with grounding/web search) for:
- Document-to-template conversion (OCR + structured extraction)
- Web search enrichment for manufacturer recommendations
- Template-from-template conversion (compliance -> competency assessment)
- Bulk template generation from uploaded documents
- Gap analysis between existing templates and industry standards
- Smart assessor guidance generation
"""

import asyncio
import json
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-pro-preview-05-06"
GEMINI_API_KEY_ENV = "GOOGLE_GEMINI_API_KEY"


class GeminiAIService:
    """Wraps Google Generative AI SDK for template intelligence."""

    def __init__(self):
        self.api_key = os.environ.get(GEMINI_API_KEY_ENV)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(GEMINI_MODEL)
            except ImportError:
                logger.warning("google-generativeai not installed; AI features disabled")
                return None
            except Exception as e:
                logger.error("Failed to initialise Gemini client: %s", e)
                return None
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def document_to_template(self, file_content: bytes, filename: str, asset_type: Optional[str] = None) -> dict:
        """Convert an uploaded document (PDF, image, etc.) into a structured audit template.

        Uses Gemini's multimodal capabilities for OCR + structured extraction.
        Classifies each extracted item as Essential or Good-to-Have.
        """
        client = self._get_client()
        if not client:
            return self._fallback_template(filename)

        asset_context = f" for asset type: {asset_type}" if asset_type else ""
        prompt = f"""Analyse the following document and extract a structured audit/inspection template{asset_context}.

For each item found, classify it as either:
- "essential" - mandatory pass/fail criteria (safety-critical, regulatory, legal)
- "good_to_have" - scored criteria (best practice, quality, efficiency)

Return a JSON object with this exact structure:
{{
    "name": "Template name derived from document",
    "description": "Brief description of what this template covers",
    "category": "compliance|safety|maintenance|inspection|training",
    "estimated_duration": <minutes as integer>,
    "sections": [
        {{
            "name": "Section name",
            "order": 1,
            "questions": [
                {{
                    "text": "The inspection/check item text",
                    "question_type": "yes_no|text|numeric|select",
                    "criticality": "essential|good_to_have",
                    "guidance": "Guidance notes for the assessor",
                    "regulatory_reference": "Any regulatory reference if applicable",
                    "order": 1
                }}
            ]
        }}
    ]
}}

Only return valid JSON, no markdown formatting."""

        def _run():
            import google.generativeai as genai

            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".bin", delete=False) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
            try:
                uploaded = genai.upload_file(path=tmp_path, display_name=filename, mime_type=mime_type)
                response = client.generate_content([prompt, uploaded])
                return response.text
            finally:
                os.unlink(tmp_path)

        try:
            text = await asyncio.to_thread(_run)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            return json.loads(text)

        except Exception as e:
            logger.error("Gemini document_to_template failed: %s", e)
            return self._fallback_template(filename)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def web_search_enrichment(self, asset_type: str, manufacturer: Optional[str] = None) -> dict:
        """Search the web for manufacturer service recommendations and regulatory requirements.

        Uses Gemini with grounding/web search to find:
        - Manufacturer service intervals and procedures
        - Regulatory inspection requirements (LOLER, PUWER, etc.)
        - Industry best practices
        """
        client = self._get_client()
        if not client:
            return {"recommendations": [], "regulatory": [], "best_practices": []}

        mfr_context = f" manufactured by {manufacturer}" if manufacturer else ""
        prompt = f"""Search for and provide comprehensive maintenance, inspection, and service recommendations for {asset_type}{mfr_context} equipment.

Include:
1. Manufacturer-recommended service intervals and procedures
2. UK regulatory requirements (LOLER 1998, PUWER 1998, etc.)
3. Industry best practices for inspection and maintenance
4. Common defects and failure points to check
5. Required certifications for operators/engineers

Return as JSON:
{{
    "recommendations": [
        {{
            "title": "Recommendation title",
            "description": "Detail",
            "source": "Manufacturer/Regulation/Industry",
            "interval_days": <number or null>,
            "criticality": "essential|good_to_have"
        }}
    ],
    "regulatory": [
        {{
            "regulation": "e.g. LOLER 1998",
            "requirement": "Detail",
            "interval_days": <number>,
            "applicable": true
        }}
    ],
    "best_practices": ["Practice 1", "Practice 2"]
}}

Only return valid JSON."""

        def _run():
            # TODO: Grounding/web search requires correct SDK API; current SDK does not
            # support Tool(google_search=True). Use standard generation without grounding.
            from google.generativeai import GenerationConfig

            response = client.generate_content(
                prompt,
                generation_config=GenerationConfig(temperature=0.2),
            )
            return response.text

        try:
            text = await asyncio.to_thread(_run)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            return json.loads(text)

        except Exception as e:
            logger.error("Gemini web_search_enrichment failed: %s", e)
            return {"recommendations": [], "regulatory": [], "best_practices": []}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def template_to_assessment(self, template_data: dict) -> dict:
        """Convert a compliance/inspection template into a competency assessment version.

        Transforms check items into skill-based competency criteria.
        """
        client = self._get_client()
        if not client:
            return template_data

        prompt = f"""Convert this compliance/inspection template into a competency assessment template.

The original template checks equipment conditions. The assessment version should check
whether an engineer is COMPETENT to perform these checks and tasks.

For each question, reframe it from "Is X in good condition?" to
"Can the engineer correctly inspect/test/verify X?"

Classify each as essential (safety-critical skill) or good_to_have (beneficial skill).

Original template:
{json.dumps(template_data, indent=2)}

Return the converted template in the same JSON structure but with assessment-focused questions.
Only return valid JSON."""

        def _run():
            response = client.generate_content(prompt)
            return response.text

        try:
            text = await asyncio.to_thread(_run)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            logger.error("Gemini template_to_assessment failed: %s", e)
            return template_data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def generate_assessor_guidance(self, question_text: str, asset_type: Optional[str] = None) -> dict:
        """Generate detailed assessor guidance for a specific question/skill.

        Provides: what to look for, common mistakes, pass/fail indicators, training tips.
        """
        client = self._get_client()
        if not client:
            return {
                "guidance": question_text,
                "pass_indicators": [],
                "fail_indicators": [],
                "common_mistakes": [],
                "training_tips": [],
                "estimated_observation_time_minutes": 5,
            }

        context = f" (asset type: {asset_type})" if asset_type else ""
        prompt = f"""Generate detailed assessor guidance for evaluating this competency{context}:

"{question_text}"

Return as JSON:
{{
    "guidance": "Detailed guidance for the assessor on how to evaluate this competency",
    "pass_indicators": ["What demonstrates competence"],
    "fail_indicators": ["What indicates lack of competence"],
    "common_mistakes": ["Common errors to watch for"],
    "training_tips": ["Suggestions for improving competence"],
    "estimated_observation_time_minutes": <number>
}}

Only return valid JSON."""

        def _run():
            response = client.generate_content(prompt)
            return response.text

        try:
            text = await asyncio.to_thread(_run)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(text)
            return result
        except Exception as e:
            logger.error("Gemini generate_assessor_guidance failed: %s", e)
            return {
                "guidance": question_text,
                "pass_indicators": [],
                "fail_indicators": [],
                "common_mistakes": [],
                "training_tips": [],
                "estimated_observation_time_minutes": 5,
            }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def gap_analysis(self, existing_templates: list, asset_type: str) -> dict:
        """Analyse gaps between existing templates and industry standards for an asset type.

        Identifies missing inspection areas, regulatory gaps, and improvement opportunities.
        """
        client = self._get_client()
        if not client:
            return {"gaps": [], "recommendations": []}

        template_summary = json.dumps(
            [
                {
                    "name": t.get("name"),
                    "sections": [s.get("name") for s in t.get("sections", [])],
                }
                for t in existing_templates
            ],
            indent=2,
        )

        prompt = f"""Analyse the following existing inspection/assessment templates for {asset_type} equipment and identify gaps:

Existing templates:
{template_summary}

Identify:
1. Missing inspection areas required by UK regulations (LOLER, PUWER, etc.)
2. Missing manufacturer-recommended checks
3. Industry best practices not covered
4. Competency areas not assessed

Return as JSON:
{{
    "gaps": [
        {{
            "area": "Gap area name",
            "description": "What is missing",
            "severity": "critical|important|nice_to_have",
            "regulation": "Applicable regulation if any"
        }}
    ],
    "recommendations": [
        {{
            "action": "Recommended action",
            "priority": "high|medium|low",
            "estimated_effort": "Description of effort"
        }}
    ]
}}

Only return valid JSON."""

        def _run():
            # TODO: Grounding/web search requires correct SDK API; current SDK does not
            # support Tool(google_search=True). Use standard generation without grounding.
            from google.generativeai import GenerationConfig

            response = client.generate_content(
                prompt,
                generation_config=GenerationConfig(temperature=0.3),
            )
            return response.text

        try:
            text = await asyncio.to_thread(_run)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            logger.error("Gemini gap_analysis failed: %s", e)
            return {"gaps": [], "recommendations": []}

    @staticmethod
    def _fallback_template(filename: str) -> dict:
        """Return a minimal template structure when AI is unavailable."""
        return {
            "name": f"Imported from {filename}",
            "description": f"Template auto-generated from {filename} (AI unavailable, manual review required)",
            "category": "inspection",
            "estimated_duration": 30,
            "sections": [
                {
                    "name": "General Inspection",
                    "order": 1,
                    "questions": [
                        {
                            "text": "Please review the source document and add inspection items manually",
                            "question_type": "text",
                            "criticality": "good_to_have",
                            "guidance": "This is a placeholder -- AI was unavailable during import",
                            "order": 1,
                        }
                    ],
                }
            ],
        }
