"""Read and display autopilot session JSONL logs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────


def _ts_str(ts: float, fmt: str = "%H:%M:%S") -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(fmt)


def _dur_str(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def _read_jsonl(path: Path) -> list[dict]:
    events: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def _session_meta(events: list[dict], path: Path) -> dict:
    start_ev = next((e for e in events if e.get("event") == "session_start"), events[0] if events else {})
    end_ev = next((e for e in events if e.get("event") == "session_end"), None)
    started_ts = start_ev.get("ts", 0)

    if end_ev:
        final_phase = end_ev.get("final_phase", "?")
        if final_phase == "DONE":
            status = "done"
        elif final_phase == "HUMAN_PAUSE":
            status = "paused"
        else:
            status = "interrupted"
        elapsed_s = end_ev.get("elapsed_s", 0)
        features_done = end_ev.get("features_done", 0)
        features_total = end_ev.get("features_total", 0)
    else:
        status = "interrupted"
        last_phase = next(
            (e.get("phase") for e in reversed(events) if e.get("event") in ("phase_enter", "phase_exit")),
            "?",
        )
        final_phase = last_phase
        elapsed_s = (events[-1].get("ts", started_ts) - started_ts) if events else 0
        features_done = sum(1 for e in events if e.get("event") == "feature_done" and e.get("success"))
        features_total = sum(1 for e in events if e.get("event") == "feature_done")

    return {
        "id": start_ev.get("session_id", path.stem),
        "path": path,
        "started_ts": started_ts,
        "backend": start_ev.get("backend", "?"),
        "max_parallel": start_ev.get("max_parallel", 1),
        "status": status,
        "final_phase": final_phase,
        "elapsed_s": elapsed_s,
        "features_done": features_done,
        "features_total": features_total,
    }


# ── public API ─────────────────────────────────────────────────────────────


def list_sessions(sessions_dir: Path) -> list[dict]:
    """Return session summaries sorted newest-first."""
    if not sessions_dir.exists():
        return []
    results = []
    for p in sessions_dir.glob("*.jsonl"):
        events = _read_jsonl(p)
        if events:
            results.append(_session_meta(events, p))
    return sorted(results, key=lambda s: s["started_ts"], reverse=True)


def format_list(sessions: list[dict]) -> str:
    if not sessions:
        return "No sessions found."
    header = f"{'SESSION ID':<28}  {'STARTED':<19}  {'STATUS':<12}  {'PHASE':<12}  {'ELAPSED':>9}  FEATURES"
    sep = "-" * 90
    lines = [header, sep]
    for s in sessions:
        dt = datetime.fromtimestamp(s["started_ts"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        features = f"{s['features_done']}/{s['features_total']}" if s["features_total"] else "-"
        lines.append(
            f"{s['id'][:28]:<28}  {dt:<19}  {s['status']:<12}  {s['final_phase']:<12}"
            f"  {_dur_str(s['elapsed_s']):>9}  {features}"
        )
    return "\n".join(lines)


def format_show(
    path: Path,
    feature_filter: str | None = None,
    show_output: bool = False,
) -> str:
    events = _read_jsonl(path)
    if not events:
        return "Empty session file."

    meta = _session_meta(events, path)
    dt = datetime.fromtimestamp(meta["started_ts"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"━━━ Session {meta['id']} ━━━",
        f"Started:  {dt}",
        f"Backend:  {meta['backend']}  (parallel: {meta['max_parallel']})",
        f"Status:   {meta['status']} — {meta['final_phase']}",
        f"Elapsed:  {_dur_str(meta['elapsed_s'])}",
        f"Features: {meta['features_done']}/{meta['features_total']}",
        "",
    ]

    # Segment events into phases
    # DEV_LOOP events carry feature_id; all others are top-level
    current_phase: str | None = None
    phase_events: list[dict] = []
    phase_segments: list[tuple[str, list[dict]]] = []

    for ev in events:
        etype = ev.get("event")
        if etype == "session_start":
            continue
        if etype == "phase_enter":
            if current_phase is not None:
                phase_segments.append((current_phase, phase_events))
            current_phase = ev.get("phase", "?")
            phase_events = []
        elif etype == "session_end":
            if current_phase is not None:
                phase_segments.append((current_phase, phase_events))
            current_phase = None
            phase_events = []
        else:
            phase_events.append(ev)

    if current_phase is not None:
        phase_segments.append((current_phase, phase_events))

    for phase, pevents in phase_segments:
        if phase == "DEV_LOOP":
            _render_dev_loop(pevents, lines, feature_filter, show_output)
        else:
            if feature_filter:
                continue
            _render_phase(phase, pevents, lines, show_output)

    return "\n".join(lines)


# ── rendering helpers ──────────────────────────────────────────────────────


def _render_phase(phase: str, events: list[dict], lines: list[str], show_output: bool) -> None:
    exit_ev = next(
        (e for e in events if e.get("event") == "phase_exit" and e.get("phase") == phase), None
    )
    dur = _dur_str(exit_ev.get("duration_s", 0)) if exit_ev else "?"
    ok = "✓" if (exit_ev and exit_ev.get("passed")) else ("✗" if exit_ev else "?")
    pad = max(0, 35 - len(phase))
    lines.append(f"── {phase} {'─' * pad} {dur} {ok}")

    for ev in events:
        if ev.get("event") != "agent_call":
            continue
        _render_agent_call(ev, lines, indent="  ")
        if show_output and ev.get("output_tail"):
            _render_output_tail(ev["output_tail"], lines, indent="    ")
    lines.append("")


def _render_dev_loop(
    events: list[dict],
    lines: list[str],
    feature_filter: str | None,
    show_output: bool,
) -> None:
    # Group by feature_id preserving first-seen order
    feature_ids: list[str] = []
    by_feature: dict[str, list[dict]] = {}
    for ev in events:
        fid = ev.get("feature_id")
        if not fid:
            continue
        if fid not in by_feature:
            feature_ids.append(fid)
            by_feature[fid] = []
        by_feature[fid].append(ev)

    if not feature_ids:
        return

    targets = [feature_filter] if feature_filter and feature_filter in by_feature else feature_ids
    lines.append("── DEV_LOOP ─────────────────────────────")
    for fid in targets:
        _render_feature(fid, by_feature[fid], lines, show_output)
    lines.append("")


def _render_feature(
    fid: str, events: list[dict], lines: list[str], show_output: bool
) -> None:
    done_ev = next((e for e in events if e.get("event") == "feature_done"), None)
    if done_ev:
        ok = "✓" if done_ev.get("success") else "✗"
        dur = _dur_str(done_ev.get("duration_s", 0))
        retries = done_ev.get("fix_retries", 0)
        title = done_ev.get("title", "")
        retry_str = f"  {retries} fix retries" if retries else ""
        lines.append(f"  {fid}  {ok}  {dur}{retry_str}  {title}")
    else:
        lines.append(f"  {fid}  (incomplete)")

    for ev in events:
        if ev.get("event") != "agent_call":
            continue
        _render_agent_call(ev, lines, indent="    ")
        if show_output and ev.get("output_tail"):
            _render_output_tail(ev["output_tail"], lines, indent="      ")
    lines.append("")


def _render_agent_call(ev: dict, lines: list[str], indent: str) -> None:
    ok = "✓" if ev.get("success") else "✗"
    dur = _dur_str(ev.get("duration_s", 0))
    agent = ev.get("agent", "?")
    backend = ev.get("backend", "?")
    err = f"  [{ev['error_type']}]" if not ev.get("success") and ev.get("error_type") else ""
    retry = f"  retry={ev['local_retry']}" if ev.get("local_retry") else ""
    ts = _ts_str(ev.get("ts", 0))
    out_chars = ev.get("output_chars", 0)
    lines.append(
        f"{indent}{ts}  {agent:<14} {backend:<10} {dur:>7}  {ok}"
        f"  {out_chars}chars{err}{retry}"
    )


def _render_output_tail(tail: str, lines: list[str], indent: str) -> None:
    tail_lines = tail.splitlines()[-12:]
    lines.append(f"{indent}┌── output tail ──")
    for tl in tail_lines:
        lines.append(f"{indent}│ {tl}")
    lines.append(f"{indent}└──")
