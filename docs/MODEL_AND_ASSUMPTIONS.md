# Model and assumptions

## 1. Population and trains

The simulator models one route and one departure date with 2–5 trains. Each train has a berth capacity, fare, and waitlist capacity

\[
W_k = \lfloor \omega C_k \rfloor.
\]

The population is divided into a small number of traveller types. A type provides a share, a valuation for each train, an outside-option value, a plan-change probability, a cancellation-hassle cost, and a valuation-noise scale. Individual valuations are sampled around the type's configured values.

The default values in `configs/default.json` are illustrative assumptions. They are not estimated from booking records.

## 2. Strategies

A traveller chooses a number of trains to request:

- `single`: book the highest-valued train only;
- `hedge2_timely` / `hedge2_late`: book the two highest-valued trains;
- `hedge3_timely` / `hedge3_late`: book the three highest-valued trains, if at least three are configured.

A timely-release traveller cancels a ticket as soon as it is redundant, provided charting has not happened. A late-release traveller holds redundant tickets until charting. The early-release refund is only paid when the release happens before charting and at least the configured number of hours remain before departure (`refund_eligibility_hours_before_departure`, the proposal's \(\tau_r\)). A ticket is redundant when its holder has another active confirmed ticket on a train with at least as high a valuation.

## 3. Event sequence

Events are measured in hours remaining before departure and processed from earliest to latest (larger remaining-hours values happen first).

1. Travellers arrive and request the trains in descending order of their valuations.
2. A request is confirmed if a berth is available. Otherwise, it is placed at the back of the waitlist if the waitlist cap allows it; otherwise the request is refused.
3. A plan-change event may cancel all of a traveller's active tickets.
4. Before charting, cancellation of a confirmed ticket promotes the first active waitlisted ticket on that train. Cancellation of a waitlisted ticket frees a waitlist slot but does not itself create a berth.
5. At chart time, every remaining waitlisted ticket is cancelled and no further waitlist promotions occur.
6. A redundant confirmed ticket released after charting is resold with probability \(\psi\); otherwise its berth remains empty.

The default booking window is 12–72 hours before departure. The chart event can be set to 4, 8, or 10 hours before departure while remaining after all modelled bookings.

## 4. Private utility and welfare

A traveller's private utility is based on the value of the selected confirmed train (net of its fare), or the outside option, minus cancellation fees and hassle, plus any early-release refund. An unused confirmed ticket that is still held at departure incurs its full fare in the private payoff.

Social welfare is kept separate from the railway's financial ledger:

\[
SW = \sum_i \text{gross value}_i
     - \kappa\, (\text{empty berths})
     - \sum_i \text{cancellation hassle}_i.
\]

Fares, cancellation charges, and refunds are treated as transfers between travellers and the railway. In particular, the early-release refund is not counted as a social loss. The refund is still included in traveller utility and the railway transfer ledger, because it changes incentives and the railway's budget.

The model does not currently add the value of passengers who may acquire a berth through post-chart resale. The resale probability only affects whether a released berth is counted as empty. This is a limitation to address in the next iteration if resale is important to the research question.

## 5. Endogenous confirmation and independence diagnostic

No independent confirmation probability is used to decide whether a ticket confirms. A waitlisted ticket is promoted through actual queue events. The empirical promotion rate can be grouped by waitlist position and the number of other hedging travellers requesting the same train.

For comparison, the diagnostic estimates marginal per-train confirmation probabilities from the sample and computes the product-of-marginals estimate

\[
P(\text{at least one confirmation}) \approx 1 - \prod_{k\in S_i}(1-p_k).
\]

It compares this with the observed share of hedgers holding at least one confirmed ticket. This gap indicates how much the independent approximation differs under the simulated strategic congestion.

## 6. Type-level equilibrium

For each traveller type, one representative traveller is tested against candidate strategies while all other travellers follow the current type-level profile. The strategy with the highest average private utility across common random seeds becomes the type's response. Types are updated sequentially until no type changes strategy, a previously visited profile recurs, or the iteration limit is reached.

This is a tractable approximation, not a proof that a unique Nash equilibrium exists. The code reports convergence status, cycles, best-response gaps, and the update history. Repeated initial profiles and larger simulation samples should be used in a final analysis.

## 7. Type-level reinforcement learning

For repeated simulated booking seasons, each type chooses one strategy using an epsilon-greedy rule. Every strategy is tried before exploitation begins. After a season, the type observes the mean private utility of its members and updates the selected strategy's action value with an incremental update:

\[
Q_{g,a} \leftarrow Q_{g,a} + \alpha (R_{g,a} - Q_{g,a}).
\]

Exploration decays toward a configured minimum. This is a type-level multi-armed-bandit learning baseline; it does not maintain a separate Q-table for each individual traveller or explicitly estimate each train's confirmation probability.

## 8. Planner benchmark

The planner benchmark assigns at most one train to each traveller subject to train capacities, choosing the allocation that maximizes gross value relative to each traveller's outside option. It uses full information and ignores waitlist dynamics, cancellation incentives, and the railway's information constraints. It is an omniscient reference point, not a directly implementable policy.

## 9. Important limitations

- No public booking-level dataset is included or assumed.
- Type shares and valuation values are synthetic and need sensitivity analysis.
- Booking times are stylized random arrivals over a fixed window.
- Only plan changes are modelled as stochastic external cancellations; other operational causes are not represented.
- The model has pure type-level strategies; mixed equilibrium strategies are not yet implemented. The learning experiment is a type-level bandit approximation, not individual Q-learning.
- Post-chart resales are represented probabilistically, without an explicit second market or new passenger utility.
- The exact Indian Railways cancellation rules can vary by ticket class and time; the configurable fees in the default file are model inputs, not a live policy implementation.
