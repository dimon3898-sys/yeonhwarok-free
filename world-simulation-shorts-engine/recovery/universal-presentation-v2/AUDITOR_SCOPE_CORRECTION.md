# Audit harness correction; no render retry

The first independent movie audit is retained at
`reports/MOVIE_AUDIT_1/ACTUAL_MOVIES_AUDIT.json`. Its only failed check required
a nonempty **aggregate** `REQUEST.inputTrace`. Inspection of the original
request and every actual frame showed that this composite contract carries
the authoritative trace in each `segments[].inputTrace` and retains that
same trace in every frame's diagnostic. The optional aggregate array is empty.

The corrected auditor verifies all of those Scene-local traces, rather than
requiring them at the wrong level. It also records the empty aggregate
explicitly in the output mapping. The actual geographic, time, source, camera,
route and event checks were not weakened. The corrected first-movie audit is
`reports/MOVIE_AUDIT_1_TRACE_SCOPED/ACTUAL_MOVIES_AUDIT.json`.

No renderer, captured frame, MP4, Studio source or claim changed. No movie was
rerendered. Both audit results remain available, so the distinction between a
test-harness assumption and an actual rendering defect can be checked.
