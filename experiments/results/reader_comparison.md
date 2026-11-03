# Reader comparison on real photos

Truth = hand labels (foggy, clear) and dataset labels (indian). Photos marked unreadable by the labeller are left out.

| Reader | Set | Photos | Exact | Char. error | Said unreadable | Sure (>=90%) but wrong |
|---|---|---|---|---|---|---|
| Reader A on SAM 3.1 crop | clear | 232 | 70.7% | 6.8% | 0.0% | 17/152 (11.2%) |
| Reader B (Muse Glimmer) | clear | 232 | 90.9% | 1.8% | 0.0% | 21/226 (9.3%) |
| Reader A on SAM 3.1 crop | foggy | 232 | 14.7% | 23.9% | 0.4% | 17/36 (47.2%) |
| Reader B (Muse Glimmer) | foggy | 232 | 37.1% | 55.9% | 54.7% | 0/2 (0.0%) |
| Reader A (open OCR) | indian | 586 | 32.4% | 22.3% | 0.0% | 20/101 (19.8%) |
| Reader B (Muse Glimmer) | indian | 600 | 68.0% | 19.5% | 16.3% | 37/332 (11.1%) |
