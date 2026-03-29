"""
report.py — Post-drive report with matplotlib graphs
get_session_figure / get_history_figure return Figure objects for embedding in Tkinter.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from session import load_sessions, load_timeline


def _grade(avg_score, critical):
    if critical > 0:       return "F", "#ff2244", "Dangerous — CRITICAL event occurred"
    if avg_score < 15:     return "A", "#00e5a0", "Excellent — Very safe drive"
    if avg_score < 30:     return "B", "#7fff00", "Good — Minor fatigue detected"
    if avg_score < 50:     return "C", "#ffd000", "Fair — Moderate fatigue"
    if avg_score < 70:     return "D", "#ff7b00", "Poor — Significant fatigue"
    return "F", "#ff2244", "Dangerous — Severe fatigue"

def _fatigue_label(s):
    if s < 20: return "Alert"
    if s < 40: return "Mild"
    if s < 60: return "Moderate"
    if s < 80: return "High"
    return "Severe"

def _ax_style(ax):
    ax.set_facecolor("#111318")
    ax.tick_params(colors="#555e70", labelsize=8)
    for sp in ax.spines.values(): sp.set_color("#1e2430")
    ax.xaxis.label.set_color("#8899aa")
    ax.yaxis.label.set_color("#8899aa")
    ax.title.set_color("#99aabb")


# ── Session figure ────────────────────────────────────────────────
def get_session_figure(session_id: int, user_name: str = "") -> plt.Figure:
    timeline = load_timeline(session_id)
    if not timeline:
        fig, ax = plt.subplots(facecolor="#0a0c0f")
        ax.text(0.5, 0.5, "No data for this session",
                ha="center", va="center", color="white", fontsize=14,
                transform=ax.transAxes)
        ax.axis("off")
        return fig

    sessions = load_sessions_by_id(session_id)
    session  = sessions[0] if sessions else {}

    times   = [s["t"]       for s in timeline]
    scores  = [s["score"]   for s in timeline]
    perclos = [s["perclos"] for s in timeline]
    blinks  = [s["blink"]   for s in timeline]
    alerts  = [s["alert"]   for s in timeline]
    ears    = [s["ear"]     for s in timeline]

    avg_score   = np.mean(scores)
    critical_ct = session.get("critical_count", sum(1 for a in alerts if a == 3))
    grade, gc, gdesc = _grade(avg_score, critical_ct)

    a1_t = [times[i] for i in range(len(alerts)) if alerts[i] == 1]
    a2_t = [times[i] for i in range(len(alerts)) if alerts[i] == 2]
    a3_t = [times[i] for i in range(len(alerts)) if alerts[i] == 3]
    a1_s = [scores[i] for i in range(len(alerts)) if alerts[i] == 1]
    a2_s = [scores[i] for i in range(len(alerts)) if alerts[i] == 2]
    a3_s = [scores[i] for i in range(len(alerts)) if alerts[i] == 3]

    session_name = f"{session.get('date','')} {session.get('start_time','')[:5]}"

    fig = plt.figure(figsize=(13, 8), facecolor="#0a0c0f")
    fig.suptitle(
        f"Drive Report  |  {user_name}  |  {session_name}  |  Grade: {grade}  ({gdesc})",
        color="white", fontsize=11, fontweight="bold", y=0.98
    )
    gs = gridspec.GridSpec(3, 2, figure=fig,
                           hspace=0.48, wspace=0.3,
                           left=0.07, right=0.97, top=0.93, bottom=0.07)

    ax_main  = fig.add_subplot(gs[0, :])
    ax_perc  = fig.add_subplot(gs[1, 0])
    ax_blink = fig.add_subplot(gs[1, 1])
    ax_ear   = fig.add_subplot(gs[2, 0])
    ax_sum   = fig.add_subplot(gs[2, 1])

    for ax in [ax_main, ax_perc, ax_blink, ax_ear]: _ax_style(ax)

    ax_main.plot(times, scores, color="#00e5a0", lw=1.5, label="Fatigue score")
    ax_main.fill_between(times, scores, alpha=0.15, color="#00e5a0")
    ax_main.axhline(30, color="#ffd000", lw=0.8, ls="--", alpha=0.5)
    ax_main.axhline(60, color="#ff7b00", lw=0.8, ls="--", alpha=0.5)
    ax_main.axhline(80, color="#ff2244", lw=0.8, ls="--", alpha=0.5)
    for ylo, yhi, col in [(0,30,"#00e5a0"),(30,60,"#ffd000"),(60,80,"#ff7b00"),(80,105,"#ff2244")]:
        ax_main.axhspan(ylo, yhi, alpha=0.04, color=col)
    if a1_t: ax_main.scatter(a1_t, a1_s, color="#ffd000", s=60, zorder=5, label="ALERT 1")
    if a2_t: ax_main.scatter(a2_t, a2_s, color="#ff7b00", s=80, zorder=5, marker="^", label="ALERT 2")
    if a3_t: ax_main.scatter(a3_t, a3_s, color="#ff2244", s=120, zorder=5, marker="*", label="CRITICAL")
    ax_main.set_xlim(0, max(times) if times else 1)
    ax_main.set_ylim(0, 105)
    ax_main.set_xlabel("Time (minutes)")
    ax_main.set_ylabel("Fatigue score")
    ax_main.set_title("① Fatigue Score Over Time")
    ax_main.legend(loc="upper left", facecolor="#111318", labelcolor="white", fontsize=8, framealpha=0.6)

    ax_perc.plot(times, perclos, color="#ffd000", lw=1.3)
    ax_perc.fill_between(times, perclos, alpha=0.15, color="#ffd000")
    ax_perc.axhline(30, color="#ff2244", lw=0.8, ls="--", alpha=0.6, label="Danger (30%)")
    ax_perc.set_xlabel("Time (minutes)"); ax_perc.set_ylabel("PERCLOS (%)")
    ax_perc.set_title("② PERCLOS"); ax_perc.set_ylim(0, 100)
    ax_perc.legend(facecolor="#111318", labelcolor="white", fontsize=7)

    ax_blink.plot(times, blinks, color="#7b9fff", lw=1.3)
    ax_blink.axhline(8,  color="#ff7b00", lw=0.8, ls="--", alpha=0.6, label="Low (<8)")
    ax_blink.axhline(20, color="#00e5a0", lw=0.8, ls="--", alpha=0.6, label="Normal (15-20)")
    ax_blink.set_xlabel("Time (minutes)"); ax_blink.set_ylabel("Blinks / min")
    ax_blink.set_title("③ Blink Rate")
    ax_blink.legend(facecolor="#111318", labelcolor="white", fontsize=7)

    ax_ear.plot(times, ears, color="#cc88ff", lw=1.0)
    ax_ear.set_xlabel("Time (minutes)"); ax_ear.set_ylabel("EAR")
    ax_ear.set_title("④ Eye Aspect Ratio")

    ax_sum.set_facecolor("#111318"); ax_sum.axis("off")
    total_min = max(times) if times else 0
    worst_idx = int(np.argmax(scores)); best_idx = int(np.argmin(scores))
    summary = [
        ("Grade",          f"{grade}  —  {gdesc}",                          gc),
        ("Session",        session_name,                                     "white"),
        ("Total drive",    f"{total_min:.1f} min",                           "white"),
        ("Avg fatigue",    f"{avg_score:.0f} / 100",                         gc),
        ("Worst moment",   f"{times[worst_idx]:.1f} min  ({_fatigue_label(scores[worst_idx])})", "#ff7b00"),
        ("Best moment",    f"{times[best_idx]:.1f} min  ({_fatigue_label(scores[best_idx])})",  "#00e5a0"),
        ("ALERT 1 / 2",    f"{len(a1_t)} / {len(a2_t)}",                    "#ffd000"),
        ("CRITICAL",       str(len(a3_t)),                                   "#ff2244" if a3_t else "white"),
        ("Avg PERCLOS",    f"{np.mean(perclos):.1f}%",                       "white"),
        ("Avg blink rate", f"{np.mean(blinks):.1f} /min",                    "white"),
    ]
    y = 0.97
    for label, value, color in summary:
        ax_sum.text(0.02, y, f"{label}:", transform=ax_sum.transAxes, color="#8899aa", fontsize=9, va="top")
        ax_sum.text(0.52, y, value, transform=ax_sum.transAxes, color=color, fontsize=9, va="top", fontweight="bold")
        y -= 0.10

    return fig


# ── History figure ────────────────────────────────────────────────
def get_history_figure(user_id: str, user_name: str = "") -> plt.Figure:
    sessions = load_sessions(user_id)
    if not sessions:
        fig, ax = plt.subplots(facecolor="#0a0c0f")
        ax.text(0.5, 0.5, "No session history found",
                ha="center", va="center", color="white", fontsize=14,
                transform=ax.transAxes)
        ax.axis("off")
        return fig

    names       = [f"{s['date']} {s['start_time'][:5]}" for s in sessions][::-1]
    avg_fatigue = [s["avg_fatigue"]      for s in sessions][::-1]
    durations   = [s["total_minutes"]    for s in sessions][::-1]
    criticals   = [s["critical_count"]   for s in sessions][::-1]
    worst_mins  = [s["worst_period_min"] for s in sessions][::-1]
    perclos_avg = [s["perclos_avg"]      for s in sessions][::-1]
    blink_avg   = [s["blink_rate_avg"]   for s in sessions][::-1]
    x = list(range(len(names)))

    overall_avg_fatigue  = np.mean(avg_fatigue)
    overall_avg_duration = np.mean(durations)
    overall_avg_perclos  = np.mean(perclos_avg)
    overall_avg_blink    = np.mean(blink_avg)
    total_criticals      = sum(criticals)
    grade, gc, gdesc     = _grade(overall_avg_fatigue, total_criticals)

    fig = plt.figure(figsize=(13, 8), facecolor="#0a0c0f")
    fig.suptitle(
        f"Drive History  |  {user_name}  |  {len(sessions)} sessions  |  Overall Grade: {grade}  ({gdesc})",
        color="white", fontsize=11, fontweight="bold", y=0.98
    )
    gs = gridspec.GridSpec(3, 2, figure=fig,
                           hspace=0.5, wspace=0.35,
                           left=0.07, right=0.97, top=0.93, bottom=0.07)

    ax_fat   = fig.add_subplot(gs[0, :])
    ax_dur   = fig.add_subplot(gs[1, 0])
    ax_crit  = fig.add_subplot(gs[1, 1])
    ax_worst = fig.add_subplot(gs[2, 0])
    ax_avg   = fig.add_subplot(gs[2, 1])

    for ax in [ax_fat, ax_dur, ax_crit, ax_worst]: _ax_style(ax)
    short = [n[-5:] for n in names]

    ax_fat.plot(x, avg_fatigue, color="#00e5a0", marker="o", ms=5, lw=1.5, label="Avg fatigue")
    ax_fat.fill_between(x, avg_fatigue, alpha=0.15, color="#00e5a0")
    ax_fat.axhline(overall_avg_fatigue, color="#ffd000", lw=1, ls="--",
                   label=f"Overall avg ({overall_avg_fatigue:.0f})")
    ax_fat.set_xticks(x); ax_fat.set_xticklabels(names, rotation=25, ha="right", fontsize=7)
    ax_fat.set_title("① Avg Fatigue Score per Session"); ax_fat.set_ylim(0, 100)
    ax_fat.legend(facecolor="#111318", labelcolor="white", fontsize=8)

    ax_dur.bar(x, durations, color="#7b9fff", alpha=0.8)
    ax_dur.axhline(overall_avg_duration, color="#ffd000", lw=1, ls="--",
                   label=f"Avg ({overall_avg_duration:.0f} min)")
    ax_dur.set_xticks(x); ax_dur.set_xticklabels(short, rotation=25, fontsize=7)
    ax_dur.set_title("② Drive Duration (minutes)")
    ax_dur.legend(facecolor="#111318", labelcolor="white", fontsize=7)

    bar_colors = ["#ff2244" if c > 0 else "#1e3a2a" for c in criticals]
    ax_crit.bar(x, criticals, color=bar_colors, alpha=0.9)
    ax_crit.set_xticks(x); ax_crit.set_xticklabels(short, rotation=25, fontsize=7)
    ax_crit.set_title("③ CRITICAL Events per Session")

    ax_worst.scatter(x, worst_mins, color="#ff7b00", s=80, zorder=5)
    ax_worst.plot(x, worst_mins, color="#ff7b00", lw=1, ls="--", alpha=0.5)
    ax_worst.set_xticks(x); ax_worst.set_xticklabels(short, rotation=25, fontsize=7)
    ax_worst.set_title("④ Worst Moment (minutes into drive)"); ax_worst.set_ylabel("minutes")

    ax_avg.set_facecolor("#111318"); ax_avg.axis("off")
    summary = [
        ("Overall grade",     f"{grade}  —  {gdesc}",                gc),
        ("Total sessions",    str(len(sessions)),                     "white"),
        ("Avg drive time",    f"{overall_avg_duration:.1f} min",      "white"),
        ("Avg fatigue score", f"{overall_avg_fatigue:.0f} / 100",     gc),
        ("Avg PERCLOS",       f"{overall_avg_perclos:.1f}%",          "white"),
        ("Avg blink rate",    f"{overall_avg_blink:.1f} /min",        "white"),
        ("Total CRITICALs",   str(total_criticals),                   "#ff2244" if total_criticals else "white"),
        ("Best session",      names[int(np.argmin(avg_fatigue))],     "#00e5a0"),
        ("Worst session",     names[int(np.argmax(avg_fatigue))],     "#ff7b00"),
    ]
    y = 0.97
    for label, value, color in summary:
        ax_avg.text(0.02, y, f"{label}:", transform=ax_avg.transAxes, color="#8899aa", fontsize=9, va="top")
        ax_avg.text(0.55, y, value, transform=ax_avg.transAxes, color=color, fontsize=9, va="top", fontweight="bold")
        y -= 0.11

    return fig


# ── Helper ────────────────────────────────────────────────────────
def load_sessions_by_id(session_id: int) -> list:
    import sqlite3, os
    DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")
    con = sqlite3.connect(DB_PATH)
    row = con.execute("""
        SELECT session_id, date, start_time, total_minutes,
               avg_fatigue, worst_period_min, best_period_min,
               alert_1_count, alert_2_count, critical_count,
               perclos_avg, blink_rate_avg
        FROM sessions WHERE session_id=?
    """, (session_id,)).fetchone()
    con.close()
    if not row: return []
    keys = ["session_id","date","start_time","total_minutes",
            "avg_fatigue","worst_period_min","best_period_min",
            "alert_1_count","alert_2_count","critical_count",
            "perclos_avg","blink_rate_avg"]
    return [dict(zip(keys, row))]