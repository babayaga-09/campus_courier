# Project Proposal: CampusCourier

**Track B (own idea), Aryan Grang**

## What is your system's story?

My system is a small delivery service that runs on one floor of the academic block. Three courier
robots carry things like projectors, lab kits, water cases, whiteboards and marker boxes from the
Supply Room to whichever room has asked for them. Staff send their orders in plain language, the way
they would message a person, for example "get 2 projectors and a lab kit to Studio 3 before the 2pm
class". An LLM reads that sentence and turns it into a structured plan, which means deciding which
robot carries which item and by which route.

The LLM runs as a ReAct loop, so each turn is a thought, then an action, then an observation. The
actions are real tools and not descriptions of tools: it reads the fleet from the database, costs a
route with A*, and asks the solver whether the plan it has in mind is actually legal. Nothing the
model says is taken on trust. Before a plan reaches the robots it has to be proved feasible by Z3,
and if the proof fails the model is told which rule it broke, so it can propose a different plan
instead of simply being refused. Usually that means a lighter load, a different robot, or a different
room.

The floor itself is a grid of corridors connecting the Supply Room to three rooms. There is a stretch
that has just been mopped where the wheels slip, a quiet zone in the corridor outside the exam hall,
and Corridor B, which is single lane and happens to be the only way into Studio 3.

## What are the hard safety rules?

I am writing the checks as constraints for an SMT solver (Z3) rather than as if/else statements I
have written by hand. The idea is that the rules are then decided as mathematics, so a confident LLM
cannot talk its way past them. Before any dispatch, the solver has to agree that:

1. **Assignment.** Every requested item goes to exactly one robot, and a robot below its minimum
   battery (20%) is not given anything to carry.
2. **Capacity.** The load on a robot stays within its rated capacity. Atlas can take 30 kg, Comet
   20 kg and Pixel 10 kg.
3. **Battery drain.** The battery left after the trip must still clear the minimum, which is
   `battery - drain_rate * load >= min_battery`. This matters because a robot can be strong enough to
   lift a load and still not have the charge to carry it.
4. **Quiet zone.** A robot without silent wheels may not be routed through the corridor outside the
   exam hall. I enforce this in the map rather than in the prompt, because those cells are removed
   from the grid before A* even plans, so an illegal route cannot be produced in the first place.
5. **Return reserve.** There has to be enough battery to reach the room and get back to the Supply
   Room.

When Z3 returns UNSAT it also reports which constraint failed, so the model has something concrete to
replan around, and resubmitting a plan that has already been rejected is blocked. This is the
verifier loop argument from the course. If a single attempt is correct with probability p, and the
checker never passes a bad plan, then k attempts give 1 - (1 - p)^k, which climbs quite quickly. Thus
an unreliable planner behind a sound checker is still a safe system. However, the opposite does not
hold: no number of retries can fix a checker that accepts bad plans, which is why I am using Z3 here
and not a second LLM.

## What is noisy in your world?

A robot cannot simply be asked where it is. There is no indoor GPS, and one stretch of corridor looks
much like another. All it has is a bump and proximity count of how many of its four neighbouring
cells are wall, so a number from 0 to 4, and that count is only correct about 80% of the time.
Movement is unreliable as well, because on the mopped stretch a robot goes where it intended 80% of
the time and slips sideways the other 20%.

As a result the true position is a hidden state, and the sensible thing is to keep a belief over
every corridor cell instead of one guess. This is the HMM forward filter from Lab 2: predict using
the movement model, then update by reweighting each cell with the likelihood of the wall count that
came in, then normalise so the belief stays a probability distribution. The dashboard draws that
belief as a heatmap, which should make it visible that the belief spreads out when the robot moves
and sharpens again when a reading arrives.

## How do the robots plan and learn?

Routing is A* on the corridor grid with the Manhattan heuristic. Movement is 4 way and each move
costs 1, so Manhattan never overestimates the real remaining cost, which makes it admissible and
means the route A* returns is still the shortest one. That matters more here than it might look,
because battery is spent per step, so the battery constraint above is only meaningful if the step
count it is given is the true one.

The mopped floor makes movement stochastic, and I think that makes the pilot an MDP rather than a
search problem. The states are cells, the actions are the four moves, and the transition
probabilities are the 80/10/10 slip. I plan to solve it with value iteration, as in Lab 3, to get a
careful policy, and then train a Q-learning policy on a reward that pays for speed. The pilot can
then be switched between careful and fast, and the difference should be visible on the map.

## Where does conflict happen?

Conflict happens in Corridor B, which is single lane and is the only way into Studio 3. When two
robots arrive at it together, each has to choose go or yield. If both go they block each other, and
if both yield the class ends up waiting for no reason. Rather than hard coding something like "Atlas
always wins", I would like the robots to learn a right of way convention by playing this game against
each other, using self play Q-learning, with the more urgent delivery taking priority and remaining
battery as the tie break.

## What does the system remember?

The short term memory is just the LLM's context for the order it is working on, and it disappears
when the run ends. Everything that has to survive lives in a SQLite database which the agent reads
and writes through tools, so the fleet, what is left in the store, and every dispatch that was
approved. Keeping the state outside the model is also what makes the grounding check possible,
because the verifier can compare the model's numbers against the database rather than against
whatever the model claims to remember.

## What interface will you build?

A Streamlit dashboard, mainly because a terminal log cannot show a map, a probability cloud and a
rejected plan at the same time. It shows:

- the floor map, with walls, corridors, the mopped stretch and the quiet zone, and each robot's
  position with its planned A* route drawn on it
- the HMM belief heatmap next to the true position, so that drift and correction are both visible
- the verdict for the current order, so either SAT with the assignment, or UNSAT with the rule that
  failed and the replan that followed it
- the coordinator's reasoning log, step by step, tagged by which gate passed or blocked it
- the database itself, meaning the fleet, the remaining stock and the log of dispatched tasks

## Why this scenario

I chose a campus delivery floor because indoors there genuinely is no
GPS, so the noisy sensor and the filter are doing real work. A quiet zone outside an exam hall is a
hard constraint, and it is not the kind of thing that should depend on a model's judgement, which is
what the SMT verifier is for. A single lane corridor is a real bottleneck, so the conflict rule has
something to resolve. And a delivery has a deadline, so "careful but late" and "fast but stuck" are
both wrong answers, which is the trade off I want the adaptive pilot to learn.

## A note on the verifier

There are 3 verifications at each order an user inputs: 

1. **Grounding.** Every robot spec and item weight in the model's proposal has to match the database.
   Without this the model can "fix" a rejection by quietly inventing a fuller battery.
2. **SMT.** Z3 has to return SAT. On UNSAT the diagnostics go back to the model, and an identical
   resubmission is refused.
3. **Commit.** The dispatch is refused unless it matches Z3's own model and every assigned robot has
   a reachable route.

Everything else, such as dashboard polish, how clever the learned policies get, and how many
scenarios I script, can be cut back if I run short of time. I built and tested the verifier on its
own first, so that the rest of the system has something trustworthy to sit on.

## Which coursework each layer reuses

Per the project guidelines the algorithms are my existing lab code, corrected but not rewritten.
Everything in `core/` is the lab file itself, and the scenario lives outside it, in the integration
and UI layer.

| Layer | Coursework reused | State |
|---|---|---|
| Route planning | Lab 1: `planner.py` (A*), `environment.py`, `models.py` | used unchanged |
| Perception | Lab 2: `hmm_filter.py`, `hmm_environment.py` | `hmm_environment.py` needed a whitespace fix before it would import. `predict()` and `update()` are the lab's own TODOs and are still to be completed |
| Safety verifier | SMT lab: `verifier.py` | two corrections. Task 0's capacity direction (`>=` to `<=`) and Task 4's battery drain constraint, which the lab leaves as a TODO |
| Adaptive pilot | Lab 3 value iteration, and the Q-learning lab | planned |
| Corridor B conflict | Q-learning lab, run as self play | planned |
| LLM coordinator | ReAct lab: `react_loop_lab.py` | loop adapted to this project's tools |
| Memory | ReAct lab: the `fake_db.py` pattern | adapted to SQLite for this project |
| Dashboard, map and scenario | new work | this is where I used LLM assistance, as the guidelines allow for integration and UI |

Simply put, no lab algorithm has been substantially reworked, so I do not think consent is needed
under guideline 2. A diff of `core/` against the original lab files returns only the corrections
listed above.
