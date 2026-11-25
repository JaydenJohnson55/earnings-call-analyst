from analyst import (analyze, compare, find_guidance, hedge_rate,
                     parse_transcript, score_sentiment)
from report import render

Q2 = open("northwind_q2_2026.txt", encoding="utf-8").read()
Q3 = open("northwind_q3_2026.txt", encoding="utf-8").read()


def test_parse_header_and_sections():
    company, quarter, prepared, qa = parse_transcript(Q3)
    assert company.startswith("Northwind Outdoor")
    assert quarter == "Q3 2026"
    assert "raising our full-year" in prepared
    assert "Congratulations" in qa and "Congratulations" not in prepared


def test_sentiment_direction():
    assert score_sentiment("Record growth and strong momentum.") > 0.5
    assert score_sentiment("Weak demand and losses from headwinds.") < -0.5
    assert score_sentiment("The meeting is on Tuesday.") == 0.0


def test_finance_words_are_not_negative():
    # "liability" and "tax" are normal finance words, not bad news
    assert score_sentiment("Our tax liability was in line.") == 0.0


def test_hedge_rate():
    assert hedge_rate("We may possibly see roughly flat sales.") > 20
    assert hedge_rate("Sales grew.") == 0.0


def test_guidance_direction():
    up = find_guidance("We are raising our full-year guidance to $1.8 billion.")
    assert up and up[0]["direction"] == "up"
    held = find_guidance("We are maintaining our guidance of revenue between $1.70 billion and $1.75 billion.")
    assert held and held[0]["direction"] == "neutral"


def test_guidance_ignores_non_forward_statements():
    assert find_guidance("Revenue was $412 million last quarter.") == []


def test_q3_more_positive_than_q2():
    q2, q3 = analyze(Q2), analyze(Q3)
    assert q3.overall_sentiment > q2.overall_sentiment
    c = compare(q2, q3)
    assert c["sentiment_change"] > 0
    assert c["guidance_up_change"] >= 1


def test_risks_found():
    r = analyze(Q2)
    assert "regulation" in r.risks          # tariffs
    assert "pricing / margins" in r.risks   # promotional pressure


def test_key_numbers_only_from_prepared_remarks():
    r = analyze(Q3)
    assert any("$468 million" in n for n in r.numbers)


def test_html_renders():
    q2, q3 = analyze(Q2), analyze(Q3)
    page = render(q3, compare(q2, q3))
    assert "<html" in page and "Versus last quarter" in page
    assert "Northwind" in page


def test_demo_mode_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = analyze(Q3, use_ai=True)
    assert r.mode == "demo"   # falls back cleanly when no key is set


def test_analyst_questions_are_not_guidance():
    r = analyze(Q3)
    assert not any("You raised guidance" in g["sentence"] for g in r.guidance)
    assert "guidance" in r.analyst_focus


def test_wage_inflation_flagged():
    r = analyze(Q3)
    assert "costs / inflation" in r.risks
