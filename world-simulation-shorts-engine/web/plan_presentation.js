// Scene review shows events; provenance stays in the immutable Scene JSON.
export function sceneEventSummary(scene, names) {
  return (scene.visual_events || [])
    .filter(event => !/camera|zoom|pan/i.test(String(event.kind || event.type || '')))
    .map(event => names[event.kind || event.type] || '상황 변화')
    .slice(0, 2).join(' → ');
}

export function failureSummary(error) {
  if (!error || typeof error !== 'object') return String(error || '');
  const parts = [error.scene_id, error.failed_stage, error.code, error.message];
  if (Number.isInteger(error.diagnostics?.return_code)) parts.push(`exit ${error.diagnostics.return_code}`);
  return parts.filter(Boolean).join(' · ');
}
