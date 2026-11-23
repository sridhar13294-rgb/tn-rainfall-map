# Method rules (Sridhar) - read at the start of EVERY work cycle; every verdict must satisfy all of them

1. Root cause first: FMEA + 5-Why + Fishbone. No trial-and-error.
2. If a physics equation / implementation looks like the problem, check its INPUTS first (measure vs ERA5/obs). Do not change physics or code blindly.
3. Register the prediction / rule in rootcause.md BEFORE the result. Gates are never relaxed beyond rule 10. No tuning: values come from references (IFS docs, papers, ERA5, RRTMG, LES, obs).
4. A fix that FAILS a gate is NOT rejected directly (18 Nov 23:50). Do a failure 5-Why: which check failed, what drives it. Reject only if the failure traces to the fix itself; otherwise mark "HELD - blocked by X" and re-test after X is fixed.
5. Compare only with real references. Honest pushback; correct my own earlier claims openly.
6. Don't ask permission to run tests; never sit idle; run in parallel where possible; fix-first when a documented fix exists (after the input check).
7. Every report: the one-word status table of every open problem, a reason on every row, and the closure count vs the plan (all Stage-1 problems closed by Dec 1st week).
8. Check the clock (TZ=Asia/Kolkata date) before writing any time. No messages 00:30-07:00 IST.
9. Kaggle: account 1 and account 4 only (acct 4: one job at a time); no workarounds; no wasted GPU minutes. main/website only after "go live". Secrets only as GitHub secrets.

Verdict stamp (required on every PASS / FAIL / named / not-named / rejected / held line from 19 Nov):
  [reg: <time registered> | inputs: <checked what> | fail-5why: <cause of failure, or n/a for PASS>]

10. TOLERANCE (user decision 23 Nov 15:42 IST, 'Agree'): a result PASSES a gate if it is within 2 standard errors of the limit
    (95 % level: 'not significantly worse than the target'). SE comes from the measurement itself, never from how close the result is:
    mean over N starts/storms -> SE = sd / sqrt(N); a count k of n -> SE = sqrt(n p (1 - p)), p = k / n. Same rule for every gate,
    stated with the SE in every verdict stamp. A pass under tolerance is written 'PASS (tol)' and any real remaining cost goes to Stage 2.
