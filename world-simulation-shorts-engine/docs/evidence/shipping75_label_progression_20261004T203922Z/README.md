# Shipping75 repeated-city progression repair

The immutable production v001 bytes and source snapshots were preserved before edits. Its exact read-only validation now reports only PLAN_DUPLICATE_PLACE_LABEL for S002/E008 and S009/E034. The original production plan byte SHA is 7cf9775ffbff58a965884f7ba25bf34c3352432deb493f2a59ea6f21a3244fe5.

`isolated_unapproved_proposal.json` and `corrected_plan_candidate.json` come from a temporary ProjectStore using those exact original inputs. The proposal is unapproved. It changes only S002 and S009 visual_events and sound_events: E008 becomes 13,567 km REMAINING on R_SUEZ; E034 becomes 681 km REMAINING on R_CAPE. IDs, times, causes, sound clocks/gains, all camera/GIS/routes/entities, eight other Scenes, and real arrival E035 remain unchanged. Exact frozen Three SceneRoutes progress is recorded in REPAIR_PROOF.json.

`fresh_generation_candidate.json` also passes the current plan, typed provenance, retention, and pure renderer eligibility gates. The narrow gate checks region_reveal plain-place text repeating a simultaneously active verified same-place city label. It does not reject a first city pulse or a real arrival. These are planning/geometry certificates, not rendered-pixel or whole-video quality proof. No media, actual project versions, approvals, server, worker, renderer JS, or Git state was modified.

The focused run at the historical filename used `PYTHONPATH=tests python3 -m unittest planning_label_regression -v`: five tests passed in 120.900s. Its exact test bytes and SHA were preserved before renaming to the standard-discovery filename. Both names have SHA ad6785e3e9db5d163f82bafbd07d88e49efd6f2c50c43162c34a63fc0e5e5729.

Current replay command:

```bash
python3 -m unittest discover -s tests -p 'test_planning_label_regression.py' -v
```

Collection-only standard test discovery includes all five tests; it does not claim a new aggregate test run. Root owns the final combined execution and any later real partial rendering.
