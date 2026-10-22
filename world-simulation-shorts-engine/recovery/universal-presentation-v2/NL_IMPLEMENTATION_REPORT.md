# Natural-language input and Scene connection result

The new opt-in adapter is implemented in `presentation_prompt.mjs`; the original input parser, facts validator, Scene compiler, engine adapter and five-region profile are unchanged. `NL_LIMITATIONS_AUDIT.md` records the prior limitations and exact original locations. `PRESENTATION_INPUT_CONTRACT.md` defines the new actual calls and explicit limits.

The adapter accepts Korean/English display instructions plus the supplied versioned data package. It extracts explicit duration/fps, calendar dates at their actual precision, supplied location/route references, directed connections and bounded camera/territory/highlight/cut intents. Scene IDs and ordinal clauses scope instructions to their supplied scenes. Factual coordinates, states, route direction and dates are never synthesized from place names or historical prose.

Missing data produces field-specific clarification objects; contradictory language or stale context returns a conflict. Invalid supplied data remains visible even when the prose also needs clarification. Unsupported visible labels, fades, orbit, external audio and other recognized unconnected requests do not silently pass. Unknown structured fields are rejected. This is bounded grammar and entity linking, with no LLM or unrestricted language claim.

A source-qualified request invokes the unchanged native validators and compilers. The original Scene object remains compatible and separate from the presentation sidecar. Input paths, hashes, geometry IDs, source notes, explicit display derivations and actual source receipts remain traceable. A previous source selection requires its matching explicit legacy profile instead of being ignored. Native context location/country bindings are checked against supplied data and the admitted region.

The compiler also passes through the independently validated `initialStateVisibility` public Area-operation mode. This retains a supplied visible initial area when explicitly requested at a matching scene boundary, without changing its source geometry or state clock. Runtime continuity admission and actual draw are reported by the runtime/Studio owners.

Actual focused validation is recorded in `reports/NL_TEST_RESULTS.json`:

- 70 Node tests passed, covering native Scene compatibility, data precedence, scoped instructions, dates, explicit coordinate/route binding, source denial, unsupported commands, dependency/partial-scene behavior, source selection, context binding and the explicit continuity sidecar.
- 15 JSON Schema tests passed, including unchanged reuse of the previous facts definitions and five positive envelope shapes.
- Compiler unit tests deliberately use an injected source stub to isolate compilation; they do not prove successful map availability. Actual provider-qualified fixture results are separate `EXAMPLE_MATRIX_ATTEMPT_*.json` evidence.
- No render, external LLM, paid API/GPU, Secret modification or FINAL change is claimed by these tests.

The current free profile is bounded to 240 total frames, preserves the existing WAR/TRANSPORT pixel families, uses the explicit closest-final camera constraint and supports actual cuts. The original long production implementation is preserved. Partial historical line/metric data remains unsupported where no pixel consumer is connected, and missing historical ownership remains a data block. Complete natural-language interpretation, arbitrary labels, factual geocoding and unrestricted new render families are not implemented.

Test success is technical evidence. Actual video, full-frame correspondence, source trajectory coverage and user visual approval are separate gates.
