# CampusCourier

My final project for COMP-343, Autonomous Agents and Sequential Decision Making. It is a small delivery
service for one floor of the academic block, where an LLM reads the order and a Z3 solver has to approve
the plan before any robot moves.

![Demo: Z3 refuses an overloaded plan, the coordinator drops the whiteboard and retries, then refuses a robot below its minimum battery](demo.gif)

Three courier robots carry projectors, lab kits and water cases from the Supply Room to whichever room
asked for them. Staff type the order in normal English, for example "get 2 projectors and a lab kit to
Studio 3 before the 2pm class". An LLM turns that into a structured plan, and then three checks in code
decide whether the plan is allowed to happen. The short version of the idea is that the LLM proposes and
the maths decides.

The reason I built it this way is that an LLM is good at reading the request and unreliable at the
arithmetic. It will say yes to a load that does not fit, and it sounds exactly the same when it is right.
Thus I moved every hard rule out of the prompt and into a solver.

**GitHub:** <https://github.com/babayaga-09/campus_courier>
**W&B report:** see the Weights and Biases section below.

## Install and run

```bash
git clone https://github.com/babayaga-09/campus_courier.git
cd campus_courier
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

### Adding your own API key

There is no key anywhere in this repository. The code reads one from the environment, so you need to
make your own `.env` file first:

```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS or Linux
```

Then open `.env` and put your own OpenAI key after `OPENAI_API_KEY=`. You can make one at
<https://platform.openai.com/api-keys>. `.env` is listed in `.gitignore`, so it never gets committed.

However, you do not actually need a key to see the project work. Without one the dashboard falls back to
**Offline scripted replay**, which runs the same three stories with no network call at all. The solver,
the planner and the database are all still real in that mode. Only the LLM's choice of next action is
replayed.

### Running the dashboard

```bash
.venv\Scripts\python -m streamlit run app.py
```

It opens at <http://localhost:8511>. Run it from this folder, otherwise `.streamlit/config.toml` is not
picked up and the theme looks wrong. In VS Code you can press F5 and pick "Dashboard (Streamlit)".

### Running it without the interface

```bash
python agent.py              # the offline routine story
python agent.py --overload   # the offline story that Z3 refuses
python agent.py --live       # uses your API key
```

### Running the tests

```bash
.venv\Scripts\python test_agent.py     # 7 checks on the safety gates
.venv\Scripts\python stress_test.py    # 17 edge cases
.venv\Scripts\python perception.py     # runs the HMM filter along a route
```

All of these run offline against a throwaway database, so they do not touch the demo state.

## What each file does

### The parts I wrote for this project

| File | What it does |
|---|---|
| `app.py` | The Streamlit dashboard: the map, the robot cards, the reasoning panel, the verdict box, the belief heatmap, the task log and stock tables, and the styling. It is the only file that imports Streamlit. |
| `agent.py` | The ReAct loop, the tool definitions, the three safety gates, and the offline scripted stories used when there is no API key. |
| `world.py` | The floor itself. The map is an ASCII drawing in this file, and it also hides the quiet zone cells from robots that do not have silent wheels, before A* ever sees the grid. |
| `memory.py` | The SQLite database: the robots, supplies and tasks tables, the seed data, and the function that commits a dispatch. |
| `perception.py` | Runs my Lab 2 filter over the campus floor. It builds the transition and emission models from the map, walks a planned route with noisy sensor readings, and returns the belief for the heatmap. No algorithm lives here, only the translation between the map and the shapes the lab code expects. |
| `test_agent.py` | Seven checks on the safety path. |
| `stress_test.py` | Seventeen edge cases: impossible loads, an empty fleet, a model that invents numbers, malformed replies, runaway loops. |
| `wandb_log.py` | Optional Weights and Biases logging. Off unless `WANDB_ENABLED=1`. |
| `ui_prototype.py`, `UI_Draft.html` | An early Tkinter mock up and a wireframe from the proposal stage. Not used by the demo, kept for history. |
| `presentation/` | Scripts and images used to render map pictures for slides. |

### The algorithms, which are my own lab code

The project rules say old working files can be reused and corrected but not rewritten, so everything in
`core/` is the lab file itself. A diff against the original lab submissions returns only what is listed
here.

| File here | Original lab submission | Path inside that zip | Changes |
|---|---|---|---|
| `core/planner.py` | `Lab1.zip` | `Lab1/planner.py` | none, byte identical |
| `core/environment.py` | `Lab1.zip` | `Lab1/environment.py` | none, byte identical |
| `core/models.py` | `Lab1.zip` | `Lab1/models.py` | none, byte identical |
| `core/hmm_filter.py` | `Aryan_Grang_Lab2.zip` | `Lab2/hmm_filter.py` | my completed Lab 2 submission, used as submitted. It passes the lab's own `hmm_test.py` |
| `core/hmm_environment.py` | `Lab2.zip` | `Lab2/hmm_environment.py` | whitespace only. The tab and space mix stopped it importing |
| `core/verifier.py` | `Lab(Updated).zip` | `Lab/verifier.py` | the two changes the lab asks for: Task 0's capacity comparison (`>=` to `<=`) and Task 4's battery drain constraint |

Patterns I reused rather than files I copied:

| Where | Original lab | How I used it |
|---|---|---|
| `agent.py` loop | `ReAct Lab_Aryan.zip`, `react_loop_lab.py` | the thought, action, observation structure, with this project's tools |
| `agent.py` offline engine | `ReAct Lab_Aryan.zip`, `scripted_llm.py` | the idea of replaying fixed steps when there is no API key |
| `memory.py` | `ReAct Lab_Aryan.zip`, `fake_db.py` | the on-disk SQLite seed and reset pattern |

Simply put, the algorithms are the coursework and the scenario and interface are mine. I used an LLM for
the integration and UI work, which the project guidelines allow.

### Configuration

| File | What it does |
|---|---|
| `requirements.txt` | Every dependency with a pinned version |
| `.env.example` | The template to copy to `.env`. It has no values in it |
| `.gitignore` | Keeps `.env`, the database, the virtual environment, PDFs and the W&B run files out of git |
| `.streamlit/config.toml` | The dark theme |
| `Project Proposal.md` | The full write up of the design |

## How it works

An order goes through six stages and stops at the first one it fails.

1. I type an order in plain English. There is no command format to learn.
2. The LLM decides what to do first and emits one JSON action. Pydantic checks the shape of the
   arguments before anything runs.
3. Tools fetch the facts. The fleet and the stock come out of SQLite, never out of the model's memory.
4. A* plans a route on the corridor grid using the Manhattan heuristic. For a robot without silent
   wheels, the quiet zone cells are removed from the grid before planning, so an illegal route cannot be
   produced in the first place.
5. Z3 checks the plan. There is one integer variable per item meaning "which robot carries this", plus
   constraints for assignment, capacity and battery drain. SAT comes back with the actual assignment.
   UNSAT comes back with diagnostics naming what failed.
6. The commit gate releases it. The dispatch is refused unless it matches Z3's own model and every
   assigned robot has a reachable route. Only then does the database change.

### The three gates

1. **Grounding.** Every robot spec and item weight in the model's payload is compared field by field
   against the database. I added this after watching the model answer a refusal by quoting a battery
   level that was higher than the real one.
2. **SMT.** Z3 has to return SAT. On UNSAT the diagnostics go back to the model, and submitting the same
   rejected payload again is blocked, so a retry has to be genuinely different.
3. **Commit.** As described in stage 6 above.

## Weights and Biases

Run metrics are logged optionally. Install and log in, then set `WANDB_ENABLED=1` in `.env`:

```bash
pip install wandb
wandb login
```

To reproduce the logged runs for all three stories at once:

```bash
python wandb_log.py --demo
```

**Report (open to anyone with the link):**
<https://forge.coreweave.com/wandb/harsh_dixit-sias22-krea-university-top-university-for-li/campuscourier/reports/CampusCourier-verified-dispatch-runs--VmlldzoxODA0OTM4MA?accessToken=z9is6gbvzf5s5u74ndkgk84kmxruqn395mgs732awlyejsb4siqu3pqvwhkrkt5c>

The three runs there are the routine dispatch (one Z3 SAT, dispatched), the overload (one UNSAT then a
replan to SAT, so two verifier attempts for one order), and the low battery trap (one UNSAT and no
dispatch, which is the correct outcome). Each run logs steps taken, tool calls, SAT and UNSAT counts,
gate blocks, schema errors, verifier attempts, whether it dispatched, items assigned, robots used and
total route steps.

## Limitations and safety

Things this version does not do, which I would rather state than let someone discover:

- **The battery rule covers the outbound trip only.** Drain is charged against the load, not against
  route distance, so there is no return reserve. The proposal says the same thing.
- **The quiet zone rule is enforced in the map, not in the solver.** Removing those cells before
  planning means an illegal route cannot be produced, and the tests check it, but Z3 does not prove it.
- **The filter tracks loosely, which is the honest result.** A wall count from 0 to 4 is weak evidence in
  a corridor grid where many cells look alike. It names the exact cell roughly 45 to 70 percent of the
  time and lands within one cell roughly 75 to 80 percent of the time, depending on the route.
- **The belief starts at the known dock, not uniform.** The robot undocks from a known room, so
  `perception.py` seeds the belief there. With a uniform prior, which is the harder "woken up lost"
  problem, exact tracking drops to about 28 percent.
- **Dispatches are handled one at a time.** Robots never contend for the single lane corridor, because
  one verified order is committed before the next begins, and robots move discretely to their
  destination rather than stepping along the route.
- **Routing is deterministic while perception assumes slips.** The planner treats every move as
  succeeding and the Lab 2 transition model does not. That mismatch is why the belief spreads more than
  the simulated robot actually wanders.
- **Offline replay is scripted.** It exercises the real gates, the real solver and the real planner, but
  the coordinator's decisions are fixed. It shows that the checking works, not that the live model
  behaves well.

On the safety side:

- No key is stored in this repository. The code reads it from the environment, `.env.example` carries no
  value, and `.env` is in `.gitignore`.
- The LLM cannot act directly. It can only call declared tools with validated arguments, and nothing
  writes to the database except through the commit gate.
- Refusals are explicit. When a plan is rejected the system says what failed instead of quietly using a
  different robot, so I always find out that my instruction was impossible.
- The verifier is only as good as the constraints written into it. A rule that is not encoded is not
  enforced, which is exactly why the quiet zone limitation above matters.
- This is a simulation. No physical robot is controlled by any of this code.
