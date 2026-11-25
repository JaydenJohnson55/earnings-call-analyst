"""Turns analysis results into a one-page HTML dashboard."""

import html


def _bar(value):
    """Sentiment bar from -1 to +1, drawn with plain CSS."""
    pct = int((value + 1) * 50)
    color = "#2e7d32" if value > 0.15 else ("#c62828" if value < -0.15 else "#9e9e9e")
    return (f'<div class="bar"><div class="fill" style="width:{pct}%;background:{color}"></div>'
            f'<span>{value:+.2f}</span></div>')


def render(report, comparison=None):
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(s.name)}</td><td>{_bar(s.sentiment)}</td><td>{s.hedge_rate}</td><td>{s.words}</td></tr>"
        for s in report.sections)
    guidance = "".join(
        f'<li><span class="tag {g["direction"]}">{g["direction"]}</span> {e(g["sentence"])}</li>'
        for g in report.guidance) or "<li>No forward guidance found.</li>"
    risks = "".join(
        f"<li><b>{e(topic)}</b> ({len(lines)}): {e(lines[0])}</li>"
        for topic, lines in sorted(report.risks.items(), key=lambda kv: -len(kv[1]))) or "<li>None flagged.</li>"
    focus = "".join(
        f"<li><b>{e(topic)}</b>: {e(qs[0])}</li>" for topic, qs in report.analyst_focus.items()) or "<li>None.</li>"
    numbers = "".join(f"<li>{e(n)}</li>" for n in report.numbers[:8]) or "<li>None found.</li>"

    comp = ""
    if comparison:
        comp = (f"<h2>Versus last quarter</h2><ul>"
                f"<li>Tone change: {comparison['sentiment_change']:+.2f}</li>"
                f"<li>Change in 'raised' guidance statements: {comparison['guidance_up_change']:+d}</li>"
                f"<li>New risk areas: {e(', '.join(comparison['new_risk_areas']) or 'none')}</li>"
                f"<li>Risk areas no longer mentioned: {e(', '.join(comparison['dropped_risk_areas']) or 'none')}</li></ul>")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(report.company)} {e(report.quarter)} call analysis</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:40px auto;padding:0 16px;color:#222}}
h1{{margin-bottom:0}} .sub{{color:#666;margin-top:4px}}
table{{border-collapse:collapse;width:100%}} td,th{{padding:6px;border-bottom:1px solid #ddd;text-align:left}}
.bar{{position:relative;background:#eee;height:18px;width:220px;border-radius:3px}}
.fill{{height:100%;border-radius:3px}} .bar span{{position:absolute;right:6px;top:0;font-size:12px}}
.tag{{font-size:12px;padding:1px 6px;border-radius:3px;background:#eee}}
.tag.up{{background:#c8e6c9}} .tag.down{{background:#ffcdd2}}
.summary{{background:#f5f5f5;padding:12px 16px;border-left:4px solid #1565c0}}
</style></head><body>
<h1>{e(report.company)} &middot; {e(report.quarter)}</h1>
<p class="sub">Earnings call analysis &middot; mode: {e(report.mode)}</p>
<p class="summary">{e(report.summary)}</p>
<h2>Tone by section</h2>
<table><tr><th>Section</th><th>Sentiment</th><th>Hedges per 100 words</th><th>Words</th></tr>{rows}</table>
<h2>Forward guidance</h2><ul>{guidance}</ul>
<h2>Risks management raised</h2><ul>{risks}</ul>
<h2>What analysts pushed on</h2><ul>{focus}</ul>
<h2>Key numbers</h2><ul>{numbers}</ul>
{comp}
</body></html>"""
