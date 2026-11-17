# Advisor feedback implementation log

## 1. Confirmation probabilities depend on other travellers

**Feedback:** The proposal's equations treat train confirmation chances as fixed and unrelated across trains, but the simulator's chances depend on how many others hedge.

**Implementation:** The simulator does not draw a fixed `p_k` for a ticket. A ticket enters a berth or an ordered waitlist according to the queue at its booking time. It is promoted only when a confirmed ticket on that train is cancelled before charting and it reaches the front of the queue. Other travellers' booking and release choices therefore affect the ticket's realised confirmation chance.

**Diagnostic:** Each simulation records waitlisted ticket outcomes, initial waitlist position, and the number of other hedging travellers who requested the same train. `diagnose` aggregates the empirical promotion probability by this congestion measure. `independence_diagnostic` compares the observed probability that a hedger has at least one confirmed ticket against `1 - product(1 - p_k)`, where the marginal `p_k` values are estimated from the same simulated sample.

**Interpretation caution:** The marginal-probability product is a deliberately simplified benchmark. The observed difference is evidence that the independence approximation is inaccurate for the modelled population; it is not a claim about measured railway data.

## 2. Refunds are transfers

**Feedback:** A refund moves money from the railway to a traveller and should be reported separately from societal loss.

**Implementation:** `social_welfare` is calculated as gross travel value (or outside-option value) minus empty-berth penalties and cancellation hassle. It does not subtract fares, cancellation charges, or refunds. Refunds are separately reported as `refunds_paid`; fare and cancellation receipts are also reported through the financial metrics. Traveller private utility still includes the refund because it affects individual incentives.

## 3. Group travellers into types

**Feedback:** A few traveller types can keep equilibrium computation manageable.

**Implementation:** The default config defines three types with different route valuations. Every member of a type follows the same strategy in a profile. The best-response calculation evaluates one representative member's unilateral deviation against the other travellers' current profile, then updates the strategy assigned to the type.

**Approximation:** This is a type-level representative-agent / mean-field approximation. It is not an exact enumeration of every traveller's strategy profile. Results should be checked against different type definitions, population sizes, and equilibrium initializations.
