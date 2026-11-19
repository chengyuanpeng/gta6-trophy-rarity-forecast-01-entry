# Step 1 findings

## Task and input

The program is called once per case. It reads UTF-8 JSON from every `*.in` file in `MAKEFUN_INPUT_DIR` (default `/input/`), in filename order. The case schema is `makefun/gta6-trophies-case/v1`. Relevant fields are `id`, `horizon_minutes`, `levels` (`[0.05, 0.25, 0.5, 0.75, 0.95]`), `trophies` (55 trophy records in id order), and `history` (valid page reads oldest first). Each history row carries `players_tracked` and a `rates` array aligned with the trophies; missing rates can be `null`. The practice cases are p00 (03:00Z checkpoint) and p01 (03:30Z); each forecasts 90 minutes ahead across the first Exophase refresh. The tracked-player denominator can change between page refreshes.

## Output and scoring

For each input `<id>.in`, write `<id>.out` under `MAKEFUN_OUTPUT_DIR` (default `/output/`). It must be UTF-8 JSON of the form `{"trophies":[{"id":1,"q":[q05,q25,q50,q75,q95]}, ...]}`. Include each case trophy exactly once, with five finite, non-decreasing percentages from 0 to 100 and no extra row keys. Maximum size is 65,536 bytes. The entry must be deterministic, Python 3.13 standard-library-only, offline, and finish within 8 seconds per run.

The sealed scorer evaluates each trophy and each quantile against the target read. It clamps rates to 0.01–99.99%, compares their logits, applies pinball loss `2 * max(tau*d, (tau-1)*d)`, and reports mean loss over all trophy/quantile items (lower is better). Invalid output is penalized as five quantiles equal to the last observed rate and makes the entry ineligible for prizes. The dev harness runs each case twice and checks deterministic output before scoring.

## Starter baseline and harness findings

The kit's `starter/main.py` is byte-for-byte identical to this repository's initial `main.py`. I ran the kit starter with the practice inputs and confirmed that it emits valid JSON with 55 unique trophy rows for both p00 and p01. The starter carries the last observed rate forward as its median and uses a fixed random-walk spread of `0.5 * sqrt(horizon_minutes / 1440)` logits with normal quantile multipliers `[-1.645, -0.674, 0, 0.674, 1.645]`.

The authoritative rules report the starter/house persistence baseline's practice performance as approximately **1.51 mean pinball loss**, **0.68 percentage-point typical median miss**, **0% 90% coverage**, with every case valid. Its miss is due to the unseen refresh moving all scored rates outside the narrow 90-minute forecast band. This is the published baseline figure, not a locally recomputed score.

I unpacked `harness/harness-src.tar.gz` to `/tmp/gta6-harness` and invoked the kit's `makefun grade-local --kit ... --bot ... --driver process` dev harness command. The command refused to grade locally: the kit does not publish its scorer or practice reference data, and reports that program/v1 scoring is server-only. The starter was still run directly with the same input/output directory interface described by the kit. The available local Python is 3.12.3, so the direct smoke run also did not exercise the required Python 3.13 grader runtime.

No forecasting model has been written in this step.

# Step 3 — rolling validation and spread calibration

## Backtest setup

The only recorded histories available in the kit are p00 and p01. Both are flat page snapshots: 7 and 8 reads respectively, with every tracked-player count at 638 and all 55 rates identical in every read. The practice target answers are not included in the kit, so their post-refresh rates cannot be scored locally. I therefore used a strictly historical rolling backtest: for each case, fit from the first two reads through the read before a later recorded read, then forecast that later read. This yields 5 later cut points in p00 and 6 in p01, or 605 trophy/cut-point observations. Since each observed rate stayed exactly at the preceding read, the current model's fitted center also stays at that rate.

## Tuning results

Tuned a shared normal-logit quantile spread across the rolling predictions, keeping the growth model unchanged. Mean logit pinball losses were:

| Spread (logits) | Mean pinball loss |
| ---: | ---: |
| 0.00 | **0.000000** |
| 0.25 | 0.050173 |
| 0.50 | 0.100346 |
| 0.75 | 0.150519 |
| 1.00 | 0.200692 |

The zero spread won this available-data backtest, so `main.py` now emits five equal quantiles around the existing pooled-growth median. The historical validation only measures unchanged snapshots; it contains no evidence about uncertainty across an Exophase refresh and does not validate the median growth model on a changing series. In particular, the kit rules say practice answers cross the first refresh, but the exact answer rates are unavailable here. Thus these are genuine scores on recorded later moments, not a claim of refresh-calibrated uncertainty or a practice score. With no changing observations available, no honest alternative spread can be estimated from this kit.

# Step 4 — final entry

Added the required live competition, rank and reward badges to `README.md`, linking them to the make.fun competition page and using this repository's owner and name. The README describes the forecast and how to run it with the input/output environment variables.

Ran the official local `grade-local` command again. It returned the kit's program/v1 limitation: the scorer and reference data are not published, so scoring is server-only and no local dev score is available.

Ran `main.py` twice on both supplied practice cases with separate output directories. The outputs matched byte for byte for p00 and p01. Both were valid JSON with 55 trophy rows and five finite, in-range, non-decreasing quantiles per row.

# Step 2 — pooled growth model v1

## Design

`main.py` now fits each trophy's earned-player and unearned-player counts separately on the log of elapsed time since launch. Earned and unearned counts are approximated from `players_tracked × rate` and `players_tracked × (1 − rate)`, so a changing tracked-player denominator is represented directly. The count trends use recency-weighted least squares. Per-trophy slopes are shrunk toward the median slopes of trophies with the same tier and current earn-rate band (with tier-level fallback), making the forecast less sensitive to short or rounded histories. It projects the tracked-player denominator from its recent log-time trend, then converts projected earned/unearned counts back to a rate. Quantiles are centered on the projected log-odds and use a horizon-scaled logistic-normal spread (`0.34 + 0.42 × sqrt(days)`).

## Verification and score

The requested `makefun grade-local` command was run against the authoritative kit with `--driver process`. The kit refused to score: this is a program/v1 competition whose scorer and reference data are server-only and are not published in the kit. Therefore **no dev score is available locally**; there is no honest pinball score to record from the available files. The harness limitation is documented in the rules and is not a model score.

As an output smoke check, v1 ran on both supplied practice cases and produced 55 unique trophy rows each. All q arrays had five finite values strictly between 0 and 100 in non-decreasing order. The forecast median stayed at the last rate in those practice cases because every pre-checkpoint history is unchanged; those cases cross the first refresh, so this says nothing about v1's target accuracy. Python 3.12.3 was used locally; the grader runtime specified by the kit is Python 3.13.
