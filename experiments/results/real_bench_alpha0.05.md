# TULA on real photos

Real photos: 1050 ({'clear': 232, 'foggy': 232, 'indian': 586}), alpha = 5%, 200 random splits (mean over splits)

| Method | Wrong charges | Charged automatically | Sent to human | Wrong: clear | Wrong: foggy | Wrong: indian |
|---|---|---|---|---|---|---|
| Today's biller (trust tag, else plate) | 17.00% (±0.86%) | 100.0% | 0.0% | 14.14% | 18.88% | 17.38% |
| One threshold: Reader A >= 0.9 | 3.70% (±0.53%) | 27.5% | 72.5% | 8.41% | 2.46% | 2.33% |
| One threshold: Glimmer >= 0.9 | 6.65% (±0.58%) | 52.2% | 47.8% | 12.23% | 0.11% | 7.03% |
| Fused score, fixed cut-off 0.3 | 2.64% (±0.38%) | 56.9% | 43.1% | 2.29% | 0.19% | 3.75% |
| Reader A only + controller | 4.51% (±1.22%) | 47.8% | 0.8% | 4.16% | 4.53% | 4.65% |
| Glimmer only + controller | 4.17% (±1.09%) | 84.6% | 0.2% | 3.52% | 3.96% | 4.50% |
| TULA (both readers + controller) | 4.26% (±1.13%) | 85.8% | 0.6% | 3.61% | 3.95% | 4.64% |
| TULA, 90% confidence mode | 2.50% (±0.83%) | 79.3% | 0.8% | 1.47% | 1.89% | 3.14% |

Reader independence (share of photos each reader gets wrong):

- clear: A wrong 29%, Glimmer wrong 9%, both wrong 9% (if independent: 3%)
- foggy: A wrong 85%, Glimmer wrong 63%, both wrong 56% (if independent: 54%)
- indian: A wrong 68%, Glimmer wrong 33%, both wrong 28% (if independent: 22%)

Review budget: stricter promise, more work for humans (held or reviewed):

| Promise | Wrong charges | Charged automatically | Held or reviewed | Auto: clear | Auto: foggy | Auto: indian |
|---|---|---|---|---|---|---|
| 1.0% | 0.53% | 30.2% | 69.8% | 21% | 14% | 41% |
| 2.0% | 1.28% | 63.3% | 36.7% | 82% | 59% | 58% |
| 3.0% | 2.31% | 78.2% | 21.8% | 86% | 76% | 76% |
| 5.0% | 4.40% | 85.7% | 14.3% | 89% | 84% | 85% |
| 7.5% | 6.96% | 90.4% | 9.6% | 92% | 88% | 91% |
| 10.0% | 9.57% | 93.8% | 6.2% | 95% | 91% | 95% |

Red team: attackers take a share of traffic after calibration (clones + swapped tags):

| Attacker share | Bound (promise + share) | TULA wrong charges | TULA charged automatically | Today's biller wrong |
|---|---|---|---|---|
| 0% | 5% | 4.79% | 86.4% | 17.03% |
| 5% | 10% | 6.59% | 84.3% | 20.98% |
| 10% | 15% | 8.10% | 81.7% | 25.18% |
| 20% | 25% | 11.46% | 76.5% | 33.88% |
| 30% | 35% | 14.63% | 71.7% | 41.98% |
| 5% (look-alike clones) | 10% | 6.79% | 84.3% | 21.04% |
| 10% (look-alike clones) | 15% | 8.24% | 82.1% | 24.94% |
