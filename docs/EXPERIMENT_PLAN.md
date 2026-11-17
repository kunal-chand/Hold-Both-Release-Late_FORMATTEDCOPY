# Experiment plan

## Phase A — Verify simulator mechanics

- Test berth capacity and waitlist capacity boundaries.
- Test promotion after a pre-chart confirmed-ticket cancellation.
- Test that no promotion happens after charting.
- Test that timely release frees a redundant waitlist slot before charting.
- Test that late release does not free that slot before charting.
- Test that refunds affect private utility and the transfer ledger but not social welfare directly.

## Phase B — Fixed-strategy baselines

Compare:

1. Nobody hedges (`single`).
2. Everyone hedges on two trains and releases redundancies timely.
3. Everyone hedges on two trains and releases redundancies late.
4. Everyone hedges on three trains and releases redundancies late.
5. An omniscient capacity-constrained planner benchmark.

Report mean travel probability, empty-berth share, refused requests, redundant waitlist slots at chart, social welfare, refunds paid, and railway transfers. Use multiple seeds and later add confidence intervals.

## Phase C — Advisor point 1

- Vary the share of travellers who hedge.
- Estimate waitlist promotion probability by waitlist position and the number of other hedging travellers competing for that train.
- Compare actual joint confirmation with the product-of-marginals independence approximation.
- Include a plot and discuss whether the gap grows with congestion.

## Phase D — Type-level equilibrium

- Start from all-single, all-hedge-timely, and all-hedge-late profiles.
- Use common seed sets to compare candidate private payoffs.
- Report the final strategy for each type, convergence/cycle status, and best-response gaps.
- Re-run with different population sizes and type definitions.

## Phase E — Learning over repeated booking seasons

- Each traveller type explores the available strategy actions over repeated seasons.
- Update the selected action's estimated private utility using an incremental value update.
- Compare the learned type-level policy with the full-information best-response equilibrium.
- Vary exploration and learning-rate parameters; report learning curves and final action values.

This initial implementation aggregates rewards by type. It is a tractable learning baseline, not an individual-level Q-learning model.

## Phase F — Railway policy comparison

Sweep:

- Waitlist cap fraction \(\omega\), including the 0.25 reference value.
- Early-release refund \(\beta\), including zero.
- Chart time \(\tau_c\), including 4, 8, and 10 hours before departure.

The stronger policy experiment recomputes the type-level equilibrium for every policy tuple. The cheaper initial experiment holds the population at `hedge2_late` to isolate how policy rules affect a fixed behaviour profile.

Report social welfare and operational outcomes separately from the financial transfer ledger. A policy should not be called cheaper or better solely because it pays fewer refunds; refunds are a transfer, while their incentive and budget effects remain relevant.

## Phase G — Robustness and presentation

- Increase Monte Carlo runs and calculate uncertainty intervals.
- Vary type shares, valuations, plan-change probabilities, and resale probability.
- Test multiple equilibrium starts and report multiple equilibria or cycles if found.
- Clearly separate calibrated facts, synthetic assumptions, and conclusions that are conditional on the model.
