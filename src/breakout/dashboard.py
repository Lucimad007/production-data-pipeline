"""Breakout dashboard: a creator growth intelligence product surface."""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from breakout.config import PROJECT_ROOT, get_settings
from breakout.pipeline import bronze_counts, latest_snapshot, quota_status
from breakout.storage import Lakehouse

PAPER = "#F4F1E8"
INK = "#141414"
MUTED = "#7C776B"
ACCENT = "#C8FF3D"
CORAL = "#FF5A36"
GREEN = "#1E7A46"
BLUE = "#3355FF"
LINE = "rgba(20,20,20,0.12)"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LABELS = {"breakout": "Breakout", "typical": "Typical", "underperformer": "Underperformer"}
COLORS = {"breakout": GREEN, "typical": "#B9B3A6", "underperformer": CORAL}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
  --paper: {PAPER};
  --ink: {INK};
  --muted: {MUTED};
  --accent: {ACCENT};
  --line: {LINE};
}}
.stApp {{ background: var(--paper); color: var(--ink); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] {{ right: 1rem; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1240px; }}
h1, h2, h3 {{ font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.035em; color: var(--ink); }}
p, li, div {{ font-family: 'Inter', sans-serif; }}
section[data-testid="stSidebar"] {{ background: #EDE9DE; border-right: 1px solid var(--line); }}
section[data-testid="stSidebar"] .block-container {{ padding-top: 2rem; }}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{ color: var(--ink) !important; }}
section[data-testid="stSidebar"] .stButton button,
section[data-testid="stSidebar"] .stButton button p,
section[data-testid="stSidebar"] .stButton button span {{ background: var(--ink); color: var(--paper) !important; border: 0; border-radius: 0; font-family: 'IBM Plex Mono', monospace; font-size: .72rem; }}
section[data-testid="stSidebar"] [data-testid="stLinkButton"] a {{ background: transparent; color: var(--ink); border: 1px solid var(--ink); border-radius: 0; font-family: 'IBM Plex Mono', monospace; font-size: .72rem; }}
[data-testid="stToolbar"] {{ display: none; }}
#MainMenu {{ visibility: hidden; }}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child > div {{
  background-color: transparent !important;
  border-color: var(--muted) !important;
}}
section[data-testid="stSidebar"] [role="radiogroup"] > div[data-selected="true"] label[data-testid="stRadioOption"] > div > div:first-child > div {{
  background-color: var(--accent) !important;
  border-color: var(--ink) !important;
}}
.brand {{ font-family: 'Space Grotesk', sans-serif; font-size: 1.55rem; font-weight: 700; letter-spacing: -0.05em; }}
.brand span {{ color: {GREEN}; }}
.side-sub {{ color: var(--muted); font-size: .78rem; margin-top: -.2rem; margin-bottom: 1.4rem; }}
.eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: .68rem; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }}
.hero h1 {{ font-size: clamp(2.2rem, 4vw, 3.6rem); line-height: .98; margin: .35rem 0 .55rem 0; }}
.hero p {{ font-size: 1.02rem; color: #4E4A42; max-width: 720px; margin: 0; }}
.hero {{ padding-bottom: 1.1rem; border-bottom: 1px solid var(--line); margin-bottom: 1.2rem; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 10px; margin: .4rem 0 .8rem 0; }}
.metric-card {{ border: 1px solid var(--line); background: rgba(255,255,255,.35); padding: .9rem .95rem .8rem .95rem; min-height: 108px; }}
.metric-label {{ font-family: 'IBM Plex Mono', monospace; font-size: .6rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); line-height: 1.2; }}
.metric-value {{ font-family: 'Space Grotesk', sans-serif; font-size: 1.55rem; font-weight: 600; line-height: 1.05; margin-top: .4rem; white-space: nowrap; }}
.metric-note {{ font-size: .72rem; color: var(--muted); margin-top: .25rem; }}
.rank-row {{ display: flex; align-items: center; gap: .7rem; padding: .55rem 0; border-bottom: 1px solid var(--line); }}
.rank-num {{ font-family: 'IBM Plex Mono', monospace; font-size: .7rem; color: var(--muted); width: 1.4rem; }}
.rank-body {{ flex: 1; min-width: 0; }}
.rank-title {{ font-size: .84rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.rank-meta {{ font-size: .68rem; color: var(--muted); margin-top: .1rem; }}
.rank-score {{ font-family: 'IBM Plex Mono', monospace; font-size: .82rem; color: {GREEN}; }}
.callout {{ border-left: 3px solid {GREEN}; background: rgba(30,122,70,.07); padding: .8rem 1rem; font-size: .86rem; line-height: 1.45; margin: .6rem 0 1rem 0; }}
.callout b {{ font-family: 'Space Grotesk', sans-serif; }}
.quote {{ border: 1px solid var(--line); padding: .8rem .9rem; margin-bottom: .55rem; background: rgba(255,255,255,.3); }}
.quote-text {{ font-size: .84rem; line-height: 1.45; }}
.quote-meta {{ font-family: 'IBM Plex Mono', monospace; font-size: .62rem; color: var(--muted); margin-top: .4rem; }}
.check-row {{ display: flex; align-items: center; gap: .7rem; padding: .55rem 0; border-bottom: 1px solid var(--line); font-size: .82rem; }}
.check-status {{ font-family: 'IBM Plex Mono', monospace; font-size: .62rem; letter-spacing: .08em; padding: .18rem .38rem; border: 1px solid var(--line); }}
.check-pass {{ color: {GREEN}; border-color: rgba(30,122,70,.35); background: rgba(30,122,70,.08); }}
.check-fail {{ color: {CORAL}; border-color: rgba(255,90,54,.35); background: rgba(255,90,54,.08); }}
.check-name {{ flex: 1; }}
.check-observed {{ font-family: 'IBM Plex Mono', monospace; font-size: .68rem; color: var(--muted); }}
.section-title {{ font-family: 'Space Grotesk', sans-serif; font-size: 1.05rem; font-weight: 600; margin: 1.4rem 0 .5rem 0; }}
.footer {{ margin-top: 2.4rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .7rem; font-family: 'IBM Plex Mono', monospace; }}
div[data-testid="stMetric"] {{ border: 1px solid var(--line); padding: .7rem .8rem; background: rgba(255,255,255,.3); }}
</style>
"""


# -- data ------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def query_df(sql: str) -> pd.DataFrame:
    with Lakehouse() as lake:
        return lake.query_df(sql)


@st.cache_data(ttl=60, show_spinner=False)
def counts() -> dict[str, int]:
    return bronze_counts(get_settings())


@st.cache_data(ttl=60, show_spinner=False)
def load_core() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    overview = query_df("select * from lake.gold.mart_channel_overview")
    videos = query_df("select * from lake.gold.mart_video_performance")
    topics = query_df("select * from lake.gold.mart_topic_performance")
    timing = query_df("select * from lake.gold.mart_publish_timing")
    return overview, videos, topics, timing


@st.cache_data(ttl=60, show_spinner=False)
def load_history(video_id: str) -> pd.DataFrame:
    safe = video_id.replace("'", "''")
    return query_df(
        f"""
        select snapshot_at, view_count, delta_views, hours_since_previous, views_per_hour
        from lake.gold.mart_video_snapshots
        where video_id = '{safe}'
        order by snapshot_at
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_comments(video_id: str) -> pd.DataFrame:
    safe = video_id.replace("'", "''")
    return query_df(
        f"""
        select text, like_count, published_at
        from lake.silver.stg_comments
        where video_id = '{safe}'
        order by like_count desc nulls last
        limit 5
        """
    )


# -- formatting ------------------------------------------------------------


def human(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    number = float(value)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= threshold:
            return f"{number / threshold:.1f}{suffix}".replace(".0", "")
    return f"{number:,.0f}"


def pct(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def score(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):+.2f}"


def short_date(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    timestamp = pd.Timestamp(value)
    return str(timestamp.strftime("%b %d, %Y"))


def safe(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return html.escape(str(value))


def apply_theme(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK, size=12),
        margin=dict(l=8, r=8, t=18, b=8),
        hoverlabel=dict(bgcolor=INK, font_color=PAPER, bordercolor=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE, tickfont=dict(size=11))
    fig.update_yaxes(gridcolor=LINE, zeroline=False, tickfont=dict(size=11))
    return fig


# -- UI pieces -------------------------------------------------------------


def _metric_html(label: str, value: str, note: str = "") -> str:
    return (
        '<div class="metric-card">'
        f'<div class="metric-label">{safe(label)}</div>'
        f'<div class="metric-value">{safe(value)}</div>'
        f'<div class="metric-note">{safe(note)}</div>'
        "</div>"
    )


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(_metric_html(label, value, note), unsafe_allow_html=True)


def metric_row(cards: list[tuple[str, str, str]]) -> None:
    body = "".join(_metric_html(*card) for card in cards)
    st.markdown(f'<div class="metric-grid">{body}</div>', unsafe_allow_html=True)


def hero(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">{safe(eyebrow)}</div>
          <h1>{safe(title)}</h1>
          <p>{safe(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def callout(text: str) -> None:
    st.markdown(f'<div class="callout">{text}</div>', unsafe_allow_html=True)


def rank_list(frame: pd.DataFrame, value_column: str, meta_columns: list[str], limit: int = 6) -> None:
    for index, (_, row) in enumerate(frame.head(limit).iterrows(), start=1):
        meta = " · ".join(safe(row[column]) for column in meta_columns if column in row)
        st.markdown(
            f"""
            <div class="rank-row">
              <div class="rank-num">{index:02d}</div>
              <div class="rank-body">
                <div class="rank-title">{safe(row['title'])}</div>
                <div class="rank-meta">{meta}</div>
              </div>
              <div class="rank-score">{safe(row[value_column])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# -- pages -----------------------------------------------------------------


def render_overview(overview: pd.DataFrame, videos: pd.DataFrame, topics: pd.DataFrame) -> None:
    channel = overview.iloc[0]
    total = len(videos)
    breakout_rate = (videos["performance_label"] == "breakout").mean()
    median_vpd = videos["views_per_day"].median()
    median_engagement = videos["engagement_rate"].median()
    median_score = videos["breakout_score"].median()

    hero(
        f"Creator intelligence · snapshot {short_date(channel['latest_video_snapshot_at'])}",
        "What broke out?",
        f"Age-adjusted performance for {total:,} recent uploads from {channel['title']}. "
        "The score compares each video with the channel's own baseline for its age.",
    )

    metric_row(
        [
            ("Videos analyzed", f"{total:,}", "newest uploads"),
            ("Breakout rate", pct(breakout_rate), "score ≥ 2.0"),
            ("Median views / day", human(median_vpd), "age-adjusted"),
            ("Median engagement", pct(median_engagement), "(likes + comments) / views"),
            ("Median breakout score", score(median_score), "channel baseline = 0"),
        ]
    )

    left, right = st.columns([1.65, 1])
    with left:
        st.markdown('<div class="section-title">Performance vs age</div>', unsafe_allow_html=True)
        plot = videos[videos["views_per_day"] > 0].copy()
        fig = px.scatter(
            plot,
            x="age_days",
            y="views_per_day",
            color="performance_label",
            color_discrete_map=COLORS,
            hover_name="title",
            hover_data={
                "topic": True,
                "view_count": ":,.0f",
                "breakout_score": ":.2f",
                "age_days": True,
                "views_per_day": ":,.0f",
            },
            labels={
                "age_days": "Days since publish",
                "views_per_day": "Views per day (log)",
                "performance_label": "",
            },
            log_y=True,
        )
        fig.update_traces(marker=dict(size=9, line=dict(width=0), opacity=0.82))
        fig.add_hline(
            y=median_vpd,
            line_dash="dot",
            line_color=MUTED,
            annotation_text="channel median",
            annotation_font_color=MUTED,
        )
        fig.for_each_trace(lambda trace: trace.update(name=LABELS.get(trace.name, trace.name)))
        st.plotly_chart(apply_theme(fig, 430), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown('<div class="section-title">Top breakouts</div>', unsafe_allow_html=True)
        top = videos.nlargest(6, "breakout_score").copy()
        top["score"] = top["breakout_score"].map(score)
        top["meta"] = top.apply(
            lambda row: f"{row['topic']} · {int(row['age_days'])}d · {human(row['view_count'])} views",
            axis=1,
        )
        for index, (_, row) in enumerate(top.iterrows(), start=1):
            st.markdown(
                f"""
                <div class="rank-row">
                  <div class="rank-num">{index:02d}</div>
                  <div class="rank-body">
                    <div class="rank-title">{safe(row['title'])}</div>
                    <div class="rank-meta">{safe(row['meta'])}</div>
                  </div>
                  <div class="rank-score">{safe(row['score'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not topics.empty:
        best_score = topics.sort_values("median_breakout_score", ascending=False).iloc[0]
        best_rate = topics.sort_values("breakout_rate", ascending=False).iloc[0]
        callout(
            f"<b>Signal:</b> <i>{safe(best_score['topic'])}</i> has the highest median breakout score "
            f"({score(best_score['median_breakout_score'])}) across {int(best_score['videos'])} videos. "
            f"<i>{safe(best_rate['topic'])}</i> has the highest breakout rate "
            f"({pct(best_rate['breakout_rate'])}, n={int(best_rate['videos'])}). "
            "These are associations, not causal claims."
        )

    st.markdown('<div class="section-title">Breakout leaderboard</div>', unsafe_allow_html=True)
    leaderboard = videos.nlargest(20, "breakout_score")[
        [
            "title",
            "topic",
            "age_days",
            "view_count",
            "views_per_day",
            "engagement_rate",
            "breakout_score",
            "performance_label",
        ]
    ].copy()
    leaderboard.columns = [
        "Video",
        "Topic",
        "Age (days)",
        "Views",
        "Views / day",
        "Engagement",
        "Score",
        "Label",
    ]
    st.dataframe(
        leaderboard,
        hide_index=True,
        width="stretch",
        column_config={
            "Views": st.column_config.NumberColumn(format="%d"),
            "Views / day": st.column_config.NumberColumn(format="%.0f"),
            "Engagement": st.column_config.NumberColumn(format="percent"),
            "Score": st.column_config.NumberColumn(format="%+.2f"),
            "Age (days)": st.column_config.NumberColumn(format="%d"),
        },
    )

    st.caption(
        f"Channel: {channel['title']} · {human(channel['subscriber_count'])} subscribers · "
        f"{human(channel['channel_view_count'])} lifetime views · snapshot data, not live."
    )


def render_video(videos: pd.DataFrame) -> None:
    hero(
        "Video deep dive",
        "Why did this one work?",
        "Pick a video to compare it with the channel baseline, inspect its snapshot history, and read what viewers said.",
    )

    options = videos.nlargest(120, "breakout_score").copy()
    options["label"] = options.apply(
        lambda row: f"{row['title'][:78]}  ·  {score(row['breakout_score'])}", axis=1
    )
    selected_label = st.selectbox("Choose a video", options["label"].tolist(), label_visibility="collapsed")
    selected = options[options["label"] == selected_label].iloc[0]
    video_id = str(selected["video_id"])

    st.markdown(
        f"""
        <div style="margin: .2rem 0 .9rem 0;">
          <div class="eyebrow">{safe(selected['topic'])} · published {short_date(selected['published_at'])} · {int(selected['age_days'])} days old</div>
          <h2 style="margin:.25rem 0 .2rem 0;">{safe(selected['title'])}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_row(
        [
            ("Views", human(selected["view_count"]), "lifetime"),
            ("Views / day", human(selected["views_per_day"]), "age-adjusted"),
            ("Engagement", pct(selected["engagement_rate"]), "likes + comments / views"),
            ("Breakout score", score(selected["breakout_score"]), str(selected["performance_label"])),
            ("Channel rank", f"#{int(selected['breakout_rank'])}", "by breakout score"),
        ]
    )

    left, right = st.columns([1.6, 1])
    with left:
        st.markdown('<div class="section-title">Snapshot history</div>', unsafe_allow_html=True)
        history = load_history(video_id)
        values = history["view_count"].dropna() if not history.empty else pd.Series(dtype=float)
        span = float(values.max() - values.min()) if len(values) > 1 else 0.0
        scale = float(values.max()) if len(values) else 0.0
        meaningful = len(values) > 1 and span > max(scale * 0.002, 10)
        if meaningful:
            fig = px.line(
                history,
                x="snapshot_at",
                y="view_count",
                markers=True,
                labels={"snapshot_at": "", "view_count": "Views"},
            )
            fig.update_traces(line=dict(color=GREEN, width=2), marker=dict(size=5, color=GREEN))
            st.plotly_chart(apply_theme(fig, 330), width="stretch", config={"displayModeBar": False})
        else:
            if len(values) > 1:
                first = pd.Timestamp(history["snapshot_at"].min())
                last = pd.Timestamp(history["snapshot_at"].max())
                minutes = (last - first).total_seconds() / 60
                st.info(
                    f"The two snapshots are only {minutes:.0f} minutes apart, so a line would exaggerate noise. "
                    "The next daily run will add a meaningful interval."
                )
            else:
                st.info(
                    "Only one snapshot so far. Velocity and acceleration appear after the next daily run. "
                    "The public API cannot reconstruct historical view counts."
                )
            fig = go.Figure(
                go.Indicator(
                    mode="number",
                    value=float(selected["view_count"] or 0),
                    number={
                        "font": {"family": "Space Grotesk", "color": INK},
                        "valueformat": ",.0f",
                    },
                )
            )
            st.plotly_chart(apply_theme(fig, 220), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown('<div class="section-title">Percentile vs channel</div>', unsafe_allow_html=True)
        percentile = pd.DataFrame(
            {
                "metric": ["Views / day", "Engagement", "Breakout score"],
                "percentile": [
                    (videos["views_per_day"] < selected["views_per_day"]).mean() * 100,
                    (videos["engagement_rate"] < selected["engagement_rate"]).mean() * 100,
                    (videos["breakout_score"] < selected["breakout_score"]).mean() * 100,
                ],
            }
        )
        fig = px.bar(
            percentile,
            x="percentile",
            y="metric",
            orientation="h",
            range_x=[0, 100],
            labels={"percentile": "Percentile", "metric": ""},
        )
        fig.update_traces(marker_color=GREEN, width=0.55)
        fig.add_vline(x=50, line_dash="dot", line_color=MUTED)
        st.plotly_chart(apply_theme(fig, 260), width="stretch", config={"displayModeBar": False})

    st.markdown('<div class="section-title">What viewers said</div>', unsafe_allow_html=True)
    comments = load_comments(video_id)
    if comments.empty:
        st.caption("No comments were collected for this video. The pipeline only fetches comments for the top videos.")
    else:
        for _, comment in comments.iterrows():
            st.markdown(
                f"""
                <div class="quote">
                  <div class="quote-text">{safe(comment['text'])}</div>
                  <div class="quote-meta">{human(comment['like_count'])} likes · {short_date(comment['published_at'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    pct_vpd = (videos["views_per_day"] < selected["views_per_day"]).mean() * 100
    pct_eng = (videos["engagement_rate"] < selected["engagement_rate"]).mean() * 100
    callout(
        f"<b>Read:</b> this video is <i>{safe(selected['performance_label'])}</i> for its age bucket. "
        f"It sits at the {pct_vpd:.0f}th percentile for views/day and the {pct_eng:.0f}th percentile "
        f"for engagement. Topic: <i>{safe(selected['topic'])}</i>. Treat this as a signal to investigate, "
        "not proof of cause."
    )
    st.link_button("Open on YouTube", f"https://youtu.be/{video_id}")


def render_topics(topics: pd.DataFrame) -> None:
    hero(
        "Topic performance",
        "Where the signal is.",
        "Topics are keyword-derived from titles and descriptions. Small cells are suppressed below three videos.",
    )
    if topics.empty:
        st.info("No topic cells with at least three videos yet.")
        return

    left, right = st.columns([1.55, 1])
    with left:
        st.markdown('<div class="section-title">Volume vs breakout</div>', unsafe_allow_html=True)
        fig = px.scatter(
            topics,
            x="videos",
            y="median_breakout_score",
            size="total_views",
            color="breakout_rate",
            text="topic",
            color_continuous_scale=["#E8E3D6", GREEN],
            hover_data={
                "videos": True,
                "total_views": ":,.0f",
                "median_views_per_day": ":,.0f",
                "breakout_rate": ":.1%",
            },
            labels={
                "videos": "Videos in topic",
                "median_breakout_score": "Median breakout score",
                "breakout_rate": "Breakout rate",
            },
            size_max=46,
        )
        fig.update_traces(textposition="top center", textfont=dict(size=10, color=INK))
        fig.add_hline(y=0, line_dash="dot", line_color=MUTED)
        fig.add_vline(x=topics["videos"].median(), line_dash="dot", line_color=MUTED)
        st.plotly_chart(apply_theme(fig, 430), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown('<div class="section-title">Best topics</div>', unsafe_allow_html=True)
        best = topics.sort_values("median_breakout_score", ascending=False).head(7)
        for index, (_, row) in enumerate(best.iterrows(), start=1):
            st.markdown(
                f"""
                <div class="rank-row">
                  <div class="rank-num">{index:02d}</div>
                  <div class="rank-body">
                    <div class="rank-title">{safe(row['topic'])}</div>
                    <div class="rank-meta">{int(row['videos'])} videos · {pct(row['breakout_rate'])} breakout rate</div>
                  </div>
                  <div class="rank-score">{score(row['median_breakout_score'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    best = topics.sort_values("median_breakout_score", ascending=False).iloc[0]
    best_rate = topics.sort_values("breakout_rate", ascending=False).iloc[0]
    callout(
        f"<b>Signal:</b> <i>{safe(best['topic'])}</i> leads on median breakout score "
        f"({score(best['median_breakout_score'])}) with {int(best['videos'])} videos. "
        f"The highest breakout rate belongs to <i>{safe(best_rate['topic'])}</i> "
        f"({pct(best_rate['breakout_rate'])}, n={int(best_rate['videos'])}). "
        "Topic labels are rules, not an LLM; treat them as a first pass."
    )

    table = topics.sort_values("median_breakout_score", ascending=False).copy()
    table.columns = [
        "Channel",
        "Topic",
        "Videos",
        "Total views",
        "Median views / day",
        "Median score",
        "Avg engagement",
        "Breakout rate",
    ]
    st.dataframe(
        table.drop(columns=["Channel"]),
        hide_index=True,
        width="stretch",
        column_config={
            "Total views": st.column_config.NumberColumn(format="%d"),
            "Median views / day": st.column_config.NumberColumn(format="%.0f"),
            "Median score": st.column_config.NumberColumn(format="%+.2f"),
            "Avg engagement": st.column_config.NumberColumn(format="percent"),
            "Breakout rate": st.column_config.NumberColumn(format="percent"),
        },
    )


def render_timing(timing: pd.DataFrame) -> None:
    hero(
        "Publish timing",
        "When to publish.",
        "Median breakout score by publish day and hour. Only cells with at least three videos are shown. Observational, not causal.",
    )
    if timing.empty:
        st.info("No timing cells with at least three videos yet.")
        return

    pivot_score = (
        timing.pivot(index="publish_dow", columns="publish_hour", values="median_breakout_score")
        .reindex(index=DAYS, columns=range(24))
    )
    pivot_n = (
        timing.pivot(index="publish_dow", columns="publish_hour", values="videos")
        .reindex(index=DAYS, columns=range(24))
    )
    text = pivot_score.copy().astype(object)
    for day in DAYS:
        for hour in range(24):
            value = pivot_score.loc[day, hour]
            text.loc[day, hour] = "" if pd.isna(value) else f"{value:+.1f}"

    fig = go.Figure(
        go.Heatmap(
            z=pivot_score.values,
            x=list(range(24)),
            y=DAYS,
            colorscale=[[0, "#F2A18E"], [0.5, "#E8E3D6"], [1, "#7CC47F"]],
            zmid=0,
            text=text.values,
            texttemplate="%{text}",
            textfont=dict(size=9, family="IBM Plex Mono", color=INK),
            customdata=pivot_n.values,
            hovertemplate="%{y} %{x}:00<br>score %{z:+.2f}<br>videos %{customdata}<extra></extra>",
            colorbar=dict(title="score", thickness=10, len=0.6),
        )
    )
    fig.update_layout(
        height=460,
        xaxis=dict(title="Hour of day (UTC)", tickmode="array", tickvals=list(range(0, 24, 2))),
        yaxis=dict(title="", autorange="reversed"),
    )
    st.plotly_chart(apply_theme(fig, 460), width="stretch", config={"displayModeBar": False})

    best = timing.sort_values("median_breakout_score", ascending=False).iloc[0]
    callout(
        f"<b>Signal:</b> {safe(best['publish_dow'])} at {int(best['publish_hour']):02d}:00 UTC has the highest "
        f"median breakout score ({score(best['median_breakout_score'])}) across {int(best['videos'])} videos. "
        "Publish time is correlated with topic and audience timezone; do not read it as a causal lever."
    )

    top = timing.sort_values("median_breakout_score", ascending=False).head(10).copy()
    top["cell"] = top.apply(
        lambda row: f"{row['publish_dow']} {int(row['publish_hour']):02d}:00", axis=1
    )
    top = top[["cell", "videos", "median_breakout_score", "breakout_rate", "median_views_per_day"]]
    top.columns = ["Cell (UTC)", "Videos", "Median score", "Breakout rate", "Median views / day"]
    st.dataframe(
        top,
        hide_index=True,
        width="stretch",
        column_config={
            "Median score": st.column_config.NumberColumn(format="%+.2f"),
            "Breakout rate": st.column_config.NumberColumn(format="percent"),
            "Median views / day": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def dbt_summary() -> dict[str, Any] | None:
    path = PROJECT_ROOT / "dbt_project" / "target" / "run_results.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    results = payload.get("results", [])
    passed = sum(1 for result in results if result.get("status") in {"success", "pass"})
    failed = sum(1 for result in results if result.get("status") in {"error", "fail"})
    return {
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "elapsed": payload.get("elapsed_time"),
        "generated_at": payload.get("generated_at"),
    }


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def render_health() -> None:
    settings = get_settings()
    bronze = counts()
    quota = quota_status(settings)
    latest = latest_snapshot(settings)
    latest_age = None
    if latest:
        latest_age = (datetime.now(UTC) - pd.Timestamp(latest).to_pydatetime().replace(tzinfo=UTC)).total_seconds() / 3600

    hero(
        "Pipeline health",
        "Is the pipeline trustworthy?",
        "The checks below are computed live from the lakehouse. The dashboard is only as good as the data underneath it.",
    )

    metric_row(
        [
            ("Bronze videos", f"{bronze['videos']:,}", "current metadata"),
            ("Snapshots", f"{bronze['video_snapshots']:,}", "append-only"),
            ("Comments", f"{bronze['comments']:,}", "hashed authors"),
            (
                "Freshness",
                f"{latest_age:.1f}h" if latest_age is not None else "—",
                "since latest snapshot",
            ),
            ("Quota", f"{quota.used}/{quota.budget}", "units today"),
        ]
    )

    st.markdown('<div class="section-title">Live checks</div>', unsafe_allow_html=True)
    checks: list[tuple[str, str, str, bool]] = []
    checks.append(("Bronze videos present", f"{bronze['videos']:,}", "> 0", bronze["videos"] > 0))
    checks.append(("Snapshots present", f"{bronze['video_snapshots']:,}", "> 0", bronze["video_snapshots"] > 0))
    checks.append(("Comments present", f"{bronze['comments']:,}", "> 0", bronze["comments"] > 0))
    checks.append(
        (
            "Freshness under 24h",
            f"{latest_age:.1f}h" if latest_age is not None else "—",
            "< 24h",
            latest_age is not None and latest_age < 24,
        )
    )
    checks.append(
        (
            "Quota under budget",
            f"{quota.used}/{quota.budget}",
            "≤ budget",
            quota.used <= quota.budget,
        )
    )

    try:
        duplicates = query_df(
            "select count(*) - count(distinct video_id) as duplicates from lake.gold.mart_video_performance"
        ).iloc[0]["duplicates"]
        checks.append(("Mart keys unique", f"{int(duplicates)} duplicates", "0", int(duplicates) == 0))
        null_scores = query_df(
            "select count(*) as nulls from lake.gold.mart_video_performance where breakout_score is null"
        ).iloc[0]["nulls"]
        checks.append(("Breakout scores present", f"{int(null_scores)} nulls", "0", int(null_scores) == 0))
        coverage = query_df(
            """
            select
              (select count(*) from lake.gold.mart_video_performance) as mart_rows,
              (select count(*) from lake.bronze.videos) as bronze_rows
            """
        ).iloc[0]
        checks.append(
            (
                "Mart coverage",
                f"{int(coverage['mart_rows']):,}/{int(coverage['bronze_rows']):,}",
                "≈ 100%",
                int(coverage["bronze_rows"]) > 0
                and int(coverage["mart_rows"]) / int(coverage["bronze_rows"]) > 0.95,
            )
        )
    except Exception as exc:  # noqa: BLE001 - health page must render even when marts are missing
        checks.append(("Mart checks available", type(exc).__name__, "no error", False))

    for name, observed, threshold, passed in checks:
        status = "PASS" if passed else "FAIL"
        css = "check-pass" if passed else "check-fail"
        st.markdown(
            f"""
            <div class="check-row">
              <span class="check-status {css}">{status}</span>
              <span class="check-name">{safe(name)}</span>
              <span class="check-observed">{safe(observed)} · target {safe(threshold)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    left, right = st.columns(2)
    with left:
        st.markdown('<div class="section-title">Last dbt build</div>', unsafe_allow_html=True)
        summary = dbt_summary()
        if summary is None:
            st.caption("No `run_results.json` found. Run `uv run breakout build` to generate one.")
        else:
            elapsed = float(summary.get("elapsed") or 0)
            note = f"{int(summary['failed'])} failed · {elapsed:.1f}s"
            if summary.get("generated_at"):
                note += f" · {summary['generated_at']}"
            st.markdown(
                f"""
                <div class="metric-card">
                  <div class="metric-label">dbt results</div>
                  <div class="metric-value">{int(summary['passed'])}/{int(summary['total'])}</div>
                  <div class="metric-note">{safe(note)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with right:
        st.markdown('<div class="section-title">Local storage</div>', unsafe_allow_html=True)
        lake_size = directory_size(settings.ducklake_data)
        raw_size = directory_size(settings.raw_dir)
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="metric-label">DuckLake + raw landing</div>
              <div class="metric-value">{lake_size / 1_048_576:.1f} MB</div>
              <div class="metric-note">raw JSON {raw_size / 1_048_576:.1f} MB · compute $0 locally</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Runbook: the three failures that matter"):
        st.markdown(
            """
            **1. Quota exhausted.** The ledger refuses calls above the daily budget. Wait for the UTC reset,
            reduce `--max-videos` or `comment_videos`, then re-run. The raw landing means no data is lost.

            **2. dbt test failure.** Open `dbt_project/target/run_results.json`, find the failing node, and query
            the model directly. Fix the contract or the model; do not silence a blocking test.

            **3. Schema drift.** A new or missing API field should fail the Pydantic contract. The raw envelope
            is preserved, so update the contract and replay bronze without calling YouTube again.
            """
        )

    st.caption(
        "Health checks are computed from the local snapshot. In production these would be scheduled, "
        "alerted, and tied to an SLO."
    )


# -- app -------------------------------------------------------------------


def sidebar(overview: pd.DataFrame | None) -> str:
    with st.sidebar:
        st.markdown('<div class="brand">BREAK<span>OUT</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="side-sub">creator intelligence</div>', unsafe_allow_html=True)
        page = st.radio(
            "Navigate",
            ["Overview", "Video", "Topics", "Timing", "Health"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        if overview is not None and not overview.empty:
            channel = overview.iloc[0]
            st.caption(f"{channel['title']}")
            st.caption(f"{human(channel['subscriber_count'])} subscribers · {human(channel['channel_view_count'])} views")
            st.caption(f"Snapshot {short_date(channel['latest_video_snapshot_at'])}")
        else:
            st.caption("No snapshot loaded")
        if st.button("Refresh data", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.link_button(
            "View source",
            "https://github.com/Lucimad007/production-data-pipeline",
            width="stretch",
        )
        st.markdown(
            '<div class="footer">DuckDB · DuckLake · dbt · Dagster<br/>YouTube Data API · snapshot data</div>',
            unsafe_allow_html=True,
        )
    return str(page)


def render_empty(error: Exception | None = None) -> None:
    hero(
        "Creator intelligence",
        "No snapshot yet.",
        "Run the ingestion and dbt build, then refresh this page. The dashboard reads the local lakehouse, not a mock.",
    )
    st.code(
        "uv run breakout ingest --channel AlexHormozi --max-videos 500\n"
        "uv run breakout build\n"
        "uv run breakout dashboard",
        language="powershell",
    )
    if error is not None:
        with st.expander("Why is the page empty?"):
            st.code(f"{type(error).__name__}: {error}", language="text")


def main() -> None:
    st.set_page_config(page_title="Breakout · creator intelligence", page_icon="◼", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)

    overview: pd.DataFrame | None = None
    videos: pd.DataFrame | None = None
    topics: pd.DataFrame | None = None
    timing: pd.DataFrame | None = None
    error: Exception | None = None
    try:
        overview, videos, topics, timing = load_core()
    except Exception as exc:  # noqa: BLE001 - show a useful onboarding state
        error = exc

    page = sidebar(overview)
    if overview is None or videos is None or topics is None or timing is None:
        render_empty(error)
        return

    if page == "Overview":
        render_overview(overview, videos, topics)
    elif page == "Video":
        render_video(videos)
    elif page == "Topics":
        render_topics(topics)
    elif page == "Timing":
        render_timing(timing)
    else:
        render_health()

    st.markdown(
        '<div class="footer">Breakout is a portfolio data product. Metrics are age-adjusted and observational. '
        "Source: YouTube Data API. Snapshot data, not live.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
