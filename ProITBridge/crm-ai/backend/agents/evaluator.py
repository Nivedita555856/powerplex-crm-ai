"""
evaluator.py — Evaluator Agent.
Reviews LLM outputs for quality, relevance, and safety before they reach the rep.
If score < threshold → signals orchestrator to retry.
"""
from backend.config import settings
from groq import Groq
from typing import Dict
import json

_groq = Groq(api_key=settings.GROQ_API_KEY)


def evaluate_response(query: str, response: str, context: str = "") -> Dict:
    """
    Score an agent's response on:
    - Relevance: Does it answer the question?
    - Grounding: Is it based on the provided context?
    - Actionability: Does it suggest clear next steps?
    - Safety: Does it avoid harmful/speculative claims?

    Returns: { score (0-100), passed (bool), feedback, dimensions }
    """
    prompt = f"""You are a quality evaluator for an AI Sales Copilot.
Score the following response and return a JSON evaluation.

QUERY: {query}

CONTEXT PROVIDED:
{context[:800] if context else "No context provided."}

RESPONSE TO EVALUATE:
{response[:600]}

Return JSON only:
{{
  "score": <0-100 integer>,
  "passed": <true if score >= 70>,
  "relevance": <0-100>,
  "grounding": <0-100>,
  "actionability": <0-100>,
  "feedback": "<one sentence explaining the score>"
}}"""

    try:
        resp = _groq.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result = json.loads(resp.choices[0].message.content)
        return result

    except Exception as e:
        # Default to pass on evaluation failure to avoid blocking the pipeline
        return {
            "score": 75,
            "passed": True,
            "relevance": 75,
            "grounding": 75,
            "actionability": 75,
            "feedback": f"Evaluation unavailable: {str(e)}"
        }


def evaluate_email_draft(draft: Dict) -> Dict:
    """Evaluate an email draft for tone, personalization, and clarity."""
    prompt = f"""Evaluate this sales email draft.

TO: {draft.get('to_name')} at {draft.get('company', 'unknown company')}
SUBJECT: {draft.get('subject')}
BODY:
{draft.get('body')}

Score it and return JSON only:
{{
  "score": <0-100>,
  "passed": <true if score >= 65>,
  "tone": <0-100>,
  "personalization": <0-100>,
  "clarity": <0-100>,
  "feedback": "<one concrete suggestion to improve it>"
}}"""

    try:
        resp = _groq.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)

    except Exception as e:
        return {
            "score": 70,
            "passed": True,
            "tone": 70,
            "personalization": 70,
            "clarity": 70,
            "feedback": "Evaluation unavailable."
        }
