# Hold Both, Release Late? — Waitlist Hedging on Indian Railways

**CS329 · Group 36 · Multi-Agent Systems project**

A simulation study of strategic waitlist hedging on multiple trains, the incentives to release redundant tickets, and the effect of railway policies such as waitlist caps, early-release refunds, and chart preparation time.

The repository is organized as a small Python package with a command-line interface, configurable model inputs, tests, experiment outputs, and plots. The linked example repository could not be fetched for detailed inspection in this session, so this uses a conventional modular research-project layout; no code is copied from that example.

> **Research prototype, not an empirical forecast.** The default population, valuations, fares, cancellation assumptions, and plan-change probabilities are synthetic starting values. They are exposed in `configs/default.json` so the group can calibrate and run sensitivity analyses. Outputs should be described as results of this model, not as measured Indian Railways outcomes.

## Research questions

1. Does hedging improve each traveller's chance of travelling while worsening outcomes for the population as a whole?
2. How much of the harm is caused by holding multiple tickets, and how much by retaining redundant tickets until charting?
3. Do tighter waitlist caps reduce congestion, or simply cause more booking attempts to be refused?
4. What early-release refund makes timely cancellation individually attractive, and what does that policy cost the railway?
5. How does moving chart preparation to 4, 8, or 10 hours before departure change the opportunity to promote waitlisted passengers?

## Advisor feedback translated into the implementation

| Advisor point | What the repository does |
|---|---|
| Confirmation chances are not fixed or independent when travellers compete for the same trains. | Waitlist confirmations arise from the simulated queue. A waitlisted ticket is promoted only when a confirmed ticket ahead of it is cancelled before charting. The diagnostics record confirmation rates by the number of other hedging travellers booking the same train and compare actual joint confirmation with an independence approximation. |
| A refund is a transfer, not a loss to society. | Refunds are included in traveller utility and reported as `refunds_paid` / railway transfers. They are **not subtracted** in `social_welfare`. Fares and cancellation charges are also treated as transfers. |
| Group travellers into a few types to keep equilibrium manageable. | The default population has three traveller types with different train valuations. Each type uses one common strategy in the type-level best-response computation. |

## What is implemented

- A discrete-event simulator for 2–5 trains, berth capacity, capped ordered waitlists, bookings, plan changes, cancellations, promotions, charting, and post-chart resale.
- Traveller strategies: book one train, or hedge across 2+ trains and release redundant tickets either **timely** or **late**.
- A type-level best-response loop that lets one representative traveller of a type deviate while the rest of the population follows the current profile.
- A type-level reinforcement-learning experiment: each type explores hedging / release strategies over repeated simulated booking seasons and updates action values from observed private utility.
- A planner benchmark that computes a capacity-constrained assignment maximizing the population's gross value over outside options. It is an omniscient upper reference, not a feasible railway policy.
- Baseline comparisons, a policy grid for waitlist cap / refund / chart time, congestion-dependent confirmation diagnostics, CSV/JSON outputs, and plots.

## Quick start

### Windows PowerShell

```powershell
cd Hold-Both-Release-Late_FORMATTEDCOPY
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### Linux / WSL

```bash
cd Hold-Both-Release-Late_FORMATTEDCOPY
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

If you only want to run the model and do not need tests or linting, use `python -m pip install -r requirements.txt` instead of the editable install.

## Run experiments

All commands are run from the repository root.

### 1. One simulation

```bash
python -m waitlist_hedging simulate --strategy hedge2_late --seed 329
```

Writes `outputs/single_run.json` and prints the main metrics.

### 2. Fixed-strategy baselines

```bash
python -m waitlist_hedging scenarios --runs 30
```

Compares `no_hedging`, `all_hedge2_timely`, `all_hedge2_late`, and `all_hedge3_late`, plus the `planner_optimum` benchmark. Writes scenario CSV/JSON, an independence diagnostic, and plots under `outputs/`.

### 3. Type-level equilibrium

```bash
python -m waitlist_hedging equilibrium --runs 6 --max-iterations 12
```

Starts from the all-single-ticket profile and repeatedly computes type-level best responses. Results are saved in `outputs/equilibrium.json` and `outputs/equilibrium_history.csv`.

### 4. Advisor point 1: endogenous confirmation diagnostics

```bash
python -m waitlist_hedging diagnose --runs 50
```

Produces:

- `outputs/confirmation_by_congestion.csv`
- `outputs/confirmation_by_waitlist_position.csv`
- `outputs/independence_diagnostic.json`
- `outputs/figures/confirmation_by_congestion.png`

The product-of-marginals calculation is a diagnostic baseline, not the model's confirmation mechanism.

### 5. Reinforcement learning

```bash
python -m waitlist_hedging learn --seasons 100
```

Each traveller type explores the available strategies, observes the mean private utility for that type, and updates the chosen strategy's action value with an incremental learning rule. Results are saved in `outputs/learning_history.csv`, `outputs/learned_policy.json`, and `outputs/figures/learning_reward_by_season.png`. This is a type-level learning approximation rather than a separate Q-table for every individual.

### 6. Policy comparison

```bash
python -m waitlist_hedging sweep --runs 3
```

Runs the fixed `hedge2_late` population across a grid of cap fractions, refunds, and chart times. To recompute the type-level equilibrium separately for every policy combination, use:

```bash
python -m waitlist_hedging sweep --runs 3 --solve-equilibrium
```

The equilibrium sweep is more computationally expensive.

### 7. Main experiment suite

```bash
python -m waitlist_hedging all --runs 30 --equilibrium-runs 4 --diagnostic-runs 30
```

Add `--with-learning` to include a 60-season learning run.

To include the fixed-strategy policy grid:

```bash
python -m waitlist_hedging all --runs 30 --equilibrium-runs 4 --diagnostic-runs 30 --with-sweep
```

For a full equilibrium re-computation at each policy setting, add `--solve-sweep-equilibrium` as well.

## Configuration

Edit `configs/default.json`, then pass it explicitly:

```bash
python -m waitlist_hedging --config configs/default.json scenarios --runs 50
```

Important parameters:

| Parameter | Meaning |
|---|---|
| `trains[].capacity` | Number of berths on each train |
| `trains[].fare` | Fare used in traveller private utility |
| `traveller_types[].share` | Population share of a type |
| `traveller_types[].values` | Type's valuations for each train, in train-list order |
| `traveller_types[].outside_option` | Value of not taking one of the simulated trains |
| `traveller_types[].plan_change_probability` | Probability of a traveller's plan changing during the simulated booking window |
| `waitlist_cap_fraction` | Waitlist capacity as a fraction of train capacity; cap is floored to an integer |
| `early_release_refund` | Refund amount for an eligible redundant ticket released before charting |
| `refund_eligibility_hours_before_departure` | Minimum hours that must remain before departure for an early-release refund to apply (the proposal's `τ_r` threshold) |
| `chart_hours_before_departure` | Chart event time; compare 4, 8, and 10 hours |
| `resale_probability` | Chance that a confirmed berth released after charting is resold |
| `empty_berth_cost` | Model penalty for an empty berth in social welfare |

The default booking window is 12–72 hours before departure, ensuring the configured 4-, 8-, and 10-hour chart events occur after the booking window.

## Output metrics

- `travel_probability`: share of travellers with at least one confirmed and selected train.
- `empty_berth_share`: empty berths divided by total capacity, including berths not resold after a post-chart cancellation.
- `travellers_turned_away`: travellers with at least one refused request and no confirmed travel option.
- `redundant_waitlist_slot_share`: redundant waitlisted tickets still occupying slots at chart time divided by total waitlist-slot capacity.
- `waitlist_confirmation_rate`: share of tickets that entered a waitlist and were promoted to confirmed before charting.
- `refunds_paid`: monetary transfers from the railway to travellers for eligible early releases.
- `social_welfare`: gross travel / outside-option value minus empty-berth penalties and cancellation hassle. Monetary transfers (fares, cancellation charges, and refunds) are excluded from this measure.
- `railway_net_transfers`: simulated fare and cancellation-charge receipts minus early-release refunds. This is a financial ledger metric, not social welfare.

## Tests

```bash
pytest -q
```

## Repository structure

```text
Hold-Both-Release-Late_FORMATTEDCOPY/
├── configs/
│   └── default.json
├── docs/
│   ├── ADVISOR_FEEDBACK.md
│   ├── EXPERIMENT_PLAN.md
│   └── MODEL_AND_ASSUMPTIONS.md
├── outputs/
├── src/waitlist_hedging/
│   ├── config.py
│   ├── diagnostics.py
│   ├── equilibrium.py
│   ├── experiments.py
│   ├── learning.py
│   ├── models.py
│   ├── planner.py
│   ├── reporting.py
│   ├── simulator.py
│   ├── strategies.py
│   └── visualization.py
├── tests/
├── .gitignore
├── LICENSE
├── pyproject.toml
├── README.md
└── requirements.txt
```

## Upload to GitHub

Create an empty GitHub repository named **`Hold-Both-Release-Late_FORMATTEDCOPY`**, then run:

```bash
git init
git add .
git commit -m "Initial waitlist hedging simulator"
git branch -M main
git remote add origin https://github.com/<your-username>/Hold-Both-Release-Late_FORMATTEDCOPY.git
git push -u origin main
```

Replace `<your-username>` with the GitHub account that will own the repository.

## Next research steps

1. Replace synthetic demand and valuation parameters with a documented calibration range from credible public sources or a sensitivity-analysis design.
2. Validate the queue / chart / cancellation transitions against hand-worked edge cases.
3. Run repeated seeds and report uncertainty intervals, not only averages.
4. Test alternate type definitions, mixed strategy populations, and multiple equilibrium initializations.
5. Interpret policy rankings only after the above robustness checks.

## License

MIT. See [LICENSE](LICENSE).
