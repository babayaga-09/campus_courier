// DeepRescue demo-day deck (19 Sep 2026). Run: node build_deck.js
const pptxgen = require("pptxgenjs");
const path = require("path");

const DIR = __dirname;
const OUT = path.join(__dirname, "..", "DeepRescue_Demo_Day.pptx");

// ---- tokens --------------------------------------------------------------
const K = {
  coal: "100F0D", panel: "1B1915", raised: "25221C", rule: "3A352D",
  ink: "ECE6DB", muted: "B3AB9E", faint: "857E71", amber: "F2B233",
  sat: "5FC98E", unsat: "F06A5A", wet: "1F5673", gas: "6E6A1C", tunnel: "3A342C",
  mole: "E9B44C", badger: "58C4DD", ferret: "B8D86B",
};
const HEAD = "Arial Narrow", BODY = "Arial";
const W = 13.333, M = 0.6;
const TOTAL = 8;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "DeepRescue: the LLM proposes, the maths decides";
pres.author = "Aryan Grang";

// ---- helpers (fresh option objects every call) -----------------------------
function text(slide, str, o) {
  slide.addText(str, Object.assign({ isTextBox: true, fontFace: BODY, color: K.ink, margin: 0, valign: "top" }, o));
}
function rect(slide, o) {
  slide.addShape(o.radius ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE, Object.assign({
    line: { color: o.lineColor || o.fill, width: o.lineWidth || 0.75 },
    fill: { color: o.fill },
  }, o.radius ? { rectRadius: o.radius } : {}, { x: o.x, y: o.y, w: o.w, h: o.h }));
}
function newSlide(n) {
  const s = pres.addSlide();
  s.background = { color: K.coal };
  if (n > 1) text(s, `DeepRescue  ${n} / ${TOTAL}`, { x: W - M - 2.5, y: 7.05, w: 2.5, h: 0.25, fontSize: 10, color: K.faint, align: "right" });
  return s;
}
function title(s, str, sub) {
  text(s, str, { x: M, y: 0.45, w: W - 2 * M, h: 0.75, fontFace: HEAD, fontSize: 40, bold: true, valign: "middle" });
  if (sub) text(s, sub, { x: M, y: 1.2, w: W - 2 * M, h: 0.45, fontSize: 16, color: K.muted, valign: "middle" });
}
const PILL = { sat: [K.sat, "15261C"], unsat: [K.unsat, "2E1A16"], live: [K.sat, K.coal], next: [K.amber, K.coal], planned: [K.faint, K.coal] };
function pill(s, label, kind, x, y, w) {
  const [c, bg] = PILL[kind];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.34, rectRadius: 0.17, fill: { color: bg }, line: { color: c, width: 1.25 } });
  text(s, label, { x, y, w, h: 0.34, fontSize: 11, bold: true, color: c, align: "center", valign: "middle", charSpacing: 1 });
}
function arrow(s, x, y, w, color) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: color || K.faint, width: 2, endArrowType: "triangle" } });
}

// ---- 1. Title ---------------------------------------------------------------
{
  const s = newSlide(1);
  text(s, "AUTONOMOUS AGENTS CAPSTONE  ·  TRACK B", { x: M, y: 1.15, w: 5.6, h: 0.3, fontSize: 12, bold: true, color: K.amber, charSpacing: 1 });
  text(s, [{ text: "DEEP", options: { color: K.ink } }, { text: "RESCUE", options: { color: K.amber } }],
    { x: M, y: 1.55, w: 5.7, h: 1.2, fontFace: HEAD, fontSize: 64, bold: true, valign: "middle" });
  text(s, "The LLM proposes.\nThe maths decides.", { x: M, y: 2.95, w: 5.6, h: 1.25, fontFace: HEAD, fontSize: 34, color: K.ink });
  text(s, "Formally verified robot dispatch inside a collapsed coal mine", { x: M, y: 4.35, w: 5.2, h: 0.7, fontSize: 16, color: K.muted });
  text(s, [{ text: "Aryan Grang", options: { bold: true, color: K.ink, breakLine: true } }, { text: "Demo day  ·  19 September 2026", options: { color: K.muted } }],
    { x: M, y: 6.1, w: 5, h: 0.7, fontSize: 14 });
  s.addImage({ path: path.join(DIR, "map_routes.png"), x: 6.45, y: 1.15, w: 6.28, h: 3.91 });
  text(s, "Real output from the system: A* routes to the trapped miners in Gallery 3. Mole (amber) crosses the methane pocket; Badger (cyan) wades the flooded tunnel.",
    { x: 6.45, y: 5.2, w: 6.28, h: 0.6, fontSize: 11, color: K.faint });
  s.addNotes("Hi, I'm Aryan. DeepRescue puts an LLM in charge of rescue robots in a collapsed coal mine, but never trusts it blindly. The map on the right is real output from my system: A* routes to the trapped miners. The one-line idea: the LLM proposes, the maths decides.");
}

// ---- 2. Situation -----------------------------------------------------------
{
  const s = newSlide(2);
  title(s, "THE SITUATION UNDERGROUND", "A methane explosion has collapsed the mine. Miners are trapped in Gallery 3, and humans can't go in yet.");
  s.addImage({ path: path.join(DIR, "map_labelled.png"), x: M, y: 1.95, w: 6.6, h: 4.11 });
  text(s, "3 robots at Base Camp  ·  Mole 30 kg  ·  Badger 20 kg  ·  Ferret 10 kg on 15% battery", { x: M, y: 6.2, w: 6.6, h: 0.3, fontSize: 12, color: K.faint });

  const rows = [
    ["No GPS, no cameras", "Position comes from a noisy count of nearby rock walls", K.tunnel, "HMM"],
    ["Flooded tunnels", "Wheels slip: 80% intended move, 20% sideways", K.wet, "MDP"],
    ["Methane pocket", "Robots that aren't spark-safe must stay out", K.gas, "Z3"],
    ["Single-lane Shaft B", "Only one robot can pass at a time", K.raised, "Conflict"],
    ["Plain-language orders", "“Get 2 oxygen tanks and a medkit to Gallery 3”", K.raised, "LLM"],
  ];
  rows.forEach(([head, desc, sw, tag], i) => {
    const y = 2.0 + i * 0.86;
    rect(s, { x: 7.65, y: y + 0.05, w: 0.38, h: 0.38, fill: sw, lineColor: K.rule, radius: 0.05 });
    if (i === 3) s.addShape(pres.shapes.DIAMOND, { x: 7.74, y: y + 0.14, w: 0.2, h: 0.2, fill: { color: K.coal }, line: { color: K.amber, width: 1.5 } });
    if (i === 4) s.addShape(pres.shapes.OVAL, { x: 7.75, y: y + 0.15, w: 0.18, h: 0.18, fill: { color: K.mole }, line: { color: K.coal, width: 1 } });
    text(s, head, { x: 8.25, y, w: 3.4, h: 0.34, fontSize: 17, bold: true });
    text(s, desc, { x: 8.25, y: y + 0.36, w: 4.45, h: 0.4, fontSize: 13, color: K.muted });
    text(s, tag, { x: 11.65, y: y + 0.02, w: 1.08, h: 0.3, fontSize: 11, bold: true, color: K.amber, align: "right", charSpacing: 1 });
  });
  s.addNotes("Three robots have to carry oxygen, medkits and water from Base Camp to Gallery 3. Everything about this place breaks naive AI: no GPS underground, flooded floors that make wheels slip, a methane pocket where a spark is fatal, and a single-lane shaft. The amber tags show which classical algorithm handles each problem.");
}

// ---- 3. Why an LLM alone is not enough --------------------------------------
{
  const s = newSlide(3);
  title(s, "WHY AN LLM ALONE IS NOT ENOUGH");
  const cols = [
    ["The LLM", "Understands messy human requests", "Sounds confident even when its maths or physics is wrong"],
    ["Classical algorithms", "Precise and provable: search, probability, logic", "Can't understand a single sentence from a person"],
  ];
  cols.forEach(([head, good, bad], i) => {
    const x = M + i * 6.22;
    rect(s, { x, y: 1.55, w: 5.91, h: 2.75, fill: K.panel, lineColor: K.rule, radius: 0.08 });
    text(s, head, { x: x + 0.35, y: 1.8, w: 5.2, h: 0.55, fontFace: HEAD, fontSize: 28, bold: true });
    text(s, "STRENGTH", { x: x + 0.35, y: 2.55, w: 2, h: 0.25, fontSize: 11, bold: true, color: K.amber, charSpacing: 1 });
    text(s, good, { x: x + 0.35, y: 2.82, w: 5.2, h: 0.4, fontSize: 17 });
    text(s, "WEAKNESS", { x: x + 0.35, y: 3.35, w: 2, h: 0.25, fontSize: 11, bold: true, color: K.faint, charSpacing: 1 });
    text(s, bad, { x: x + 0.35, y: 3.62, w: 5.2, h: 0.45, fontSize: 17, color: K.muted });
  });
  text(s, [{ text: "“Usually right”", options: { color: K.amber } }, { text: ", repeated across every rescue run, means regular failures.", options: { color: K.ink } }],
    { x: M, y: 4.6, w: W - 2 * M, h: 0.7, fontFace: HEAD, fontSize: 30, bold: true, valign: "middle" });

  const flow = [["LLM coordinates", "reads the order, calls tools"], ["Algorithms compute", "A*, HMM, MDP, Q-learning"], ["Z3 approves", "every plan, before any robot moves"]];
  flow.forEach(([h, d], i) => {
    const x = M + i * 4.2;
    rect(s, { x, y: 5.6, w: 3.55, h: 1.05, fill: i === 2 ? "2A2314" : K.panel, lineColor: i === 2 ? K.amber : K.rule, radius: 0.08 });
    text(s, h, { x: x + 0.25, y: 5.72, w: 3.1, h: 0.42, fontSize: 19, bold: true, color: i === 2 ? K.amber : K.ink });
    text(s, d, { x: x + 0.25, y: 6.15, w: 3.1, h: 0.35, fontSize: 13, color: K.muted });
    if (i < 2) arrow(s, x + 3.6, 6.12, 0.58, K.amber);
  });
  s.addNotes("LLMs are brilliant at understanding people and terrible at guaranteeing physics. Classical algorithms are the opposite. In a rescue, 'usually right' isn't acceptable. So DeepRescue splits the job: the LLM coordinates, the algorithms from this course do the maths, and a Z3 solver has to approve every single plan.");
}

// ---- 4. Architecture --------------------------------------------------------
{
  const s = newSlide(4);
  title(s, "SIX LAYERS, EACH BUILT ON A COURSE LAB");
  const nodes = ["Commander order", "LLM coordinator", "Three safety gates", "Robots move", "Live dashboard"];
  nodes.forEach((n, i) => {
    const x = M + i * 2.5;
    const hot = i === 2;
    rect(s, { x, y: 1.45, w: 2.14, h: 0.72, fill: hot ? "2A2314" : K.panel, lineColor: hot ? K.amber : K.rule, radius: 0.08 });
    text(s, n, { x, y: 1.45, w: 2.14, h: 0.72, fontSize: 15, bold: true, align: "center", valign: "middle", color: hot ? K.amber : K.ink });
    if (i < 4) arrow(s, x + 2.17, 1.81, 0.3, K.faint);
  });

  const cols = [[M, 2.75, "LAYER"], [3.45, 5.15, "WHAT IT DOES"], [8.75, 2.45, "BUILT ON"], [11.33, 1.4, "STATUS"]];
  const hy = 2.6;
  cols.forEach(([x, w, h]) => text(s, h, { x, y: hy, w, h: 0.3, fontSize: 11, bold: true, color: K.faint, charSpacing: 1 }));
  const rows = [
    ["LLM coordinator", "Turns orders into tool calls: thought, action, observation", "ReAct lab", "live"],
    ["Safety filter", "Z3 proves every dispatch plan is feasible before it runs", "SMT reflection lab", "live"],
    ["Route finder", "A* through the tunnel grid to any location", "Lab 1 · A*", "live"],
    ["Memory", "Robots, supplies and the task log in SQLite", "ReAct lab database", "live"],
    ["Perception", "HMM filter: true position from noisy wall counts", "Lab 2 · HMM", "next"],
    ["Adaptive pilot", "Value iteration on slippery floors; Q-learning speed habits", "Lab 3 · MDP, Q-learning", "planned"],
    ["Shaft B conflict", "Two robots learn right-of-way by self-play (bonus)", "Q-learning lab", "planned"],
  ];
  rows.forEach(([a, b, c, st], i) => {
    const y = 2.98 + i * 0.55;
    s.addShape(pres.shapes.LINE, { x: M, y, w: W - 2 * M, h: 0, line: { color: K.rule, width: 0.75 } });
    text(s, a, { x: M, y: y + 0.1, w: 2.75, h: 0.36, fontSize: 15, bold: true, valign: "middle" });
    text(s, b, { x: 3.45, y: y + 0.1, w: 5.15, h: 0.36, fontSize: 13, color: K.muted, valign: "middle" });
    text(s, c, { x: 8.75, y: y + 0.1, w: 2.45, h: 0.36, fontSize: 13, valign: "middle" });
    pill(s, st.toUpperCase(), st, 11.33, y + 0.11, 1.15);
  });
  s.addNotes("Here's the architecture. An order flows through the LLM coordinator, then three safety gates, and only then do robots move, with everything visible on the dashboard. Every layer is built on one of our labs. Four are live today, perception is next, and the adaptive pilot and Shaft B conflict come before the final submission.");
}

// ---- 5. Verification gates ---------------------------------------------------
{
  const s = newSlide(5);
  title(s, "THE VERIFICATION LAYER: THREE GATES IN CODE", "The LLM is never trusted. Each gate is Python the model can't talk its way past.");
  const gates = [
    ["1", "Grounding", "Every battery level, capacity and weight in the plan must match the database.",
      "The model claimed Ferret had 95% battery. The database says 15%. Rejected before Z3 even ran."],
    ["2", "Z3 proof", "Each item on exactly one robot. No robot under 20% battery. Load within capacity. Battery after drain above the minimum.",
      "On UNSAT the reason goes back to the LLM, and resubmitting the same plan is blocked."],
    ["3", "Commit", "The final answer must equal Z3's approved assignment, with a reachable A* route for every robot.",
      "The LLM can't declare success on its own authority."],
  ];
  gates.forEach(([n, name, rule, ex], i) => {
    const x = M + i * 4.2;
    rect(s, { x, y: 1.95, w: 3.75, h: 4.1, fill: K.panel, lineColor: K.rule, radius: 0.08 });
    text(s, n, { x: x + 0.3, y: 2.1, w: 0.8, h: 0.8, fontFace: HEAD, fontSize: 48, bold: true, color: K.amber });
    text(s, name, { x: x + 0.3, y: 2.9, w: 3.2, h: 0.5, fontFace: HEAD, fontSize: 28, bold: true });
    text(s, rule, { x: x + 0.3, y: 3.45, w: 3.2, h: 1.3, fontSize: 14 });
    rect(s, { x: x + 0.2, y: 4.8, w: 3.35, h: 1.1, fill: K.raised, lineColor: K.raised, radius: 0.06 });
    text(s, ex, { x: x + 0.35, y: 4.88, w: 3.05, h: 0.95, fontSize: 12.5, color: K.muted, valign: "middle" });
    if (i < 2) arrow(s, x + 3.8, 4.0, 0.36, K.amber);
  });
  text(s, [{ text: "Next Z3 rules:  ", options: { bold: true, color: K.amber } },
    { text: "no-spark robots barred from methane routes  ·  return-trip battery reserve  ·  one robot in Shaft B at a time", options: { color: K.ink } }],
    { x: M, y: 6.3, w: W - 2 * M, h: 0.4, fontSize: 14, valign: "middle" });
  s.addNotes("This is the part that makes the system trustworthy. Gate one checks every number against the database: in testing, the model claimed a robot had 95% battery when it had 15%, and it was caught. Gate two is the Z3 proof. Gate three makes sure the final answer is exactly what Z3 approved. All three are code, not prompts.");
}

// ---- 6. Worked example ------------------------------------------------------
{
  const s = newSlide(6);
  title(s, "WORKED EXAMPLE: THE OVERLOAD ORDER", "“Send 3 oxygen tanks and the stretcher to Gallery 3, fast.”");

  // stage A: 54 vs 50 -> UNSAT
  rect(s, { x: M, y: 1.95, w: 5.0, h: 2.2, fill: K.panel, lineColor: K.rule, radius: 0.08 });
  text(s, "54 kg", { x: M + 0.3, y: 2.05, w: 2.2, h: 0.9, fontFace: HEAD, fontSize: 54, bold: true });
  text(s, "asked: 3 × 12 kg oxygen + 18 kg stretcher", { x: M + 0.3, y: 2.95, w: 2.25, h: 0.55, fontSize: 12, color: K.muted });
  text(s, "50 kg", { x: M + 2.7, y: 2.05, w: 2.1, h: 0.9, fontFace: HEAD, fontSize: 54, bold: true, color: K.amber });
  text(s, "usable: Mole 30 + Badger 20. Ferret disabled at 15%", { x: M + 2.7, y: 2.95, w: 2.1, h: 0.55, fontSize: 12, color: K.muted });
  pill(s, "Z3: UNSAT", "unsat", M + 0.3, 3.6, 1.45);
  text(s, "54 kg exceeds 50 kg usable capacity", { x: M + 1.9, y: 3.6, w: 3.0, h: 0.34, fontSize: 13, color: K.ink, valign: "middle" });
  arrow(s, 5.68, 3.05, 0.5, K.amber);

  // stage B: reflection
  rect(s, { x: 6.3, y: 1.95, w: 3.1, h: 2.2, fill: K.panel, lineColor: K.rule, radius: 0.08 });
  text(s, "LLM reflects", { x: 6.6, y: 2.1, w: 2.6, h: 0.5, fontFace: HEAD, fontSize: 26, bold: true });
  text(s, "Oxygen is life-critical, so it drops the stretcher and resubmits a lighter plan.", { x: 6.6, y: 2.65, w: 2.6, h: 1.3, fontSize: 14, color: K.muted });
  arrow(s, 9.48, 3.05, 0.5, K.amber);

  // stage C: 36 -> SAT
  rect(s, { x: 10.1, y: 1.95, w: 2.63, h: 2.2, fill: "15261C", lineColor: K.sat, radius: 0.08 });
  text(s, "36 kg", { x: 10.4, y: 2.05, w: 2.2, h: 0.9, fontFace: HEAD, fontSize: 54, bold: true });
  text(s, "3 × 12 kg oxygen", { x: 10.4, y: 2.95, w: 2.2, h: 0.35, fontSize: 12, color: K.muted });
  pill(s, "Z3: SAT", "sat", 10.4, 3.6, 1.3);

  // committed plan
  text(s, "Committed plan", { x: M, y: 4.3, w: 4, h: 0.35, fontSize: 18, bold: true });
  text(s, "LOAD vs CAPACITY", { x: 2.6, y: 4.68, w: 4, h: 0.3, fontSize: 11, bold: true, color: K.faint, charSpacing: 1 });
  text(s, "BATTERY (red tick = 20% minimum)", { x: 8.2, y: 4.68, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: K.faint, charSpacing: 1 });
  const robots = [
    ["RX-1 Mole", K.mole, 24, 30, "24 / 30 kg  ·  2 oxygen tanks", 85, 73],
    ["RX-2 Badger", K.badger, 12, 20, "12 / 20 kg  ·  1 oxygen tank", 40, 28],
    ["RX-3 Ferret", K.ferret, 0, 10, "Not used: battery below minimum", 15, 15],
  ];
  robots.forEach(([name, col, load, cap, label, b0, b1], i) => {
    const y = 5.02 + i * 0.64;
    s.addShape(pres.shapes.OVAL, { x: M, y: y + 0.1, w: 0.22, h: 0.22, fill: { color: col }, line: { color: K.coal, width: 1 } });
    text(s, name, { x: M + 0.35, y, w: 1.6, h: 0.42, fontSize: 14, bold: true, valign: "middle" });
    const bw = 5.2;
    rect(s, { x: 2.6, y: y + 0.05, w: bw, h: 0.32, fill: K.raised, lineColor: K.raised, radius: 0.04 });
    if (load) rect(s, { x: 2.6, y: y + 0.05, w: bw * load / cap, h: 0.32, fill: col, lineColor: col, radius: 0.04 });
    text(s, label, { x: 2.75, y: y + 0.05, w: bw - 0.2, h: 0.32, fontSize: 12, bold: !!load, color: load ? K.coal : K.muted, valign: "middle" });
    const mx = 8.2, mw = 2.6;
    rect(s, { x: mx, y: y + 0.13, w: mw, h: 0.16, fill: K.raised, lineColor: K.raised });
    rect(s, { x: mx, y: y + 0.13, w: mw * b1 / 100, h: 0.16, fill: b1 < 20 ? K.unsat : "CFC7B9", lineColor: b1 < 20 ? K.unsat : "CFC7B9" });
    s.addShape(pres.shapes.LINE, { x: mx + mw * 0.2, y: y + 0.04, w: 0, h: 0.34, line: { color: K.unsat, width: 2 } });
    text(s, b0 === b1 ? `${b1}%` : `${b0}% → ${b1}%`, { x: 11.0, y, w: 1.73, h: 0.42, fontSize: 14, bold: true, align: "right", valign: "middle", color: b1 < 20 ? K.unsat : K.ink });
  });
  s.addNotes("Here's a real run. The commander asks for 54 kilograms, but only 50 kilograms of capacity is usable, because Ferret's battery is below the minimum. Z3 says UNSAT and explains why. The LLM reflects, keeps the oxygen, drops the stretcher, and Z3 approves 36 kilograms. The batteries drain exactly as the model predicts.");
}

// ---- 7. Live demo ----------------------------------------------------------
{
  const s = newSlide(7);
  title(s, "LIVE DEMO: MINE RESCUE COMMAND");
  const orders = [
    ["1", "Routine dispatch", "2 oxygen tanks and a medkit to Gallery 3. Verified and dispatched."],
    ["2", "Overload", "Watch the red UNSAT step, the reflection, then the green SAT step."],
    ["3", "Low-battery trap", "The order asks for Ferret. The verifier refuses it."],
  ];
  orders.forEach(([n, h, d], i) => {
    const y = 1.6 + i * 1.12;
    text(s, n, { x: M, y, w: 0.6, h: 0.8, fontFace: HEAD, fontSize: 44, bold: true, color: K.amber });
    text(s, h, { x: M + 0.75, y: y + 0.05, w: 4.6, h: 0.42, fontSize: 20, bold: true });
    text(s, d, { x: M + 0.75, y: y + 0.48, w: 4.6, h: 0.55, fontSize: 14, color: K.muted });
  });
  text(s, "WATCH FOR", { x: M, y: 5.05, w: 3, h: 0.3, fontSize: 11, bold: true, color: K.amber, charSpacing: 1 });
  text(s, "The colour-coded reasoning stream, A* routes drawn on the mine map, and the SQLite task log updating live.",
    { x: M, y: 5.38, w: 5.2, h: 0.9, fontSize: 15 });
  rect(s, { x: 6.2, y: 1.5, w: 6.53, h: 4.55, fill: K.coal, lineColor: K.rule, radius: 0.04 });
  s.addImage({ path: path.join(DIR, "dash_crop.png"), x: 6.23, y: 1.53, w: 6.47, h: 4.46 });
  text(s, "The DeepRescue dashboard: fleet battery meters with the 20% minimum marked, the mine map, and the coordinator's reasoning panel.",
    { x: 6.2, y: 6.15, w: 6.53, h: 0.5, fontSize: 11, color: K.faint });
  s.addNotes("Now let me switch to the live dashboard. [Click Reset mine state first.] Order one is a routine dispatch. Order two overloads the robots so you can watch Z3 reject the plan and the LLM recover. Order three tries to use the low-battery robot, and the verifier refuses. If the wifi fails, switch the sidebar to Offline scripted replay.");
}

// ---- 8. Roadmap -------------------------------------------------------------
{
  const s = newSlide(8);
  title(s, "ROADMAP TO THE FINAL SUBMISSION");
  const ly = 1.95;
  s.addShape(pres.shapes.LINE, { x: M + 0.1, y: ly, w: W - 2 * M - 0.2, h: 0, line: { color: K.rule, width: 2 } });
  const items = [
    ["20–23 Sep", "Perception + new Z3 rules", "HMM belief heatmap on the map; methane no-spark zone, return-trip battery, Shaft B exclusion"],
    ["24–26 Sep", "Adaptive pilot", "Value iteration for flooded floors; Q-learning for fast vs careful driving"],
    ["27–28 Sep", "Shaft B conflict (bonus)", "Two robots learn right-of-way through self-play Q-learning"],
    ["30 Sep", "Final submission", "All six layers integrated, documentation and presentation"],
  ];
  items.forEach(([when, h, d], i) => {
    const x = M + 0.1 + i * 3.08;
    const last = i === 3;
    s.addShape(pres.shapes.OVAL, { x: x - 0.1, y: ly - 0.1, w: 0.2, h: 0.2, fill: { color: last ? K.amber : K.coal }, line: { color: last ? K.amber : K.muted, width: 2 } });
    text(s, when, { x, y: ly + 0.28, w: 2.8, h: 0.4, fontFace: HEAD, fontSize: 22, bold: true, color: last ? K.amber : K.ink });
    text(s, h, { x, y: ly + 0.72, w: 2.8, h: 0.4, fontSize: 16, bold: true });
    text(s, d, { x, y: ly + 1.12, w: 2.75, h: 1.1, fontSize: 13, color: K.muted });
  });
  text(s, [{ text: "An LLM that is never trusted blindly,", options: { color: K.ink, breakLine: true } },
    { text: "because something always checks its work.", options: { color: K.amber } }],
    { x: M, y: 4.75, w: 8.55, h: 1.5, fontFace: HEAD, fontSize: 33, bold: true, valign: "middle" });
  s.addImage({ path: path.join(DIR, "map_routes.png"), x: 9.35, y: 4.55, w: 3.38, h: 2.1 });
  s.addNotes("By the final submission on the 30th: the HMM heatmap and mine-specific Z3 rules, the adaptive pilot, and the Shaft B self-play conflict as a bonus layer. The takeaway: an LLM that is never trusted blindly, because something always checks its work. Thank you, happy to take questions.");
}

pres.writeFile({ fileName: OUT }).then(f => console.log("wrote", f));
