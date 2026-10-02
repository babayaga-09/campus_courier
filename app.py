"""
app.py -- CampusCourier live command dashboard.   Run:  streamlit run app.py
Theme tokens live in .streamlit/config.toml; this file adds the component CSS.
"""

import json
import os
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import agent
import memory
import wandb_log
import world

st.set_page_config(page_title="CampusCourier Command", layout="wide")

ROBOT_COLORS = {"CB-1": "#E9B44C", "CB-2": "#58C4DD", "CB-3": "#B8D86B"}
STEP_KIND = {  # flag -> (pill label, pill class)
    "ok": ("Tool", "neutral"), "sat": ("Z3 SAT", "sat"), "unsat": ("Z3 UNSAT", "unsat"),
    "blocked": ("Gate blocked", "blocked"), "syntax": ("Schema error", "syntax"), "finish": ("Finish", "commit"),
}
PRESETS = {
    "Routine dispatch": "Get 2 projectors and a lab kit to Studio 3 before the 2pm class.",
    "Overload": "Send 3 projectors and the whiteboard to Studio 3, fast.",
    "Low-battery trap": "Use Pixel to carry a lab kit to the Library.",
}
# Demo mode: show only what the presentation brief asks for (GUI, input, one working
# algorithm, the verification layer). Set True to show the task log, the stock table and
# the layer roadmap again. Nothing is removed, only hidden.
SHOW_FULL = True
LAYERS = [
    ("LLM coordinator + Z3 safety filter", "live"),
    ("A* routing", "live"),
    ("SQLite memory", "live"),
    ("Live dashboard", "live"),
    ("HMM localisation", "next"),
    ("Adaptive pilot (MDP + RL)", "planned"),
    ("Corridor B conflict (self-play)", "planned"),
]

st.markdown("""
<style>
:root{
  --ground:#100F0D; --panel:#1B1915; --raised:#221F1A; --rule:#2E2A24;
  --ink:#ECE6DB; --muted:#A8A093; --faint:#948C7F; --amber:#F2B233;
  --sat:#7FD9A6; --unsat:#F58B7C; --blocked:#F0A868; --syntax:#BCA9F5;
  --mono:'JetBrains Mono',Consolas,monospace;
  --ease:cubic-bezier(.25,1,.5,1);
}
.block-container{padding-top:1.4rem; padding-bottom:6rem; max-width:1500px}
header[data-testid="stHeader"]{background:transparent}

/* command bar */
.cmdbar{display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:14px 24px;
  padding-bottom:14px; border-bottom:1px solid var(--rule); margin-bottom:14px}
.cmd-title{font-stretch:72%; font-weight:800; font-size:2.35rem; line-height:1; letter-spacing:.01em;
  text-transform:uppercase; margin:0; color:var(--ink)}
.cmd-title span{color:var(--amber)}
.cmd-sub{color:var(--muted); font-size:.9rem; margin-top:6px}
.kv{display:flex; flex-wrap:wrap; gap:8px}
.kv div{display:flex; align-items:center; gap:8px; padding:6px 11px; border:1px solid var(--rule);
  border-radius:6px; background:var(--panel); font-size:.92rem; color:var(--muted)}
.kv b{color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums}

/* pills */
.pill{display:inline-flex; align-items:center; gap:6px; font-size:.78rem; font-weight:650; letter-spacing:.03em;
  text-transform:uppercase; padding:3px 9px; border-radius:999px; border:1px solid; white-space:nowrap; line-height:1.5}
.pill.neutral{color:var(--muted); border-color:var(--rule); background:rgba(236,230,219,.04)}
.pill.sat{color:var(--sat); border-color:rgba(127,217,166,.35); background:rgba(127,217,166,.10)}
.pill.unsat{color:var(--unsat); border-color:rgba(245,139,124,.38); background:rgba(245,139,124,.10)}
.pill.blocked{color:var(--blocked); border-color:rgba(240,168,104,.38); background:rgba(240,168,104,.10)}
.pill.syntax{color:var(--syntax); border-color:rgba(188,169,245,.35); background:rgba(188,169,245,.10)}
.pill.commit{color:var(--amber); border-color:rgba(242,178,51,.45); background:rgba(242,178,51,.12)}
.pill.live{color:var(--sat); border-color:rgba(127,217,166,.3); background:transparent}
.pill.next{color:var(--amber); border-color:rgba(242,178,51,.35); background:transparent}
.pill.planned{color:var(--faint); border-color:var(--rule); background:transparent}

/* fleet strip */
.fleet{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:10px; margin:2px 0 16px}
.unit{background:var(--panel); border:1px solid var(--rule); border-radius:8px; padding:11px 14px 12px; display:grid; gap:9px}
.unit-head{display:flex; align-items:center; gap:9px}
.unit-head .dot{width:10px; height:10px; border-radius:50%; background:var(--c); box-shadow:0 0 0 3px color-mix(in srgb,var(--c) 22%,transparent)}
.unit-head .uid{font-family:var(--mono); font-size:.8rem; color:var(--muted)}
.unit-head .uname{font-weight:650; font-size:1rem; color:var(--ink); margin-right:auto}
.meter{position:relative; height:8px; border-radius:4px; background:var(--raised); overflow:visible}
.meter .fill{height:100%; border-radius:4px; background:var(--f); transition:width .25s var(--ease)}
.meter .tick{position:absolute; top:-4px; bottom:-4px; width:2px; background:var(--unsat); opacity:.8}
.unit-meta{display:flex; flex-wrap:wrap; gap:4px 14px; font-size:.88rem; color:var(--muted)}
.unit-meta b{color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums}

/* verdict */
.verdict{display:flex; gap:12px; align-items:flex-start; padding:13px 16px; border-radius:8px; border:1px solid; margin-bottom:8px}
.verdict .answer{color:var(--ink); font-size:1.15rem; line-height:1.4; text-wrap:pretty}
.verdict .order{margin:0; color:var(--muted); font-size:.9rem; margin-top:4px}
.verdict.ok{border-color:rgba(127,217,166,.35); background:rgba(127,217,166,.07)}
.verdict.no{border-color:rgba(245,139,124,.38); background:rgba(245,139,124,.07)}

/* map legend */
.legend{display:flex; flex-wrap:wrap; gap:6px 16px; font-size:.88rem; color:var(--muted); margin-top:-4px}
.legend span{display:inline-flex; align-items:center; gap:6px}
.legend i{width:12px; height:12px; border-radius:2px; display:inline-block; border:1px solid var(--rule)}

/* reasoning log */
.panel-title{display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:2px 10px; margin:0 0 8px}
.panel-title h3{margin:0; font-size:1.2rem; font-weight:650; color:var(--ink); flex:0 0 auto; white-space:nowrap}
.panel-title small{color:var(--faint); font-size:.82rem; flex:0 1 auto}
.step{display:grid; grid-template-columns:28px 1fr; gap:10px; padding:11px 4px 13px; border-bottom:1px solid var(--rule);
  animation:step-in .22s var(--ease) both}
.step:last-child{border-bottom:0}
.step .n{font-family:var(--mono); font-size:.85rem; color:var(--faint); padding-top:3px; text-align:right}
.step .head{display:flex; flex-wrap:wrap; align-items:center; gap:8px}
.step .act{font-family:var(--mono); font-size:.95rem; color:var(--ink)}
.step .thought{margin:6px 0 0; color:var(--muted); font-size:1rem; line-height:1.5; text-wrap:pretty}
/* the two rows the audience must read: a decision, not another log line */
.step.sat,.step.unsat{border-bottom:0; border:1px solid; border-radius:8px; padding:12px 14px 13px; margin:8px 0}
.step.sat{background:rgba(127,217,166,.07); border-color:rgba(127,217,166,.32)}
.step.unsat{background:rgba(245,139,124,.07); border-color:rgba(245,139,124,.34)}
.step.sat .act,.step.unsat .act{font-size:1rem}
.step .plain{margin:7px 0 0; font-size:1.02rem; line-height:1.45; color:var(--ink); font-weight:600}
.step.unsat .plain{color:var(--unsat)}
.step.sat .plain{color:var(--sat)}
.step details{margin-top:7px}
.step summary{cursor:pointer; color:var(--faint); font-size:.85rem; list-style:none; width:fit-content}
.step summary::-webkit-details-marker{display:none}
.step summary::before{content:"+ "; font-family:var(--mono)}
.step details[open] summary::before{content:"- "}
.step summary:hover{color:var(--ink)}
.step pre{margin:6px 0 0; padding:9px 11px; background:var(--ground); border:1px solid var(--rule); border-radius:6px;
  font-family:var(--mono); font-size:.84rem; line-height:1.55; color:#CFC7B9; white-space:pre-wrap; word-break:break-word; max-height:260px; overflow:auto}
.working{display:flex; align-items:center; gap:10px; padding:10px 4px; color:var(--muted); font-size:.95rem}
.working i{width:8px; height:8px; border-radius:50%; background:var(--amber); animation:pulse 1.1s ease-in-out infinite}
.empty{padding:18px 4px; color:var(--muted); font-size:1rem; line-height:1.6; max-width:68ch}
.empty b{color:var(--ink); font-weight:600}
@keyframes step-in{from{opacity:.35; transform:translateY(4px)} to{opacity:1; transform:none}}
@keyframes pulse{0%,100%{opacity:.35} 50%{opacity:1}}

/* sidebar */
.side-brand{font-stretch:72%; font-weight:800; font-size:1.5rem; text-transform:uppercase; letter-spacing:.02em; color:var(--ink); margin:0}
.side-brand span{color:var(--amber)}
.side-note{color:var(--muted); font-size:.82rem; line-height:1.45; margin:4px 0 0}
.layers{display:grid; gap:7px; margin-top:4px}
.layers div{display:flex; align-items:center; justify-content:space-between; gap:10px; font-size:.9rem; color:var(--ink)}
.side-h{font-size:.85rem; font-weight:650; color:var(--muted); margin:18px 0 8px}

@media (prefers-reduced-motion: reduce){
  .step,.working i,.meter .fill{animation:none; transition:none}
}
</style>
""", unsafe_allow_html=True)

if "result" not in st.session_state:
    st.session_state.result = None


# ------------------------------------------------------------------ helpers
def near_location(x, y):
    for name, (lx, ly) in world.LOCATIONS.items():
        if abs(lx - x) + abs(ly - y) <= 1:
            return name
    return None


def fleet_html(robots):
    units = []
    for r in robots:
        disabled = r["battery_pct"] < r["min_battery"]
        where = near_location(r["x"], r["y"])
        status = ("Disabled", "unsat") if disabled else (f"At {where}" if where else "In tunnels", "neutral")
        fill = "var(--unsat)" if disabled else "var(--amber)" if r["battery_pct"] < 35 else "#CFC7B9"
        units.append(f"""
<div class="unit">
  <div class="unit-head"><i class="dot" style="--c:{ROBOT_COLORS[r['robot_id']]}"></i>
    <span class="uid">{r['robot_id']}</span><span class="uname">{escape(r['name'])}</span>
    <span class="pill {status[1]}">{status[0]}</span></div>
  <div class="meter" title="Minimum battery {r['min_battery']}%">
    <div class="fill" style="width:{max(r['battery_pct'], 2)}%; --f:{fill}"></div>
    <div class="tick" style="left:{r['min_battery']}%"></div></div>
  <div class="unit-meta"><span>Battery <b>{r['battery_pct']}%</b></span><span>Capacity <b>{r['capacity']} kg</b></span>
    <span>Drain <b>{r['drain_rate']}%/kg</b></span><span>{'Silent wheels' if r['quiet_wheels'] else '<b>No</b> silent wheels'}</span></div>
</div>""")
    return f"<div class='fleet'>{''.join(units)}</div>"


def plain_verdict(obs):
    """One sentence of English for a Z3 answer, so the room doesn't have to read JSON."""
    if not isinstance(obs, dict):
        return ""
    if obs.get("status") == "UNSATISFIABLE":
        d = obs.get("diagnostics", {})
        asked, usable = d.get("total_requested_weight"), d.get("available_active_capacity")
        if asked is not None and usable is not None:
            return (f"No legal assignment exists: {asked} kg asked for, {usable} kg usable "
                    f"across {len(d.get('active_agvs', []))} available robots.")
        return "No legal assignment exists for this request."
    if obs.get("status") == "SATISFIABLE":
        a = obs.get("assignments", {})
        per_robot = {}
        for item, rid in a.items():
            per_robot.setdefault(rid, []).append(item)
        split = ", ".join(f"{rid} takes {len(items)}" for rid, items in sorted(per_robot.items()))
        return f"Proved feasible: {len(a)} items assigned ({split})." if a else "Proved feasible."
    return ""


def step_html(i, entry):
    label, kind = STEP_KIND[entry["flag"]]
    obs = escape(json.dumps(entry["observation"], indent=1))
    is_open = " open" if entry["flag"] in ("sat", "unsat", "blocked", "syntax") else ""
    thought = f"<div class='thought'>{escape(entry['thought'])}</div>" if entry["thought"] else ""
    plain = plain_verdict(entry["observation"]) if entry["flag"] in ("sat", "unsat") else ""
    plain_html = f"<div class='plain'>{escape(plain)}</div>" if plain else ""
    # no blank lines inside: markdown would end the HTML block there
    return (f"<div class='step {kind if entry['flag'] in ('sat', 'unsat') else ''}'><span class='n'>{i:02d}</span><div>"
            f"<div class='head'><span class='pill {kind}'>{label}</span>"
            f"<span class='act'>{escape(entry['action'])}</span></div>{thought}{plain_html}"
            f"<details{is_open}><summary>Observation</summary><pre>{obs}</pre></details></div></div>")


def campus_figure(result):
    z = [[1 if c == "#" else 2 if c == "~" else 3 if c == "g" else 0 for c in row] for row in world.ROWS]
    scale = [[0, "#3A342C"], [.25, "#3A342C"], [.25, "#0A0908"], [.5, "#0A0908"],
             [.5, "#1F5673"], [.75, "#1F5673"], [.75, "#6E6A1C"], [1, "#6E6A1C"]]
    fig = go.Figure(go.Heatmap(z=z, colorscale=scale, zmin=0, zmax=3, showscale=False,
                               hoverinfo="skip", xgap=1, ygap=1))

    result = result or {}
    for rid, route in result.get("routes", {}).items():
        if rid not in result.get("assignments", {}).values():
            continue
        xs, ys = zip(*route["path"])
        color = ROBOT_COLORS.get(rid, "#fff")
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=color, width=14), opacity=.2))
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=f"{rid} · {route['steps']} steps",
                                 line=dict(color=color, width=4)))

    for name, (x, y) in world.LOCATIONS.items():
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text", text=[name], textposition="top center", showlegend=False,
            textfont=dict(color="#ECE6DB", size=15, family="Archivo, sans-serif"), hoverinfo="text",
            marker=dict(symbol="diamond", size=15, color="#100F0D", line=dict(color="#F2B233", width=2.5))))

    robots = memory.robots()
    fig.add_trace(go.Scatter(
        x=[r["x"] for r in robots], y=[r["y"] for r in robots], mode="markers", showlegend=False,
        marker=dict(size=19, color=[ROBOT_COLORS[r["robot_id"]] for r in robots], line=dict(color="#100F0D", width=3)),
        hovertext=[f"{r['robot_id']} {r['name']} · battery {r['battery_pct']}%" for r in robots], hoverinfo="text"))

    fig.update_yaxes(autorange="reversed", scaleanchor="x", constrain="domain", visible=False)
    fig.update_xaxes(constrain="domain", visible=False)
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=22, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Archivo, sans-serif", color="#A8A093"),
                      legend=dict(orientation="h", y=-0.03, x=0, font=dict(size=14)),
                      hoverlabel=dict(bgcolor="#221F1A", bordercolor="#2E2A24", font=dict(color="#ECE6DB")))
    return fig


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("<div class='side-brand'>Campus<span>Courier</span></div>"
                "<div class='side-note'>An LLM coordinator whose every dispatch plan must pass a Z3 proof "
                "before a robot moves.</div>", unsafe_allow_html=True)
    st.markdown("<div class='side-h'>Reasoning engine</div>", unsafe_allow_html=True)
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    mode = st.radio("Reasoning engine", ["OpenAI (live)", "Offline scripted replay"], label_visibility="collapsed",
                    index=0 if has_key else 1, disabled=not has_key)
    if st.button("Reset campus state", width="stretch", help="Rebuild the database: batteries, stock and positions"):
        memory.reset()
        st.session_state.result = None
        st.rerun()
    if SHOW_FULL:
        st.markdown("<div class='side-h'>System layers</div><div class='layers'>" + "".join(
            f"<div><span>{name}</span><span class='pill {status}'>{status}</span></div>" for name, status in LAYERS
        ) + "</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ command bar + fleet
robots = memory.robots()
stock = {s["item"]: s["stock"] for s in memory.supplies()}
result = st.session_state.result
verdict = next((t["observation"].get("status") for t in reversed((result or {}).get("trace", []))
                if t["flag"] in ("sat", "unsat")), None)
verdict_html = (f"<span class='pill {'sat' if verdict == 'SATISFIABLE' else 'unsat'}'>"
                f"{'SAT' if verdict == 'SATISFIABLE' else 'UNSAT'}</span>") if verdict else "<b>none yet</b>"

st.markdown(f"""
<div class="cmdbar">
  <div><div class="cmd-title">Campus <span>Courier</span></div>
       <div class="cmd-sub">Campus delivery floor · a class waiting in Studio 3 · 3 courier robots on shift</div></div>
  <div class="kv">
    <div>Engine <b>{'OpenAI live' if mode.startswith('OpenAI') else 'Offline replay'}</b></div>
    <div>Last Z3 verdict {verdict_html}</div>
    <div>Dispatches <b>{len(memory.tasks())}</b></div>
    <div>Projectors <b>{stock.get('projector', 0)}</b></div>
  </div>
</div>
{fleet_html(robots)}
""", unsafe_allow_html=True)

order = st.chat_input("Send an order to the coordinator, e.g. “Get 2 lab kits to the Library”")
preset_cols = st.columns(len(PRESETS))
for col, (label, text) in zip(preset_cols, PRESETS.items()):
    if col.button(label, width="stretch", help=text):
        order = text

map_col, log_col = st.columns([7, 5], gap="large")

with log_col:
    st.markdown("<div class='panel-title'><h3>Coordinator reasoning</h3>"
                "<small>Every step is checked in code</small></div>", unsafe_allow_html=True)
    if order:
        stream = st.container(height=470, border=True)
        stream.markdown(f"<div class='empty'>Order: <b>“{escape(order)}”</b></div>", unsafe_allow_html=True)
        working = stream.empty()
        working.markdown("<div class='working'><i></i>Coordinator is working…</div>", unsafe_allow_html=True)
        steps = []

        def on_step(entry):
            steps.append(entry)
            working.empty()
            stream.markdown(step_html(len(steps), entry), unsafe_allow_html=True)

        try:
            if mode.startswith("OpenAI"):
                llm = agent.OpenAILLM()
            elif order == PRESETS["Low-battery trap"]:
                llm = agent.scripted_low_battery()
            else:
                llm = agent.scripted_delivery(overloaded=order == PRESETS["Overload"])
            run = agent.run_agent(llm, order, on_step=on_step)
        except Exception as exc:  # network down, bad API key, replay out of steps: never crash mid-demo
            hint = ("Check the wifi and OPENAI_API_KEY, or switch the sidebar to Offline scripted replay."
                    if mode.startswith("OpenAI") else "Offline replay only covers the three preset orders.")
            run = {"ok": False, "final_answer": f"The reasoning engine stopped ({type(exc).__name__}). {hint}",
                   "destination": None, "assignments": {}, "packages": [], "routes": {}, "trace": steps}
        if run["ok"]:
            memory.record_dispatch(order, run["destination"], run["packages"], run["assignments"], run["routes"])
        wandb_log.log_run(order, run, engine="live" if mode.startswith("OpenAI") else "offline")
        st.session_state.result = run | {"order": order}
        st.rerun()
    else:
        stream = st.container(height=470, border=True)
        if result:
            stream.markdown("".join(step_html(i, e) for i, e in enumerate(result["trace"], 1)),
                            unsafe_allow_html=True)
        else:
            stream.markdown(
                "<div class='empty'><b>No order yet.</b> Every plan the coordinator makes must pass three checks "
                "before a robot moves: its numbers must match the database, Z3 must prove it feasible, and each "
                "robot needs a real route.<br><br>Try <b>Routine dispatch</b> for a clean run, or <b>Overload</b> "
                "to watch Z3 reject a plan and the coordinator cut the load.</div>", unsafe_allow_html=True)

with map_col:
    if result:
        ok = result["ok"]
        st.markdown(f"""
<div class="verdict {'ok' if ok else 'no'}">
  <span class="pill {'sat' if ok else 'unsat'}">{'Dispatched' if ok else 'Not dispatched'}</span>
  <div><div class='answer'>{escape(result['final_answer'])}</div><div class="order">Order: “{escape(result['order'])}”</div></div>
</div>""", unsafe_allow_html=True)
    st.plotly_chart(campus_figure(result), width="stretch", config={"displayModeBar": False})
    st.markdown("""<div class="legend">
  <span><i style="background:#3A342C"></i>Corridor</span><span><i style="background:#0A0908"></i>Wall</span>
  <span><i style="background:#1F5673"></i>Just mopped, wheels slip</span><span><i style="background:#6E6A1C"></i>Quiet zone, silent wheels only</span>
  <span><i style="background:#100F0D;border-color:#F2B233;transform:rotate(45deg) scale(.8)"></i>Location</span>
</div>""", unsafe_allow_html=True)

if SHOW_FULL:  # the database view number of supplies and weight
    st.write("")
    tab_log, tab_stock = st.tabs(["Task log", "Supplies"])
    with tab_log:
        tasks = memory.tasks()
        if tasks:
            st.dataframe(pd.DataFrame(tasks), width="stretch", hide_index=True, column_config={
                "id": st.column_config.NumberColumn("#", width="small"),
                "created_at": "Time", "order_text": "Order", "robot_id": "Robot", "items": "Items",
                "destination": "Destination", "route_steps": st.column_config.NumberColumn("Route steps"),
                "status": "Status"})
        else:
            st.caption("No dispatches yet. Verified plans are logged here with their route length.")
    with tab_stock:
        st.dataframe(pd.DataFrame(memory.supplies()), width="stretch", hide_index=True, column_config={
            "item": "Supply", "weight": st.column_config.NumberColumn("Weight per unit", format="%d kg"),
            "stock": st.column_config.ProgressColumn("In stock", min_value=0, max_value=10, format="%d")})
