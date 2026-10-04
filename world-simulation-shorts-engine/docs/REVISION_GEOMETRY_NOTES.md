# Partial-edit geometry verification

Ship additions select the sourced route that actually moves during the requested
time interval. A completed/stopped Suez reference is not used as the template for
ships departing on the Cape alternative. Two added ships use small distinct route
offsets, retain the same IDs across the selected adjacent scenes, and preserve the
verified maritime graph. If the route has not departed yet, the approval proposal
states when the ships will first appear; it does not invent an earlier departure.

Additional faint connections produce `network_expand` events. They do not claim
a bright route head: faint routes deliberately have no such head. A canvas-free
Three.js geometry check uses the frozen renderer's actual camera, Earth occlusion,
route progress and network-event rules to check a usable visible interval. Sound
events share the exact visual timestamps. If no existing sourced route can be
shown in that camera, the proposal returns `UNSUPPORTED_VISUAL_REQUIREMENT` with
`VISIBLE_NETWORK_COMPOSITION` before approval.

For example, two connections can be shown during the London–Paris–Rome sample's
second scene. The New York–London–Dubai sample's second scene still follows the
Atlantic, so its existing London-origin connections cannot be presented there
without changing the camera composition. That specific proposal is rejected.

These checks create no WebGL context, render no image and do not certify texture,
lighting or final video quality. Final rendering and automatic QC remain required.
