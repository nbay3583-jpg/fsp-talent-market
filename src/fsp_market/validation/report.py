from __future__ import annotations

from typing import Any

from fsp_market.validation.matching import LABELS, METHODS

HEADER = ["P@3", "P@5", "R@10", "nDCG@10", "violations@10"]


def markdown(res: dict[str, Any]) -> str:
    m, a = res["matching"], res["assessment"]
    ds = res["dataset"]
    lines = [
        "# VALIDATION REPORT",
        "",
        (
            "MVP validation on a self-made, reproducible dataset. The organisers provided no official dataset or "
            "ground truth. This is **not** a psychometric calibration and the numbers do not describe real candidates."
        ),
        "",
        (
            f"Dataset: version {ds['version']}, sha256 `{ds['sha256'][:16]}…`, {ds['candidates']} candidates, "
            f"{ds['needs']} needs, {ds['label_cells']} label cells ({ds['nonzero_labels']} non-zero), "
            f"relevant = grade >= {ds['relevant_threshold']}."
        ),
        "",
        "## Matching",
        "",
        "| method | P@3 | P@5 | R@10 | nDCG@10 | hard-constraint violations in top-10 |",
        "|---|---|---|---|---|---|",
    ]
    for k in METHODS:
        s = m["summary"][k]
        lines.append(
            f"| {LABELS[k]} | {s['p@3']:.3f} | {s['p@5']:.3f} | {s['r@10']:.3f} | {s['ndcg@10']:.3f} | "
            f"{s['constraint_violations@10']}/{s['returned@10']} ({s['constraint_violation_rate@10']:.1%}) |"
        )
    lines += [
        "",
        f"Deterministic ordering (two runs identical): **{m['deterministic']}**",
        "",
        "### Sensitivity of the evidence-matching weights",
        "",
        "| config | P@5 | nDCG@10 | top-5 Jaccard vs default | top-1 same as default |",
        "|---|---|---|---|---|",
    ]
    for name, s in m["sensitivity"].items():
        lines.append(
            f"| {name} | {s['p@5']:.3f} | {s['ndcg@10']:.3f} | {s['top5_jaccard_vs_default']:.3f} | {s['top1_same_as_default']:.3f} |"
        )
    lines += [
        "",
        "Configurations were fixed in advance and not tuned on the labels.",
        "",
        "## Assessment (reference-solution validation)",
        "",
        f"- reference cases: {a['cases']} ({len(a['personas'])} personas x 3 grades x 2 equivalent variants)",
        f"- grade accuracy vs hand-written expectations: **{a['grade_accuracy']:.3f}**",
        f"- highest verified grade accuracy per persona: {a['highest_grade_accuracy']:.3f}",
        (
            f"- variant stability: identical outcome on {a['variant_stability']['identical_outcome_rate']:.3f} of "
            f"{a['variant_stability']['pairs']} persona-grade pairs; mean |score diff| {a['variant_stability']['mean_abs_score_diff']:.3f}, "
            f"max {a['variant_stability']['max_abs_score_diff']:.3f}"
        ),
        f"- disagreement of more than one sublevel: {a['disagreement_over_one_sublevel_rate']:.3f}",
        f"- rubric / content checks: {a['rubric_checks']['violations']} violations",
        "",
        "| grade test | AUC (knowers vs others) | score margin | competencies covered | items per attempt |",
        "|---|---|---|---|---|",
    ]
    for g, d in a["discrimination"].items():
        lines.append(
            f"| {g} | {d['auc_knowers_vs_others']:.3f} | {d['margin']:.3f} | {a['coverage']['competencies_covered'][g]}/6 | {a['coverage']['items_per_attempt'][g]} |"
        )
    lines += ["", "Random-guess false verification rate (500 seeded guessers):", ""]
    for g, d in a["guessing_baseline"].items():
        lines.append(f"- {g}: {d['false_verification_rate']:.1%} ({d['items']} items)")
    lines += [
        "",
        "Anchors: "
        + "; ".join(f"{x['variant']} solved by {', '.join(x['solved_by'])}" for x in a["anchors"]),
        "",
        "## Failure cases",
        "",
        f"Total recorded: {len(res['failures'])} (full list in `latest.json`). First entries per source:",
        "",
    ]
    seen: dict[str, int] = {}
    for f in res["failures"]:
        src = f["id"].split(":")[0]
        seen[src] = seen.get(src, 0) + 1
        if seen[src] <= 4:
            lines.append(
                f"- `{f['id']}` expected: {f['expected']}; actual: {f['actual']}; reason: {f['probable_reason']}"
            )
    lines += [
        "",
        "Counts by source: " + ", ".join(f"{k}={v}" for k, v in sorted(seen.items())),
        "",
        "## Known limitations",
        "",
    ]
    lines += [f"- {x}" for x in res["limitations"]]
    return "\n".join(lines) + "\n"
