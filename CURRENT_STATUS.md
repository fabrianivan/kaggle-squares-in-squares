# Current Optimization Status

* **Status:** Complete / Active Run
* **Last Updated:** 2026-11-12 ~09:28 UTC
* **Active Working Best Submission:** [`output/submission_22.177465.csv`](file:///Users/fabrianivan/kaggle-squares-in-squares/output/submission_22.177465.csv) (synced to [`output/submission_final.csv`](file:///Users/fabrianivan/kaggle-squares-in-squares/output/submission_final.csv))
* **Official Kaggle Public Score:** **`22.1774646631`** (Verified `SubmissionStatus.COMPLETE`, exact match to local interval certification; local certified best updated to `22.1774646584`)
* **Official Kaggle Leaderboard Rank:** **Rank 86** globally out of 1,965 teams (Team **"Cat & Dog"**)
* **Latest Turn Gain:** **`+0.0013422408`**
* **Cumulative Gain Today (Nov 12):** **`+0.0179631294`**
* **Daily Kaggle Submission Quota:** 5 submissions remaining today.

---

## 1. What Happened This Turn
1. **Claude History & Mechanism Audit:**
   - Audited conversation histories and local cache in `~/.claude/` and `~/Library/Application Support/Claude/`.
   - Discovered the `--no-alm` contact polish mechanism:
     ```bash
     fq quench --in in.txt --out out.txt --loosen 1.0 --no-alm --finish
     ```
     Bypasses Augmented Lagrangian relaxation entirely, eliminating the destructive 2% CLI expansion and executing a purely contractive Newton contact projection onto active contact manifolds.
   - Built [`src/engine/fast_repolish.py`](file:///Users/fabrianivan/kaggle-squares-in-squares/src/engine/fast_repolish.py) and ran across all 554 non-trivial puzzles:
     - **140 puzzles** improved strictly in certified side length.
     - Squeezed cumulative numerical slack: **`+0.0000012743`** (score: `22.1788056249`).
2. **Fresh Community Harvest Integration:**
   - Intercepted newly published releases on Kaggle:
     - `jonathan1506/50-top-2-6-22-1783-fault-dp-fq-stretch` (JoeGun #50 / 22.1783, published 09:02 UTC).
     - `jazivxt/boxed-in-sub` (published 08:51 UTC).
   - Executed certified interval merge via [`src/tools/merge_harvest.py`](file:///Users/fabrianivan/kaggle-squares-in-squares/src/tools/merge_harvest.py):
     - **29 candidate wins certified** (including massive improvements on $n=642$ ($+0.000343$), $n=800$ ($+0.000055$), $n=862$ ($+0.000122$), $n=905$ ($+0.000045$), $n=922$ ($+0.000118$)).
     - Full 1,000-puzzle official interval arithmetic certification: **0 rejected, 0 missing, score = 22.177464663134**.
3. **Kaggle Submission & Leaderboard Leap:**
   - Submitted `output/submission_22.177465.csv` to Kaggle (Ref `58267818`).
   - Official Kaggle evaluation confirmed: **`22.1774646631`** (`COMPLETE`).
   - Leaderboard rank jumped from **Rank 100** straight up 14 positions to **Rank 86** globally!
