# Optional Planner Scene V1 causal contract

The night-run continuation composes the existing route, moving-object, endpoint-pulse,
front-line and area features. It adds optional portable scheduling data to the
non-FINAL planner contract. Existing Scene V1 fields, version constants, feature
enums and default planning behavior remain unchanged. This does not promote
Planner V1 to FINAL; the gate remains `USER_VIDEO_REVIEW_REQUIRED`.

## Scene `causal_tracks`

`causal_tracks` is optional. Omit it when there are no tracks; when present it is a
nonempty array. Each track rejects unknown fields and requires the following:

| Field | Meaning / constraint |
| --- | --- |
| `id` | Unique track identifier using the existing identifier format. |
| `source_id` | Reference to supplied source notes; production provenance must remain verified. |
| `action_kind` | Free nonempty text describing a generic action; no historical unit identity is implied. |
| `from_state_id` | Existing preceding state identifier. |
| `to_state_id` | Existing immediately following state identifier. |
| `motion_start_frame` | Nonnegative safe integer frame at which the approach interval starts. |
| `contact_frame` | Nonnegative safe integer frame marking contact or the no-contact phase boundary. |
| `control_start_frame` | Nonnegative safe integer frame at which control change starts. |
| `control_end_frame` | Nonnegative safe integer frame at which control change finishes. |
| `end_frame` | Nonnegative safe integer exclusive end of the track. |
| `contact_kind` | `SCHEMATIC_FRONT_CONTACT`, `ARRIVAL`, or `NONE`. |
| `semantic_mode` | Exactly `SCHEMATIC_STATE_TRANSITION`. |
| `represents_historical_unit` | Exactly `false`. |

Optional `route_id` and `object_id` must occur together. They reference an existing
route and moving object, and the object's `route_id` must match the track's route.
Optional `target_front_line_id` and `contact_anchor` must occur together. The
anchor uses the existing `[longitude, latitude]` convention and bounds:
longitude `[-180, 180]`, latitude `[-90, 90]`.

An actor-free track must use `action_kind: CONTROL_ONLY` or `SETTLEMENT`,
`contact_kind: NONE`, and omit both route/object references. Conversely, those two
action kinds forbid route/object references and require `NONE`. The frame named
`contact_frame` remains a phase boundary and does not produce a contact cue for
`NONE`.

The runtime validator supplements JSON Schema with reference and cross-field
checks. It enforces adjacent states, source and actor bindings, directed route
endpoint contact, a contact anchor supported by the supplied front geometry, and
the frame order:

```text
motion_start_frame < contact_frame <= control_start_frame < control_end_frame <= end_frame
```

Frames must follow the camera lock and stay within `timing.total_frames`. The
control interval must fit within the target state's transition window. Frame
order is a visual schedule, not a claim of observed historical unit timing.
Schematic front-contact cues indicate a supplied broad front transition; they
must not imply a fabricated battle, precise attack location, or historical unit.

No new selected-feature enum is introduced. Route/object graphics continue to
use the existing Flow contract. WAR continues to reject disaster `impact_zones`
and `IMPACT_ZONE`; a schematic contact cue does not relax that rule. Contact and
control rendering remain adapter composition of existing feature APIs, without
changing FINAL cores.

## Optional facts `scene_timing`

The facts input may provide `scene_timing` to supply the full existing timing
record. Omission keeps the default planner timing unchanged. This is an input
override; it is emitted as the existing Scene `timing` field, not a new Scene
root field.

The complete record contains exactly these existing keys:

```text
fps
total_frames
duration_seconds
camera_lock_frame
event_start_frame
initial_reveal_frames
state_transition_frames
final_hold_frames
action_frames
frame_policy
blank_interstage_frames
```

The existing timing constraints still apply: safe integer frame values;
`fps` matches output FPS; `duration_seconds === total_frames / fps`;
`camera_lock_frame === event_start_frame`; `frame_policy` is
`INTEGER_DETERMINISTIC`; and `blank_interstage_frames` is `0`. Existing state
windows remain chronological and contiguous, ending at the final HOLD. Output
remains silent and requires user video review.

When the supplied camera/event lock is frame `0`, the planner skips zero-length
geographic-context and event-approach beats. It does not emit zero-duration beats.
The minimum is an action beat followed by HOLD; legacy beat sequences remain unchanged.
The existing camera director and adapter still own camera behavior.

For an explicit WAR `scene_timing` override, `action_frames` must equal
`initial_reveal_frames + state_transition_frames * (stage_count - 1)`; default WAR
timing retains its legacy `action_frames` value when no override is supplied.

## Compatibility and verification scope

The updated schema and validator accept existing scenes without either optional
addition. Default compilation must preserve prior scene data and deterministic
timing. An old validator rejects scenes carrying the new root field, so support
for new scenes requires the updated planner/adapter.

Focused checks should cover an unchanged legacy scene, an opted-in scheduled
scene, paired references, actor-free actions, bad provenance/references, adjacent
states, geographic contact, and invalid frame ordering. Schema and runtime checks
are complementary: JSON Schema covers structure and paired fields; the runtime
validator covers the referenced data, geography, and relative frame ordering.
