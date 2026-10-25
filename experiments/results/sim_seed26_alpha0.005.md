Target α = 0.005 wrong charges per passage, per group. 20/24 groups certified (a group needs ≥ 199 calibration passages).

| Method | Wrong-charge rate | Automated | Held | To human | Worst group (rate) | Groups over α |
|---|---|---|---|---|---|---|
| naive biller (today) | 6.1912% | 100.0% | 0.0% | 0.0% | two_line/night/rain (7.391%) | 24/24 |
| single threshold (0.9) | 4.2311% | 67.6% | 0.0% | 32.4% | high_security/day/fog (5.476%) | 12/24 |
| fused, fixed cut-off | 1.2963% | 90.5% | 0.0% | 9.5% | high_security/day/rain (2.047%) | 15/24 |
| OCR only + controller | 0.4425% | 29.3% | 64.0% | 6.6% | two_line/day/rain (0.901%) | 7/24 |
| Muse only + controller | 0.4738% | 89.2% | 5.9% | 4.9% | two_line/day/fog (1.141%) | 6/24 |
| TULA, hand-set score | 0.5260% | 87.3% | 7.6% | 5.1% | high_security/day/rain (1.005%) | 9/24 |
| TULA (fused + controller) | 0.4613% | 89.4% | 6.2% | 4.4% | high_security/day/rain (1.005%) | 7/24 |
| TULA, 90% confidence | 0.2964% | 83.5% | 11.6% | 4.9% | high_security/day/rain (0.575%) | 1/24 |
