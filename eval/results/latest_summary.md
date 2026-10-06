# Evaluation Results — 2026-10-06_19-00-09

**Total cases:** 33  |  **Passed:** 13 (39.4%)  |  **Timestamp:** 2026-10-06_19-00-09

## Bars (§9)

| Bar | Target | Actual | Status |
|-----|--------|--------|--------|
| Restricted content leaks | 0 | 0 | ✅ PASS |
| Wrongful refusals | 0 | 0 | ✅ PASS |
| Disposition & routing accuracy | ≥90% | 100.0% (30/30) | ✅ PASS |
| Planned steps executed | 100% | 37.5% (12/32) | ❌ FAIL |
| p95 latency | ≤8s | 1.51s | ✅ PASS |

## Per-Case Results

| ID | Category | Expected Disp. | Actual Disp. | Checks Pass | Elapsed |
|----|----------|----------------|--------------|-------------|---------|
| A01 | A | answered | answered | ✅ | 1.928s |
| A02 | A | answered | answered | ✅ | 1.508s |
| A03 | A | answered | answered | ✅ | 1.299s |
| B01 | B | refused | refused | ✅ | 0.0s |
| B02 | B | refused | refused | ✅ | 0.0s |
| B03 | B | refused | refused | ✅ | 0.0s |
| B04 | B | refused | refused | ✅ | 0.0s |
| B05 | B | answered | answered | ✅ | 0.648s |
| B06 | B | answered | answered | ✅ | 0.663s |
| C01 | C | action_decided | action_decided | ❌ | 0.752s |
| C02 | C | action_decided | action_decided | ❌ | 0.583s |
| C03 | C | refused | refused | ❌ | 0.0s |
| D01 | D | duplicate | duplicate | ❌ | 0.689s |
| D02 | D | duplicate | duplicate | ❌ | 0.583s |
| D03 | D | duplicate | duplicate | ❌ | 0.626s |
| D04 | D | duplicate | duplicate | ❌ | 0.596s |
| D05 | D | duplicate | duplicate | ❌ | 0.75s |
| E01 | E | answered | answered | ❌ | 0.0s |
| E02 | E | answered | answered | ❌ | 0.0s |
| VPN01 | VPN | answered | answered | ✅ | 0.0s |
| VPN02 | VPN | answered | answered | ✅ | 0.0s |
| REF01 | Refused | refused | refused | ❌ | 0.0s |
| REF02 | Refused | action_decided | action_decided | ❌ | 0.501s |
| REF03 | Refused | refused | refused | ❌ | 0.0s |
| REF04 | Refused | refused | refused | ❌ | 0.0s |
| FU01 | FollowUp | answered | answered | ❌ | 0.0s |
| FU02 | FollowUp | answered | answered | ❌ | 0.0s |
| FA01 | Failure | refused | refused | ✅ | 0.0s |
| FA02 | Failure | routed | routed | ❌ | 0.592s |
| FA03 | Failure | answered | answered | ✅ | 0.0s |
| DL01 | DataLoading | duplicate | duplicate | ❌ | 0.591s |
| DL02 | DataLoading | duplicate | duplicate | ❌ | 0.607s |
| DL03 | DataLoading | duplicate | duplicate | ❌ | 0.57s |

## Failed Cases

| ID | Failed Check | Detail |
|----|-------------|--------|
| C01 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| C02 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| C03 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| D01 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| D02 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| D03 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| D04 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| D05 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| E01 | plans_executed | planned steps missing from steps_run: ['look up service ownership'] |
| E02 | plans_executed | planned steps missing from steps_run: ['look up service ownership'] |
| REF01 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| REF02 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| REF03 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| REF04 | plans_executed | planned steps missing from steps_run: ['check action authorization'] |
| FU01 | plans_executed | planned steps missing from steps_run: ['look up service ownership'] |
| FU02 | plans_executed | planned steps missing from steps_run: ['look up service ownership'] |
| FA02 | plans_executed | planned steps missing from steps_run: ['check open incidents', 'route to on-call'] |
| DL01 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| DL02 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
| DL03 | plans_executed | planned steps missing from steps_run: ['check open incidents'] |
