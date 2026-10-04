# Completed-connection summary regression fix

The preceding clean-runtime aggregate run remains preserved at `../final_core_153_clean_runtime_20261004T205807Z`:153 tests ran in703.951s, five failed, source_changes was empty. All five failures were the same final region label repeating a city after all relevant movement had ended. The active-distance helper and strict duplicate-place gate were correct; neither was weakened. Exact source snapshots and hashes were saved before this fix.

Only planner generation gained a separate post-arrival fallback. It accepts a verified nonfaint main route ending at the disclosed place only when the actual authored SceneRoutes progress is complete. It reuses the completed sourced connection/total-distance formatter. It never fabricates an active entity, a remaining distance, or a future arrival. When necessary, the summary and its paired SFX are moved to an earlier safe information-reading slot before the final payoff; strict eligibility still checks both captions.

The focused completed-summary suite passed4/4 in191.637s. It checks aviation180/183.5/180.013 and shipping180/183.5 against strict gates, cumulative30fps frame boundaries, actual frozen Three curve progress/length, final payoff windows, rejection of incomplete/faint/unverified curves, and the unchanged original B75 two-Scene natural revision. The exact aggregate core topic was also generated and revalidated separately; see TEST_REPORT.json and core_180_plan_candidate.json.

Current focused replay:

```bash
python3 -m unittest discover -s tests -p 'test_completed_connection_summaries.py' -v
```

The B75 original bytes, revisions handler, retention guard, existing label regression tests, and renderer JS retain their previous hashes. These are planning/geometry results, not new rendered-pixel or whole-video quality proof. No original media, actual project version/approval, worker, server, renderer, cache policy, or Git state was changed. Root owns the next combined test run and later actual rendering.
