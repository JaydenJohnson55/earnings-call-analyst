"""Command line entry point.

Examples:
  python cli.py northwind_q2_2026.txt
  python cli.py northwind_q3_2026.txt --compare northwind_q2_2026.txt --html report.html
  python cli.py northwind_q3_2026.txt --ai      (needs ANTHROPIC_API_KEY)
"""

import argparse
import json

from analyst import analyze, compare, to_json
from report import render


def main():
    p = argparse.ArgumentParser(description="Analyze an earnings call transcript.")
    p.add_argument("transcript")
    p.add_argument("--compare", help="previous quarter transcript")
    p.add_argument("--html", help="write an HTML dashboard to this path")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    p.add_argument("--ai", action="store_true", help="use Claude for the summary")
    args = p.parse_args()

    with open(args.transcript, encoding="utf-8") as f:
        current = analyze(f.read(), use_ai=args.ai)

    comparison = None
    if args.compare:
        with open(args.compare, encoding="utf-8") as f:
            comparison = compare(analyze(f.read()), current)

    if args.json:
        out = to_json(current)
        if comparison:
            out["vs_previous"] = comparison
        print(json.dumps(out, indent=2))
    else:
        print(current.summary)
        print()
        for s in current.sections:
            print(f"  {s.name:<17} tone {s.sentiment:+.2f}   hedges/100 words {s.hedge_rate}")
        print(f"\nGuidance ({len(current.guidance)}):")
        for g in current.guidance:
            print(f"  [{g['direction']:>7}] {g['sentence']}")
        print("\nRisk areas:")
        for topic, lines in current.risks.items():
            print(f"  {topic}: {len(lines)} mention(s)")
        if comparison:
            print("\nVs previous quarter:", comparison)

    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render(current, comparison))
        print(f"\nDashboard written to {args.html}")


if __name__ == "__main__":
    main()
