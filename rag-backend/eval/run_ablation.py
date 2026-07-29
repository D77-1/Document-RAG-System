"""2x2 retrieval ablation: (hybrid on/off) x (rerank on/off).

Note: rerank OFF also disables the relevance threshold — the threshold only
applies to genuine 0..1 rerank scores (see retriever.py), so the "no_rerank"
cells measure removing the *entire* rerank+threshold stage.

Usage:
    ./.venv/Scripts/python.exe eval/run_ablation.py [--limit N] [--questions PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from run_eval import apply_toggles, build_config_snapshot, run  

# (cell_name, no_hybrid, no_rerank) — full 在前，作为 Δ 的基准
CELLS = [
    ("full", False, False),
    ("no_rerank", False, True),
    ("vector_only", True, False),
    ("vector_only_no_rerank", True, True),
]

CELL_LABELS = {
    "full": "混检 + 精排（基线）",
    "no_rerank": "混检，无精排",
    "vector_only": "纯向量 + 精排",
    "vector_only_no_rerank": "纯向量，无精排",
}


def fmt_delta(v: float, base: float) -> str:
    d = v - base
    return f"{v:.3f} ({d:+.3f})" if abs(d) > 1e-9 else f"{v:.3f}"


def main() -> int:
    ap = argparse.ArgumentParser(description="2x2 retrieval ablation")
    ap.add_argument("--questions", type=Path, default=Path("eval/sample_questions.json"))
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--num-relevancy-queries", type=int, default=3)
    ap.add_argument("--judge-model", type=str, default="qwen-turbo")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    out_dir = Path("eval/results") / f"ablation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cell_summaries = {}
    cell_by_category = {}
    for name, no_hybrid, no_rerank in CELLS:
        print(f"\n===== cell: {name} =====")
        apply_toggles(no_hybrid, no_rerank)
        summary, results = run(args.questions, args.top_k,
                               args.num_relevancy_queries, args.limit,
                               judge_model=args.judge_model)
        cell_summaries[name] = summary

        # per-category aggregation
        cats = {}
        for r in results:
            if r.error is not None:
                continue
            cats.setdefault(r.category or "uncategorized", []).append(r)
        cell_by_category[name] = {
            c: {
                "n": len(rs),
                "context_precision": sum(x.context_precision for x in rs) / len(rs),
                "faithfulness": sum(x.faithfulness for x in rs) / len(rs),
                "answer_relevancy": sum(x.answer_relevancy for x in rs) / len(rs),
            }
            for c, rs in cats.items()
        }

        with open(out_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump({
                "summary": asdict(summary),
                "config": build_config_snapshot(args.judge_model),
                "run_args": {
                    "top_k": args.top_k,
                    "num_relevancy_queries": args.num_relevancy_queries,
                    "limit": args.limit,
                },
                "by_category": cell_by_category[name],
                "per_question": [asdict(r) for r in results],
            }, f, ensure_ascii=False, indent=2)
        print(f"cell {name}: CP={summary.context_precision:.3f} "
              f"FA={summary.faithfulness:.3f} AR={summary.answer_relevancy:.3f}")

    # ---- summary.md ----
    base = cell_summaries["full"]
    lines = [
        "# 检索消融实验结果（2×2）",
        "",
        f"- 评测集：{base.num_questions} 题 · 裁判模型：{args.judge_model} · 生成模型：{build_config_snapshot(args.judge_model)['llm_model']}",
        "- 口径说明：\"无精排\"同时关闭相关性阈值（阈值只作用于 0..1 精排分，见 retriever.py）",
        "",
        "| 配置 | Context Precision | Faithfulness | Answer Relevancy |",
        "|---|---|---|---|",
    ]
    for name, *_ in CELLS:
        s = cell_summaries[name]
        lines.append(
            f"| {CELL_LABELS[name]} | {fmt_delta(s.context_precision, base.context_precision)} "
            f"| {fmt_delta(s.faithfulness, base.faithfulness)} "
            f"| {fmt_delta(s.answer_relevancy, base.answer_relevancy)} |")

    lines += ["", "## 分题型 Context Precision", ""]
    categories = sorted({c for m in cell_by_category.values() for c in m})
    lines.append("| 配置 | " + " | ".join(categories) + " |")
    lines.append("|---|" + "---|" * len(categories))
    for name, *_ in CELLS:
        row = [CELL_LABELS[name]]
        for c in categories:
            v = cell_by_category[name].get(c)
            row.append(f"{v['context_precision']:.3f} (n={v['n']})" if v else "—")
        lines.append("| " + " | ".join(row) + " |")

    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nAblation written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
