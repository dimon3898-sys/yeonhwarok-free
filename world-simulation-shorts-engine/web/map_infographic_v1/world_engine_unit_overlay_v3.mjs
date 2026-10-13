/** Original WORLD ENGINE infantry artwork over immutable geographic anchors.
 * Reuses the established projection/layout/protection evaluator; this module
 * owns only a transparent visual profile, with no simulation or event effects.
 */
import {evaluateReferenceCombatLayout} from './reference_combat_overlay_v2.mjs';

export const WORLD_ENGINE_UNIT_OVERLAY_V3_VERSION = 'WORLD_ENGINE_ORIGINAL_UNIT_OVERLAY_V3';
const point = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite);
const color = value => typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value);
const forbidden = ['flag_shapes', 'national_flag', 'insignia', 'badge_artwork', 'reference_pixels'];

export function validateWorldEngineUnitFixture(units, profiles) {
 if (!Array.isArray(units) || !units.length || !profiles || typeof profiles !== 'object')
  throw Error('WORLD_ENGINE_ORIGINAL_UNIT_FIXTURE_REQUIRED');
 for (const profile of Object.values(profiles)) {
  if (!profile || profile.role !== 'INFANTRY' || profile.artwork !== 'ORIGINAL_FULL_BODY_ISOMETRIC_INFANTRY'
   || !color(profile.faction_color) || !color(profile.faction_highlight)
   || !Array.isArray(profile.metal_palette) || profile.metal_palette.length !== 3
   || !profile.metal_palette.every(color) || forbidden.some(key => key in profile))
   throw Error('WORLD_ENGINE_ORIGINAL_INFANTRY_PROFILE_REQUIRED');
 }
 const ids = new Set();
 for (const unit of units) {
  if (!unit || typeof unit.id !== 'string' || !unit.id || ids.has(unit.id) || !profiles[unit.profile_id])
   throw Error('WORLD_ENGINE_UNIQUE_BOUND_UNIT_REQUIRED');
  ids.add(unit.id);
  if (!Array.isArray(unit.anchor_frames) || unit.anchor_frames.length < 2
   || !unit.anchor_frames.every(value => point(value) && Math.abs(value[0]) <= 180 && Math.abs(value[1]) <= 90))
   throw Error('WORLD_ENGINE_GEOGRAPHIC_ANCHORS_REQUIRED');
  if (!Array.isArray(unit.size_frames) || unit.size_frames.length !== unit.anchor_frames.length
   || !unit.size_frames.every(value => Number.isFinite(value) && value >= 32 && value <= 96))
   throw Error('WORLD_ENGINE_RESTRAINED_ROLE_SIZE_REQUIRED');
  if (!Array.isArray(unit.rotation_frames) || unit.rotation_frames.length !== unit.anchor_frames.length
   || !unit.rotation_frames.every(Number.isFinite))
   throw Error('WORLD_ENGINE_SUPPLIED_ROTATION_REQUIRED');
 }
 if (units.some(unit => unit.anchor_frames.length !== units[0].anchor_frames.length))
  throw Error('WORLD_ENGINE_EQUAL_UNIT_FRAME_COUNTS_REQUIRED');
 return {units: units.length, frames: units[0].anchor_frames.length,
  motionEngine: 'NONE_SUPPLIED_FRAME_ANCHORS', layoutEngine: 'REUSED_REFERENCE_COMBAT_LAYOUT',
  artwork: 'ORIGINAL_FULL_BODY_ISOMETRIC_INFANTRY', sourceIconArtworkCopied: false};
}

export function evaluateWorldEngineUnitLayout(units, frame, input) {
 const layout = evaluateReferenceCombatLayout(units, frame, input);
 return {...layout, version: WORLD_ENGINE_UNIT_OVERLAY_V3_VERSION,
  artwork: 'ORIGINAL_FULL_BODY_ISOMETRIC_INFANTRY',
  collisionEnvelope: 'REUSED_CONSERVATIVE_EIGHT_SIDED_SUPPORT_NOT_VISIBLE_ARTWORK',
  sourceIconArtworkCopied: false, nationalInsignia: 0, flags: 0,
  visibleBadgeOutlines: 0, speculativeImpactCues: 0};
}

function polygon(context, points, fill, stroke = '#111c20', strokeWidth = .012) {
 context.beginPath();
 points.forEach(([x, y], index) => index ? context.lineTo(x, y) : context.moveTo(x, y));
 context.closePath(); context.fillStyle = fill; context.fill();
 if (stroke) {context.strokeStyle = stroke; context.lineWidth = strokeWidth; context.stroke();}
}
function line(context, points, stroke, width = .01) {
 context.beginPath();
 points.forEach(([x, y], index) => index ? context.lineTo(x, y) : context.moveTo(x, y));
 context.strokeStyle = stroke; context.lineWidth = width; context.stroke();
}

/** Authored transparent vector artwork, never a crop or texture from a video.
 * Three bevel tones describe depth at mobile size; the small color panels
 * communicate faction without borrowing any real-world badge or insignia.
 */
export function createWorldEngineUnitArtwork(profile, resolution = 256) {
 validateWorldEngineUnitFixture([{id: 'ARTWORK_VALIDATION', profile_id: 'ARTWORK',
  anchor_frames: [[0, 0], [0, 0]], size_frames: [72, 72], rotation_frames: [0, 0]}], {ARTWORK: profile});
 if (!Number.isSafeInteger(resolution) || resolution < 96 || resolution > 1024)
  throw Error('WORLD_ENGINE_UNIT_ARTWORK_RESOLUTION_REQUIRED');
 const canvas = document.createElement('canvas'); canvas.width = canvas.height = resolution;
 const context = canvas.getContext('2d', {alpha: true});
 context.translate(resolution / 2, resolution / 2); context.scale(resolution, resolution);
 context.lineJoin = 'round'; context.lineCap = 'round';
 const [light, mid, dark] = profile.metal_palette;
 const shadow = context.createRadialGradient(.015, .345, .015, .015, .345, .29);
 shadow.addColorStop(0, '#02080bcc'); shadow.addColorStop(.45, '#02080b77'); shadow.addColorStop(1, '#02080b00');
 context.save(); context.translate(0, .345); context.scale(1, .27); context.translate(0, -.345);
 context.fillStyle = shadow; context.beginPath(); context.arc(.015, .345, .29, 0, Math.PI * 2); context.fill(); context.restore();

 // Offset pack and separated boots make a full-body unit, rather than a bust.
 polygon(context, [[-.13, -.18], [-.23, -.13], [-.235, .035], [-.17, .12], [-.08, .08]], dark);
 polygon(context, [[-.10, .075], [.005, .10], [-.008, .225], [-.095, .325], [-.14, .315], [-.105, .195]], '#344449');
 polygon(context, [[.005, .10], [.09, .068], [.137, .21], [.132, .345], [.069, .345], [.033, .225]], mid);
 polygon(context, [[-.14, .30], [-.08, .325], [-.074, .367], [-.17, .377], [-.203, .349]], '#1a272c');
 polygon(context, [[.068, .318], [.135, .32], [.182, .363], [.159, .387], [.062, .378]], '#1a272c');
 line(context, [[-.169, .357], [-.079, .349]], '#89a1a0', .009);
 line(context, [[.071, .35], [.146, .362]], '#acc0b6', .009);

 // Side and top planes are intentionally asymmetric for a distinctive 2.5D silhouette.
 polygon(context, [[-.10, -.205], [.073, -.227], [.156, -.146], [.159, .028], [.071, .13], [-.10, .1], [-.158, -.04]], mid);
 polygon(context, [[.073, -.227], [.156, -.146], [.159, .028], [.071, .13], [.063, -.047]], dark);
 polygon(context, [[-.10, -.205], [.073, -.227], [.133, -.174], [-.025, -.148]], light);
 polygon(context, [[-.122, -.108], [.062, -.115], [.065, .013], [-.099, .022]], '#708789');
 polygon(context, [[-.103, -.087], [.059, -.092], [.058, -.041], [-.099, -.034]], profile.faction_color, null);
 line(context, [[-.099, -.084], [.051, -.088]], profile.faction_highlight, .012);
 polygon(context, [[-.144, -.14], [-.231, -.067], [-.248, .03], [-.20, .072], [-.159, -.016]], mid);
 polygon(context, [[.13, -.149], [.209, -.105], [.245, -.027], [.213, .015], [.164, -.052]], dark);
 polygon(context, [[-.149, -.15], [-.205, -.107], [-.187, -.06], [-.138, -.087]], profile.faction_color);
 polygon(context, [[.146, -.143], [.198, -.119], [.209, -.076], [.167, -.094]], profile.faction_color);
 line(context, [[-.227, -.057], [-.235, .016]], '#b4c7bd', .008);
 polygon(context, [[-.247, .015], [-.216, -.003], [-.17, .043], [-.19, .079], [-.231, .064]], '#415659');
 polygon(context, [[.213, -.024], [.248, -.007], [.243, .038], [.210, .046], [.188, .012]], '#415659');

 // A compact equipment strap is static artwork, not a weapon/effect animation.
 line(context, [[-.10, -.14], [.054, .077]], '#142227', .028);
 line(context, [[-.097, -.146], [.053, .073]], '#abbcaf', .007);
 polygon(context, [[-.119, .055], [.09, .037], [.093, .097], [-.09, .118]], '#283d41');
 polygon(context, [[-.075, .063], [-.023, .059], [-.021, .1], [-.07, .105]], light);
 polygon(context, [[.004, .057], [.052, .053], [.052, .093], [.006, .096]], mid);

 // An opaque visor and chamfered helmet avoid cloning the source's face portrait.
 polygon(context, [[-.085, -.293], [.082, -.301], [.1, -.219], [.063, -.164], [-.063, -.169], [-.096, -.221]], '#34484e');
 polygon(context, [[-.097, -.278], [.082, -.289], [.094, -.235], [-.08, -.222]], '#11242d');
 line(context, [[-.083, -.264], [.076, -.273]], '#8aacb3', .01);
 const helmet = context.createLinearGradient(-.13, -.37, .16, -.24);
 helmet.addColorStop(0, '#d6dfcc'); helmet.addColorStop(.45, light); helmet.addColorStop(1, dark);
 context.beginPath(); context.moveTo(-.14, -.278); context.bezierCurveTo(-.155, -.35, -.115, -.409, -.039, -.418);
 context.bezierCurveTo(.05, -.433, .134, -.397, .147, -.318); context.lineTo(.143, -.278);
 context.quadraticCurveTo(.02, -.293, -.14, -.278); context.closePath(); context.fillStyle = helmet; context.fill();
 context.strokeStyle = '#172a2e'; context.lineWidth = .014; context.stroke();
 line(context, [[-.111, -.317], [-.097, -.363], [-.055, -.387]], '#e4e9d4', .009);
 polygon(context, [[-.145, -.282], [.143, -.296], [.153, -.271], [-.138, -.254]], '#8aa4a2');
 line(context, [[-.136, -.271], [.141, -.283]], '#d0ddd0', .008);
 return canvas;
}

function shader(gl, type, source) {
 const value = gl.createShader(type); gl.shaderSource(value, source); gl.compileShader(value);
 if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) throw Error('WORLD_ENGINE_UNIT_SHADER:' + gl.getShaderInfoLog(value));
 return value;
}

/** Transparent unit sprites on the original framebuffer; no map-frame copy. */
export async function createWorldEngineUnitOverlay({canvas, width = 1080, height = 1920, units, profiles} = {}) {
 const fixture = validateWorldEngineUnitFixture(units, profiles);
 if (!canvas || canvas.width !== width || canvas.height !== height) throw Error('WORLD_ENGINE_UNIT_CANVAS_REQUIRED');
 const gl = canvas.getContext('webgl2'); if (!gl) throw Error('WORLD_ENGINE_UNIT_WEBGL2_REQUIRED');
 const {captureFlowNativeGlState, restoreFlowNativeGlState} = await import('./flow_graphic_pass_v2.mjs');
 const surface = document.createElement('canvas'); surface.width = width; surface.height = height;
 const context = surface.getContext('2d', {alpha: true});
 const artwork = new Map(Object.entries(profiles).map(([id, profile]) => [id, createWorldEngineUnitArtwork(profile)]));
 const saved = captureFlowNativeGlState(gl); let program, texture, vao, buffer, disposed = false;
 try {
  program = gl.createProgram();
  const vertex = shader(gl, gl.VERTEX_SHADER, '#version 300 es\nprecision highp float;\nlayout(location=0) in vec2 p;out vec2 uv;void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0.,1.);}');
  const fragment = shader(gl, gl.FRAGMENT_SHADER, '#version 300 es\nprecision highp float;\nuniform sampler2D symbols;in vec2 uv;out vec4 color;void main(){color=texture(symbols,vec2(uv.x,1.-uv.y));}');
  gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
  gl.deleteShader(vertex); gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error('WORLD_ENGINE_UNIT_LINK:' + gl.getProgramInfoLog(program));
  vao = gl.createVertexArray(); buffer = gl.createBuffer(); gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  texture = gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, texture);
  for (const [key, value] of [['TEXTURE_MIN_FILTER', 'LINEAR'], ['TEXTURE_MAG_FILTER', 'LINEAR'],
   ['TEXTURE_WRAP_S', 'CLAMP_TO_EDGE'], ['TEXTURE_WRAP_T', 'CLAMP_TO_EDGE']]) gl.texParameteri(gl.TEXTURE_2D, gl[key], gl[value]);
 } finally {restoreFlowNativeGlState(gl, saved);}
 return {
  version: WORLD_ENGINE_UNIT_OVERLAY_V3_VERSION, fixture,
  evidence: {version: WORLD_ENGINE_UNIT_OVERLAY_V3_VERSION, artwork: 'ORIGINAL_FULL_BODY_ISOMETRIC_INFANTRY',
   layoutEngine: 'REUSED_REFERENCE_COMBAT_LAYOUT', sourceIconArtworkCopied: false,
   nationalInsignia: 0, flags: 0, visibleBadgeOutlines: 0, speculativeImpactCues: 0,
   sourceVideoPixelsAsTexture: false, frameBackgroundReadOrCopied: false,
   noRoutesArrowsOrText: true, motionEngine: 'NONE_SUPPLIED_GEOGRAPHIC_FRAME_ANCHORS'},
  draw({frame, project, protectedGraphics = [], safeArea = [48, 72, width - 48, height - 72]} = {}) {
   if (disposed) throw Error('WORLD_ENGINE_UNIT_OVERLAY_DISPOSED');
   const controls = evaluateWorldEngineUnitLayout(units, frame, {project, protectedGraphics, safeArea});
   context.clearRect(0, 0, width, height);
   for (const item of controls.units) {
    context.save(); context.translate(...item.position); context.rotate(item.rotation_degrees * Math.PI / 180);
    context.drawImage(artwork.get(item.profile_id), -item.size_px / 2, -item.size_px / 2, item.size_px, item.size_px);
    context.restore();
   }
   const native = captureFlowNativeGlState(gl);
   try {
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, width, height); gl.disable(gl.SCISSOR_TEST);
    for (const capability of ['DEPTH_TEST', 'CULL_FACE', 'STENCIL_TEST', 'RASTERIZER_DISCARD']) gl.disable(gl[capability]);
    gl.enable(gl.BLEND); gl.blendEquation(gl.FUNC_ADD); gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.colorMask(true, true, true, true); gl.useProgram(program); gl.bindVertexArray(vao);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, texture); gl.bindSampler(0, null);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE); gl.pixelStorei(gl.UNPACK_ALIGNMENT, 4);
    gl.pixelStorei(gl.UNPACK_ROW_LENGTH, 0); gl.pixelStorei(gl.UNPACK_SKIP_PIXELS, 0); gl.pixelStorei(gl.UNPACK_SKIP_ROWS, 0);
    gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER, null); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, surface);
    gl.uniform1i(gl.getUniformLocation(program, 'symbols'), 0); gl.drawArrays(gl.TRIANGLES, 0, 6);
    const error = gl.getError(); if (error !== gl.NO_ERROR) throw Error('WORLD_ENGINE_UNIT_DRAW_GL_ERROR:' + error);
   } finally {restoreFlowNativeGlState(gl, native);}
   const error = gl.getError(); if (error !== gl.NO_ERROR) throw Error('WORLD_ENGINE_UNIT_RESTORE_GL_ERROR:' + error);
   return {...controls, frameBackgroundReadOrCopied: false, motionOwner: 'SUPPLIED_REFERENCE_GEOGRAPHIC_FRAME_ANCHORS', glError: error};
  },
  dispose() {if (disposed) return; gl.deleteProgram(program); gl.deleteTexture(texture); gl.deleteVertexArray(vao);
   gl.deleteBuffer(buffer); artwork.clear(); disposed = true;},
 };
}

export const createMapOriginalUnitOverlayV3 = createWorldEngineUnitOverlay;
