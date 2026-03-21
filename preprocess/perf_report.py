import argparse
import json
from collections import defaultdict
from pathlib import Path


def read_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    return data


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    idx = int(len(s) * p) - 1
    idx = max(0, min(idx, len(s) - 1))
    return s[idx]


def avg(values):
    if not values:
        return None
    return sum(values) / len(values)


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def summarize_by_mode(rows):
    grouped = defaultdict(list)
    for row in rows:
        mode = row.get("mode", "unknown")
        grouped[mode].append(row)

    summary = []
    for mode, items in grouped.items():
        def pick_num(key):
            return [x.get(key) for x in items if isinstance(x.get(key), (int, float))]

        fps_avg = pick_num("render_fps_avg")
        frame95 = pick_num("frame_time_ms_p95")
        long_tasks = pick_num("long_task_count")
        mem = pick_num("memory_peak_mb")
        load_time = pick_num("load_time_ms")
        context_lost = pick_num("webgl_context_lost_count")

        summary.append(
            {
                "mode": mode,
                "samples": len(items),
                "fps_avg_median": percentile(fps_avg, 0.5),
                "fps_avg_p95": percentile(fps_avg, 0.95),
                "frame_p95_median_ms": percentile(frame95, 0.5),
                "long_task_median": percentile(long_tasks, 0.5),
                "memory_peak_median_mb": percentile(mem, 0.5),
                "load_time_median_ms": percentile(load_time, 0.5),
                "context_lost_avg": avg(context_lost),
            }
        )
    return sorted(summary, key=lambda x: x["mode"])


def to_markdown(rows):
    headers = [
        "mode",
        "samples",
        "fps_avg_median",
        "fps_avg_p95",
        "frame_p95_median_ms",
        "long_task_median",
        "memory_peak_median_mb",
        "load_time_median_ms",
        "context_lost_avg",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="性能日志汇总脚本")
    parser.add_argument("--inputs", nargs="+", required=True, help="输入 JSON 日志文件列表")
    parser.add_argument("--output", required=True, help="输出 markdown 报告路径")
    args = parser.parse_args()

    all_rows = []
    for p in args.inputs:
        all_rows.extend(read_json_file(Path(p)))

    summary = summarize_by_mode(all_rows)

    exp_lines = []
    exp_ids = sorted(
        {
            str(r["experiment"]["experiment_id"])
            for r in all_rows
            if isinstance(r.get("experiment"), dict) and r["experiment"].get("experiment_id")
        }
    )
    run_labels = sorted(
        {
            str(r["experiment"]["run_label"])
            for r in all_rows
            if isinstance(r.get("experiment"), dict) and r["experiment"].get("run_label")
        }
    )
    if exp_ids or run_labels:
        exp_lines = ["", "## 实验元数据（来自导出 JSON 的 experiment 字段）", ""]
        if exp_ids:
            exp_lines.append(f"- `experiment_id` 出现：{', '.join(exp_ids)}")
        if run_labels:
            exp_lines.append(f"- `run_label` 出现：{', '.join(run_labels)}")
        exp_lines.append("- 配置方式见仓库 `docs/experiment-recording.md`。")

    md = [
        "# 性能对比汇总报告",
        "",
        "## 模式汇总表",
        "",
        to_markdown(summary),
        "",
        "## 说明",
        "- 使用每个模式的中位数作为主要口径。",
        "- `context_lost_avg` 越低越好。",
        "- 建议与固定操作脚本配合使用，保证可比性。",
        *exp_lines,
    ]

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"[OK] 报告生成: {out}")


if __name__ == "__main__":
    main()
