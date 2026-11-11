These three source-independent helpers contain no private map, source polygon,
source frame, city anchor, event date or historical assertion. They are offline
source conversion helpers and do not change the renderer.

- `bounded_projection.py` subdivides edges before a nonlinear graticule
  transform. It splits at every graticule piece boundary, bounds the analytic
  second derivative, and accepts a chord only when its error bound is below the
  requested tolerance. The field supplies its own original curves, angular
  bounds and transform function. The 112,000 metres/degree metric is an upper
  bound for geographic angular-coordinate error, not a claim of source survey
  accuracy. This bound covers the additional projection approximation;
  pre-existing source-curve approximation error must be propagated separately.
- `exact_contact_faces.py` separates a repeated contact only when the caller
  has separately proved that the point is an exact shared source point. It
  preserves the complete directed edge multiset and exact binary64-input signed
  area. Unproved contacts, incompatible winding or a contact split involving holes fail closed. No
  snapping, coordinate repair or MakeValid operation is supplied.

- `exact_zero_length_edges.py` removes only exactly identical adjacent
  coordinate occurrences. All nonzero directed edges, exact signed area and
  distinct coordinate values must remain equal. It uses no epsilon and does
  not move coordinates or remove any nonzero edge.

The public helpers alone do not authorize a historical source or a deployment.
The private adapters and evidence are deliberately kept outside this folder.

Runtime integration must retain separate same-owner Polygon area records when
an existing validator rejects contact between MultiPolygon parts. Do not relax
that validator or merge the exact source faces to suppress the rejection.

The projection field must implement the specific graticule ratio transform
contract documented in the module; an arbitrary transform callback is not
supported. Native coordinates and the requested positive tolerance must be
finite, curves must be monotone in their input axis, and source coordinates
must remain inside the original vector-curve domains.
