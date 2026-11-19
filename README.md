# GTA VI Trophy Rarity Forecast

[![Competition](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![Rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/chengyuanpeng/gta6-trophy-rarity-forecast-01-entry/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![Reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/chengyuanpeng/gta6-trophy-rarity-forecast-01-entry/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)

This entry forecasts five quantiles for every GTA VI PS5 trophy's Exophase earn rate. It fits pooled trends in estimated earned and unearned player counts, accounting for growth in the tracked-player denominator.

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The program uses only the Python standard library, reads each `*.in` case in the input directory, and writes its corresponding `*.out` forecast.
