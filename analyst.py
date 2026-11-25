"""AI Earnings Call Analyst.

Reads an earnings call transcript and pulls out the things an analyst
actually looks for: forward guidance, risks management brought up,
how confident the tone was, and how prepared remarks compare to the Q&A.

Two modes:
  * demo (default): rule-based extraction, works offline, no API key
  * ai: sends each section to Claude for a structured summary
        (needs ANTHROPIC_API_KEY and `pip install anthropic`)
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict

# Small finance sentiment word lists, in the style of the
# Loughran-McDonald dictionary (general-purpose sentiment lists
# misread words like "liability" or "tax" as negative).
POSITIVE = {
    "strong", "record", "growth", "grew", "exceeded", "beat", "improved",
    "improvement", "momentum", "confident", "expand", "expanded", "gain",
    "gains", "outperformed", "accelerate", "accelerated", "healthy",
    "robust", "upside", "raised", "raising", "solid", "opportunity",
}
NEGATIVE = {
    "decline", "declined", "weak", "weaker", "loss", "losses", "headwind",
    "headwinds", "pressure", "challenging", "uncertain", "uncertainty",
    "lower", "slowdown", "miss", "missed", "impairment", "risk", "risks",
    "downturn", "cautious", "softness", "soft", "delay", "delays",
}
# Hedging words: lots of these = management is less sure of itself
HEDGES = {"may", "might", "could", "approximately", "roughly", "believe",
          "expect", "anticipate", "potentially", "possibly", "somewhat"}

GUIDANCE_PATTERNS = [
    r"\b(we|management) (now )?(expect|anticipate|project|forecast|guide)",
    r"\bguidance\b",
    r"\boutlook\b",
    r"\bfor (the )?(full|fiscal) year\b",
    r"\bnext quarter\b",
    r"\b(raising|raise|lowering|lower|reaffirm|reaffirming|maintain)\w* (our )?(guidance|outlook|forecast)",
]
RISK_TOPICS = {
    "macro / demand": ["macro", "demand", "consumer", "recession", "spending"],
    "supply chain": ["supply", "supplier", "shortage", "inventory", "freight"],
    "pricing / margins": ["pricing", "margin", "discount", "promotion"],
    "costs / inflation": ["inflation", "cost", "wage", "labor"],
    "fx / rates": ["currency", "foreign exchange", "fx", "interest rate"],
    "competition": ["competition", "competitor", "competitive"],
    "regulation": ["regulation", "regulatory", "tariff", "legal"],
}

MONEY = r"\$\s?\d[\d,.]*\s?(billion|million|thousand|[bmk])?"
PERCENT = r"\d+(\.\d+)?\s?(%|percent)"


@dataclass
class Section:
    name: str
    text: str
    sentiment: float = 0.0     # -1 (very negative) to +1 (very positive)
    hedge_rate: float = 0.0    # hedge words per 100 words
    words: int = 0


@dataclass
class Report:
    company: str
    quarter: str
    guidance: list = field(default_factory=list)
    risks: dict = field(default_factory=dict)
    numbers: list = field(default_factory=list)
    analyst_focus: dict = field(default_factory=dict)
    sections: list = field(default_factory=list)
    overall_sentiment: float = 0.0
    tone_gap: float = 0.0          # prepared remarks minus Q&A sentiment
    summary: str = ""
    mode: str = "demo"


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def tokenize(text):
    return re.findall(r"[a-z']+", text.lower())


def score_sentiment(text):
    """Net tone between -1 and 1 using the finance word lists."""
    words = tokenize(text)
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 3)


def hedge_rate(text):
    words = tokenize(text)
    if not words:
        return 0.0
    hedges = sum(1 for w in words if w in HEDGES)
    return round(100 * hedges / len(words), 2)


def parse_transcript(raw):
    """Pull the header and split into prepared remarks and Q&A.

    Expected header lines (optional):
        Company: Example Corp
        Quarter: Q3 2026
    The Q&A starts at a line containing 'Question-and-Answer' or 'Q&A'.
    """
    company = re.search(r"^Company:\s*(.+)$", raw, re.M)
    quarter = re.search(r"^Quarter:\s*(.+)$", raw, re.M)
    body = re.sub(r"^(Company|Quarter):.*$", "", raw, flags=re.M).strip()

    split = re.search(r"^.*(Question-and-Answer|Q&A).*$", body, re.M | re.I)
    if split:
        prepared = body[:split.start()].strip()
        qa = body[split.end():].strip()
    else:
        prepared, qa = body, ""

    return (company.group(1).strip() if company else "Unknown company",
            quarter.group(1).strip() if quarter else "Unknown quarter",
            prepared, qa)


def management_text(text):
    """Only the lines management said. Analyst questions and the operator
    are dropped, so "You raised guidance?" from an analyst doesn't count
    as the company giving guidance."""
    keep = []
    for line in text.splitlines():
        speaker = line.split(":", 1)[0].lower() if ":" in line[:60] else ""
        if speaker.startswith(("analyst", "operator")):
            continue
        keep.append(line.split(":", 1)[1] if speaker else line)
    return "\n".join(keep)


def analyst_questions(text):
    """Topics analysts pushed on: a good read on what the market is worried about."""
    topics = {}
    for line in text.splitlines():
        if not line.lower().startswith("analyst") or ":" not in line:
            continue
        q = line.split(":", 1)[1].strip()
        for topic, keys in RISK_TOPICS.items():
            if any(k in q.lower() for k in keys):
                topics.setdefault(topic, []).append(q)
        if "guidance" in q.lower() or "range" in q.lower():
            topics.setdefault("guidance", []).append(q)
    return topics


def find_guidance(text):
    hits = []
    for s in split_sentences(text):
        low = s.lower()
        if any(re.search(p, low) for p in GUIDANCE_PATTERNS):
            if re.search(MONEY, s) or re.search(PERCENT, s) or "guidance" in low:
                direction = "neutral"
                if re.search(r"rais|increas|above|higher|up\b", low):
                    direction = "up"
                elif re.search(r"lower|reduc|below|cut|down\b", low):
                    direction = "down"
                hits.append({"sentence": s, "direction": direction})
    return hits


def find_risks(text):
    found = {}
    for s in split_sentences(text):
        low = s.lower()
        if not any(w in low for w in ("risk", "headwind", "pressure", "uncertain",
                                      "challeng", "soft", "decline", "impact",
                                      "watching", "inflation", "tariff")):
            continue
        for topic, keys in RISK_TOPICS.items():
            if any(k in low for k in keys):
                found.setdefault(topic, []).append(s)
    return found


def find_numbers(text):
    out = []
    for s in split_sentences(text):
        if re.search(MONEY, s) or re.search(PERCENT, s):
            if re.search(r"revenue|sales|margin|eps|earnings|income|cash|growth", s.lower()):
                out.append(s)
    return out


def ai_summary(prepared, qa):
    """Optional: ask Claude for a structured summary. Returns None if unavailable."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic()
    prompt = (
        "You are a sell-side equity analyst. Read this earnings call and reply with "
        "JSON only: {\"summary\": str (3 sentences), \"guidance\": [str], "
        "\"risks\": [str], \"analyst_concerns\": [str]}. Only use facts in the text.\n\n"
        f"PREPARED REMARKS:\n{prepared}\n\nQ&A:\n{qa}"
    )
    msg = client.messages.create(
        model=os.environ.get("ANALYST_MODEL", "claude-sonnet-4-5"),
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def analyze(raw, use_ai=False):
    company, quarter, prepared, qa = parse_transcript(raw)
    report = Report(company=company, quarter=quarter)

    for name, text in (("Prepared remarks", prepared), ("Q&A", qa)):
        if text:
            report.sections.append(Section(
                name=name, text=text, sentiment=score_sentiment(management_text(text)),
                hedge_rate=hedge_rate(management_text(text)),
                words=len(tokenize(management_text(text)))))

    full = management_text(prepared + "\n" + qa)
    report.guidance = find_guidance(full)
    report.risks = find_risks(full)
    report.numbers = find_numbers(management_text(prepared))
    report.analyst_focus = analyst_questions(qa)
    report.overall_sentiment = score_sentiment(full)
    if len(report.sections) == 2:
        report.tone_gap = round(report.sections[0].sentiment - report.sections[1].sentiment, 3)

    ups = sum(1 for g in report.guidance if g["direction"] == "up")
    downs = sum(1 for g in report.guidance if g["direction"] == "down")
    tone = "positive" if report.overall_sentiment > 0.15 else (
        "negative" if report.overall_sentiment < -0.15 else "mixed")
    report.summary = (
        f"{company} {quarter}: overall tone {tone} ({report.overall_sentiment:+.2f}). "
        f"{len(report.guidance)} guidance statements ({ups} raised, {downs} lowered). "
        f"Top risk areas: {', '.join(sorted(report.risks, key=lambda k: -len(report.risks[k]))[:3]) or 'none flagged'}."
    )
    if report.tone_gap > 0.3:
        report.summary += " Management sounded noticeably more upbeat in prepared remarks than in Q&A."

    if use_ai:
        ai = ai_summary(prepared, qa)
        if ai:
            report.mode = "ai"
            report.summary = ai.get("summary", report.summary)
            report.ai_extra = ai  # type: ignore[attr-defined]
    return report


def compare(previous, current):
    """Quarter-over-quarter change in tone and guidance direction."""
    return {
        "sentiment_change": round(current.overall_sentiment - previous.overall_sentiment, 3),
        "guidance_up_change": sum(g["direction"] == "up" for g in current.guidance)
        - sum(g["direction"] == "up" for g in previous.guidance),
        "new_risk_areas": sorted(set(current.risks) - set(previous.risks)),
        "dropped_risk_areas": sorted(set(previous.risks) - set(current.risks)),
    }


def to_json(report):
    d = asdict(report)
    for s in d["sections"]:
        s.pop("text")
    return d
