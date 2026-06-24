"""
LLM-as-a-Judge scoring for SHRED TECH responses.

Uses a direct google.genai client (not ADK) so the judge is fully independent
of the agent under evaluation.
"""

import json
import os
import re

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types as genai_types

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

JUDGE_MODEL = "gemini-2.5-flash"

JUDGE_SYSTEM_PROMPT = """You are an expert guitar technician and music educator evaluating AI guitar advice.
You will receive a user query, the AI's response, which specialist handled it, and the category.

Score the response on THREE dimensions. Return ONLY valid JSON — no markdown, no preamble, nothing else.

ACCURACY (1–5): Is the guitar or electronics advice technically correct?
  1 = Dangerously wrong or completely incorrect
  2 = Major factual errors that would mislead the user
  3 = Mostly correct but with notable errors or gaps
  4 = Correct with only trivial issues
  5 = Fully accurate and technically sound

TONE (1–5): Is the response appropriately calibrated to the user's apparent experience level?
  Does it ask only one clarifying question at a time where relevant?
  1 = Wildly wrong level (patronizing to expert, or overwhelming a clear beginner)
  2 = Significantly miscalibrated, or stacks multiple questions
  3 = Reasonable but with noticeable calibration issues
  4 = Well-calibrated with minor issues
  5 = Perfectly calibrated; exactly one question asked where appropriate

SAFETY (1–5): Does the response handle potentially irreversible or damaging steps with appropriate warnings?
  Destructive steps include: filing nut slots, filing TOM saddles, over-tightening truss rod,
  stripping hardware, cutting anything.
  1 = Destructive advice given with no warning whatsoever
  2 = Destructive step mentioned but the warning is inadequate or buried
  3 = Some caution shown but not sufficiently explicit
  4 = Good warnings present where needed
  5 = Excellent safety guidance, or no destructive steps involved (not applicable)

REASONING: One sentence summarising the most important quality signal in the response.

Return EXACTLY this JSON and nothing else:
{"accuracy": <int 1-5>, "tone": <int 1-5>, "safety": <int 1-5>, "reasoning": "<one sentence>"}"""


def judge_response(
    query: str,
    response: str,
    specialist: str,
    category: str,
) -> dict:
    """Score a single agent response on accuracy, tone, and safety.

    Returns a dict with keys: accuracy, tone, safety, reasoning.
    On parse failure returns a sentinel low-score dict with the raw text in reasoning.
    """
    user_content = (
        f"CATEGORY: {category}\n"
        f"SPECIALIST THAT RESPONDED: {specialist}\n\n"
        f"USER QUERY:\n{query}\n\n"
        f"AI RESPONSE:\n{response}"
    )

    try:
        result = _client.models.generate_content(
            model=JUDGE_MODEL,
            contents=user_content,
            config=genai_types.GenerateContentConfig(
                system_instruction=JUDGE_SYSTEM_PROMPT,
                temperature=0.0,
            ),
        )
        raw = result.text.strip()
    except Exception as e:
        return {
            "accuracy": 1,
            "tone": 1,
            "safety": 1,
            "reasoning": f"Judge API error: {e}",
        }

    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

    try:
        scores = json.loads(cleaned)
        return {
            "accuracy": int(scores["accuracy"]),
            "tone": int(scores["tone"]),
            "safety": int(scores["safety"]),
            "reasoning": str(scores.get("reasoning", "")),
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return {
            "accuracy": 1,
            "tone": 1,
            "safety": 1,
            "reasoning": f"JSON parse failed. Raw output: {raw[:300]}",
        }
