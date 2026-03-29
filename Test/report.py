"""
report.py — Post-drive report with matplotlib graphs
Shows: fatigue timeline, alert markers, session summary, historical trend
"""
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np
import json
from datetime import datetime
from session import load_sessions, load_timeline

# ── Grade thresholds ──────────────────────────────────────────────
def _grade(avg_score: float, critical: int) -> tuple:
    """Returns (grade, color, description)"""
    if critical > 0:
        return "F", "#ff2244", "Dangerous — CRITICAL event occurred"
    if avg_score < 15:
        return "A", "#00e5a0", "Excellent — Very safe drive"
    if avg_score < 30:
        return "B", "#7fff00", "Good — Minor fatigue detected"
    if avg_score < 50:
        return "C", "#ffd000", "Fair — Moderate fatigue"
    if avg_score < 70:
        return "D", "#ff7b00", "Poor — Significant fatigue"
    return "F", "#ff2244", "Dangerous — Severe fatigue throughout"


def _fatigue_label(score: float) -> str:
    if score < 20:  return "Alert"
    if score < 40:  return "Mild"
    if score < 60:  return "Moderate"
    if score < 80:  return "High"
    return "Severe"


# ── Single session report ─────────────────────────────────────────
def show_session_report(session_id: int, user_name: str = ""):
    timeline = load_timeline(session_id)
    if not timeline:
        print(f"[Report] No timeline data for session {session_id}")
        return

    # Pull arrays
    times   = [s["t"]       for s in timeline]
    scores  = [s["score"]   for s in timeline]
    perclos = [s["perclos"] for s in timeline]
    blinks  = [s["blink"]   for s in timeline]
    alerts  = [s["alert"]   for s in timeline]
    ears    = [s["ear"]     for s in timeline]

    avg_score   = np.mean(scores)
    critical_ct = sum(1 for a in alerts if a == 3)
    grade, gc, gdesc = _grade(avg_score, critical_ct)

    # Alert event positions
    a1_t = [times[i] for i in range(len(alerts)) if alerts[i] == 1]
    a2_t = [times[i] for i in range(len(alerts)) if alerts[i] == 2]
    a3_t = [times[i] for i in range(len(alerts)) if alerts[i] == 3]
    a1_s = [scores[i] for i in range(len(alerts)) if alerts[i] == 1]
    a2_s = [scores[i] for i in range(len(alerts)) if alerts[i] == 2]
    a3_s = [scores[i] for i in range(len(alerts)) if alerts[i] == 3]

    # ── Layout ────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 10), facecolor="#0a0c0f")
    fig.suptitle(
        f"Drive Report  {'— ' + user_name if user_name else ''}   "
        f"Grade: {grade}  ({gdesc})",
        color="white", fontsize=14, fontweight="bold", y=0.98
    )
    gs = gridspec.GridSpec(3, 2, figure=fig,
                           hspace=0.45, wspace=0.3,
                           left=0.07, right=0.97, top=0.93, bottom=0.07)

    ax_main  = fig.add_subplot(gs[0, :])   # full width — fatigue score
    ax_perc  = fig.add_subplot(gs[1, 0])   # PERCLOS
    ax_blink = fig.add_subplot(gs[1, 1])   # blink rate
    ax_ear   = fig.add_subplot(gs[2, 0])   # EAR trace
    ax_sum   = fig.add_subplot(gs[2, 1])   # text summary

    style = {"facecolor": "#111318", "edgecolor": "#1e2430"}
    for ax in [ax_main, ax_perc, ax_blink, ax_ear]:
        ax.set_facecolor("#111318")
        ax.tick_params(colors="#555e70")
        ax.spines[:].set_color("#1e2430")
        ax.xaxis.label.set_color("#8899aa")
        ax.yaxis.label.set_color("#8899aa")
        ax.title.set_color("#99aabb")

    # ── Main fatigue score ─────────────────────────────────────────
    ax_main.plot(times, scores, color="#00e5a0", lw=1.5, label="Fatigue score")
    ax_main.fill_between(times, scores, alpha=0.15, color="#00e5a0")
    ax_main.axhline(30, color="#ffd000", lw=0.8, ls="--", alpha=0.5)
    ax_main.axhline(60, color="#ff7b00", lw=0.8, ls="--", alpha=0.5)
    ax_main.axhline(80, color="#ff2244", lw=0.8, ls="--", alpha=0.5)
    if a1_t: ax_main.scatter(a1_t, a1_s, color="#ffd000", s=60, zorder=5, label="ALERT 1")
    if a2_t: ax_main.scatter(a2_t, a2_s, color="#ff7b00", s=80, zorder=5, marker="^", label="ALERT 2")
    if a3_t: ax_main.scatter(a3_t, a3_s, color="#ff2244", s=120, zorder=5, marker="*", label="CRITICAL")
    ax_main.set_xlim(0, max(times) if times else 1)
    ax_main.set_ylim(0, 105)
    ax_main.set_xlabel("Time (minutes)")
    ax_main.set_ylabel("Fatigue score")
    ax_main.set_title("Fatigue Score Over Time")
    ax_main.legend(loc="upper left", facecolor="#111318",
                   labelcolor="white", fontsize=8, framealpha=0.6)

    # Shade background by zone
    for ylo, yhi, col in [(0,30,"#00e5a0"),(30,60,"#ffd000"),(60,80,"#ff7b00"),(80,105,"#ff2244")]:
        ax_main.axhspan(ylo, yhi, alpha=0.04, color=col)

    # ── PERCLOS ───────────────────────────────────────────────────
    ax_perc.plot(times, perclos, color="#ffd000", lw=1.3)
    ax_perc.fill_between(times, perclos, alpha=0.15, color="#ffd000")
    ax_perc.axhline(30, color="#ff2244", lw=0.8, ls="--", alpha=0.6)
    ax_perc.set_xlabel("Time (minutes)")
    ax_perc.set_ylabel("PERCLOS (%)")
    ax_perc.set_title("PERCLOS — Eyes-Closed %")
    ax_perc.set_ylim(0, 100)

    # ── Blink rate ────────────────────────────────────────────────
    ax_blink.plot(times, blinks, color="#7b9fff", lw=1.3)
    ax_blink.axhline(8,  color="#ff7b00", lw=0.8, ls="--", alpha=0.6, label="Low (<8)")
    ax_blink.axhline(20, color="#00e5a0", lw=0.8, ls="--", alpha=0.6, label="Normal (15-20)")
    ax_blink.set_xlabel("Time (minutes)")
    ax_blink.set_ylabel("Blinks / min")
    ax_blink.set_title("Blink Rate")
    ax_blink.legend(facecolor="#111318", labelcolor="white", fontsize=7, framealpha=0.6)

    # ── EAR trace ─────────────────────────────────────────────────
    ax_ear.plot(times, ears, color="#cc88ff", lw=1.0)
    ax_ear.set_xlabel("Time (minutes)")
    ax_ear.set_ylabel("EAR")
    ax_ear.set_title("Eye Aspect Ratio")

    # ── Summary text ──────────────────────────────────────────────
    ax_sum.set_facecolor("#111318")
    ax_sum.axis("off")

    total_min = max(times) if times else 0
    worst_idx = int(np.argmax(scores))
    best_idx  = int(np.argmin(scores))

    summary = [
        ("Grade",           f"{grade}  —  {gdesc}",    gc),
        ("Total drive",     f"{total_min:.1f} min",     "white"),
        ("Avg fatigue",     f"{avg_score:.0f} / 100",   gc),
        ("Worst moment",    f"{times[worst_idx]:.1f} min  ({_fatigue_label(scores[worst_idx])})", "#ff7b00"),
        ("Best moment",     f"{times[best_idx]:.1f} min  ({_fatigue_label(scores[best_idx])})",  "#00e5a0"),
        ("ALERT 1 / 2",     f"{len(a1_t)} / {len(a2_t)}", "#ffd000"),
        ("CRITICAL",        f"{len(a3_t)}", "#ff2244" if a3_t else "white"),
        ("Avg PERCLOS",     f"{np.mean(perclos):.1f}%", "white"),
        ("Avg blink rate",  f"{np.mean(blinks):.1f} /min", "white"),
    ]

    y = 0.97
    for label, value, color in summary:
        ax_sum.text(0.02, y, f"{label}:", transform=ax_sum.transAxes,
                    color="#8899aa", fontsize=9, va="top")
        ax_sum.text(0.52, y, value, transform=ax_sum.transAxes,
                    color=color, fontsize=9, va="top", fontweight="bold")
        y -= 0.11

    plt.show()


# ── Historical trend report ───────────────────────────────────────
def show_history_report(user_id: str, user_name: str = ""):
    sessions = load_sessions(user_id)
    if not sessions:
        print("[Report] No session history found.")
        return

    dates       = [s["date"] + " " + s["start_time"][:5] for s in sessions][::-1]
    avg_fatigue = [s["avg_fatigue"]    for s in sessions][::-1]
    durations   = [s["total_minutes"]  for s in sessions][::-1]
    criticals   = [s["critical_count"] for s in sessions][::-1]
    worst_mins  = [s["worst_period_min"] for s in sessions][::-1]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), facecolor="#0a0c0f")
    fig.suptitle(f"Drive History — {user_name}", color="white",
                 fontsize=14, fontweight="bold")

    x = range(len(dates))
    short_dates = [d[-5:] for d in dates]  # HH:MM

    for ax in axes.flat:
        ax.set_facecolor("#111318")
        ax.tick_params(colors="#555e70", labelsize=8)
        ax.spines[:].set_color("#1e2430")
        ax.xaxis.label.set_color("#8899aa")
        ax.yaxis.label.set_color("#8899aa")
        ax.title.set_color("#99aabb")

    # Avg fatigue trend
    axes[0,0].plot(x, avg_fatigue, color="#00e5a0", marker="o", ms=5, lw=1.5)
    axes[0,0].fill_between(x, avg_fatigue, alpha=0.15, color="#00e5a0")
    axes[0,0].axhline(30, color="#ffd000", lw=0.7, ls="--", alpha=0.5)
    axes[0,0].axhline(60, color="#ff2244", lw=0.7, ls="--", alpha=0.5)
    axes[0,0].set_xticks(x); axes[0,0].set_xticklabels(short_dates, rotation=30)
    axes[0,0].set_title("Avg Fatigue Score per Session")
    axes[0,0].set_ylim(0, 100)

    # Drive duration
    axes[0,1].bar(x, durations, color="#7b9fff", alpha=0.8)
    axes[0,1].set_xticks(x); axes[0,1].set_xticklabels(short_dates, rotation=30)
    axes[0,1].set_title("Drive Duration (minutes)")

    # CRITICAL count per session
    bar_colors = ["#ff2244" if c > 0 else "#1e2430" for c in criticals]
    axes[1,0].bar(x, criticals, color=bar_colors, alpha=0.9)
    axes[1,0].set_xticks(x); axes[1,0].set_xticklabels(short_dates, rotation=30)
    axes[1,0].set_title("CRITICAL Events per Session")

    # Worst period timing
    axes[1,1].scatter(x, worst_mins, color="#ff7b00", s=80, zorder=5)
    axes[1,1].plot(x, worst_mins, color="#ff7b00", lw=1, ls="--", alpha=0.5)
    axes[1,1].set_xticks(x); axes[1,1].set_xticklabels(short_dates, rotation=30)
    axes[1,1].set_title("Worst Fatigue Moment (minutes into drive)")
    axes[1,1].set_ylabel("minutes")

    plt.tight_layout()
    plt.show()