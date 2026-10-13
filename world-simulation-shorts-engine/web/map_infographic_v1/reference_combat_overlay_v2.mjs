/** Reference-study symbols on geographic, fixture-owned frame anchors.
 * FINAL camera, projection, layout, Flow motion and rendering remain untouched.
 * The pass owns only transparent authored badge artwork and uploads no map or
 * reference-video pixels. Flag shapes, sizes and rotations are fixture data.
 */
export const REFERENCE_COMBAT_OVERLAY_V2_VERSION = 'REFERENCE_COMBAT_OVERLAY_V2';
const finitePoint = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite);
const box = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
const intersects = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const inside = (a, b) => a[0] >= b[0] && a[1] >= b[1] && a[2] <= b[2] && a[3] <= b[3];
function convexOverlap(a, b) {
 // SAT measures actual octagonal symbol footprints. Their empty rectangular
 // corners must not create false collision failures on the source composition.
 for (const polygon of [a, b]) for (let index = 0; index < polygon.length; index++) {
  const first = polygon[index], next = polygon[(index+1)%polygon.length];
  const axis = [-(next[1]-first[1]), next[0]-first[0]];
  const one = a.map(point => point[0]*axis[0]+point[1]*axis[1]);
  const two = b.map(point => point[0]*axis[0]+point[1]*axis[1]);
  if (Math.max(...one) <= Math.min(...two) || Math.max(...two) <= Math.min(...one)) return false;
 }
 return true;
}

export function validateReferenceCombatUnits(units, profiles) {
 if (!Array.isArray(units) || !units.length || !profiles || typeof profiles !== 'object')
  throw Error('REFERENCE_COMBAT_FIXTURE_REQUIRED');
 const ids = new Set();
 for (const unit of units) {
  if (!unit || typeof unit.id !== 'string' || !unit.id || ids.has(unit.id))
   throw Error('REFERENCE_COMBAT_UNIQUE_ID_REQUIRED');
  ids.add(unit.id);
  if (!profiles[unit.profile_id] || !Array.isArray(profiles[unit.profile_id].flag_shapes)
   || !profiles[unit.profile_id].flag_shapes.length)
   throw Error('REFERENCE_COMBAT_AUTHORED_PROFILE_REQUIRED');
  if (!Array.isArray(unit.anchor_frames) || unit.anchor_frames.length < 2
   || !unit.anchor_frames.every(point => finitePoint(point) && Math.abs(point[0]) <= 180 && Math.abs(point[1]) <= 90))
   throw Error('REFERENCE_COMBAT_GEOGRAPHIC_FRAME_ANCHORS_REQUIRED');
  if (!Array.isArray(unit.size_frames) || unit.size_frames.length !== unit.anchor_frames.length
   || !unit.size_frames.every(size => Number.isFinite(size) && size >= 16 && size <= 240))
   throw Error('REFERENCE_COMBAT_MEASURED_SCREEN_SIZES_REQUIRED');
  if (!Array.isArray(unit.rotation_frames) || unit.rotation_frames.length !== unit.anchor_frames.length
   || !unit.rotation_frames.every(Number.isFinite))
   throw Error('REFERENCE_COMBAT_MEASURED_SCREEN_ROTATIONS_REQUIRED');
 }
 if (units.some(unit => unit.anchor_frames.length !== units[0].anchor_frames.length))
  throw Error('REFERENCE_COMBAT_EQUAL_FRAME_COUNTS_REQUIRED');
 return {units: units.length, frames: units[0].anchor_frames.length, motionEngine: 'NONE_SUPPLIED_FRAME_ANCHORS'};
}

/** The camera/presentation owner supplies the final geographic projection. */
export function evaluateReferenceCombatLayout(units, frame, {project, safeArea, protectedGraphics = []} = {}) {
 if (!Number.isSafeInteger(frame) || frame < 0 || typeof project !== 'function' || !box(safeArea))
  throw Error('REFERENCE_COMBAT_FRAME_PROJECTION_SAFE_AREA_REQUIRED');
 const output = units.map(unit => {
  if (frame >= unit.anchor_frames.length) throw Error('REFERENCE_COMBAT_FRAME_OUT_OF_RANGE');
  const anchor = unit.anchor_frames[frame], center = project([...anchor]);
  if (!finitePoint(center)) throw Error('REFERENCE_COMBAT_FINAL_PROJECTION_REQUIRED');
  const size = unit.size_frames[frame], radians = unit.rotation_frames[frame] * Math.PI / 180;
  // Regular octagons are bounded more tightly than rotated square textures.
  const vertices = Array.from({length: 8}, (_, index) => {
   const angle = (-112.5 + index * 45) * Math.PI / 180 + radians;
   return [center[0] + Math.cos(angle) * size / 2, center[1] + Math.sin(angle) * size / 2];
  });
  const actualBox = [Math.min(...vertices.map(p => p[0])) - 2, Math.min(...vertices.map(p => p[1])) - 2,
   Math.max(...vertices.map(p => p[0])) + 2, Math.max(...vertices.map(p => p[1])) + 2];
  return {id: unit.id, profile_id: unit.profile_id, anchor: [...anchor], position: [...center],
   size_px: size, rotation_degrees: unit.rotation_frames[frame], bounds: actualBox,
   footprint: vertices, insideSafeArea: inside(actualBox, safeArea), suppliedFrameAnchor: true};
 });
 const collisions = [];
 for (const item of output) for (const protectedItem of protectedGraphics) {
  const bounds = Array.isArray(protectedItem) ? protectedItem : protectedItem.bounds ?? protectedItem.box;
  if (!box(bounds)) throw Error('REFERENCE_COMBAT_PROTECTED_BOUNDS_REQUIRED');
  if (intersects(item.bounds, bounds)) collisions.push({unit: item.id, protected: protectedItem.id ?? 'PROTECTED_GRAPHIC'});
 }
 const overlaps = [];
 for (let index = 0; index < output.length; index++) for (let other = index + 1; other < output.length; other++)
  if (intersects(output[index].bounds, output[other].bounds)
   && convexOverlap(output[index].footprint, output[other].footprint)) overlaps.push([output[index].id, output[other].id]);
 return {version: REFERENCE_COMBAT_OVERLAY_V2_VERSION, frame, units: output,
  safeAreaViolations: output.filter(item => !item.insideSafeArea).map(item => item.id),
  criticalCollisions: collisions, unitOverlaps: overlaps, geographicAnchorsUnchanged: true,
  noReferenceFrameTexture: true, noRoutesArrowsOrText: true, speculativeImpactCues: 0};
}

function octagon(context, radius) {
 context.beginPath();
 for (let index = 0; index < 8; index++) {
  const angle = (-112.5 + index * 45) * Math.PI / 180;
  const x = Math.cos(angle) * radius, y = Math.sin(angle) * radius;
  if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
 }
 context.closePath();
}
function shapePath(context, shape) {
 context.beginPath();
 if (shape.type === 'rect') context.rect(shape.x, shape.y, shape.width, shape.height);
 else if (shape.type === 'circle') context.arc(shape.cx, shape.cy, shape.radius, 0, Math.PI * 2);
 else if (shape.type === 'ellipse') context.ellipse(shape.cx, shape.cy, shape.rx, shape.ry, shape.rotation ?? 0, 0, Math.PI * 2);
 else if (shape.type === 'polygon') {
  shape.points.forEach((point, index) => index ? context.lineTo(...point) : context.moveTo(...point)); context.closePath();
 } else if (shape.type === 'star') {
  const points = shape.points ?? 5;
  for (let index = 0; index < points * 2; index++) {
   const angle = -Math.PI / 2 + (shape.rotation ?? 0) + index * Math.PI / points;
   const radius = index % 2 === 0 ? shape.radius : shape.inner_radius ?? shape.radius * .43;
   const x = shape.cx + Math.cos(angle) * radius, y = shape.cy + Math.sin(angle) * radius;
   index ? context.lineTo(x, y) : context.moveTo(x, y);
  } context.closePath();
 } else if (shape.type === 'path') {
  for (const [operation, ...coordinates] of shape.commands) {
   if (operation === 'M') context.moveTo(...coordinates);
   else if (operation === 'L') context.lineTo(...coordinates);
   else if (operation === 'Q') context.quadraticCurveTo(...coordinates);
   else if (operation === 'C') context.bezierCurveTo(...coordinates);
   else if (operation === 'Z') context.closePath();
   else throw Error('REFERENCE_COMBAT_AUTHORED_PATH_COMMAND_REQUIRED');
  }
 } else throw Error('REFERENCE_COMBAT_AUTHORED_SHAPE_REQUIRED');
}
function paint(context, shape) {
 shapePath(context, shape);
 if (shape.fill) {context.fillStyle = shape.fill; context.fill();}
 if (shape.stroke) {context.strokeStyle = shape.stroke; context.lineWidth = shape.stroke_width ?? .01; context.stroke();}
}
function soldier(context, profile) {
 const ink = profile.soldier_ink ?? '#0b1010', helmet = profile.helmet_color ?? '#72856a';
 const uniform = profile.uniform_color ?? '#758271', skin = profile.skin_color ?? '#e9b896';
 context.lineJoin = 'round'; context.lineCap = 'round';
 const shapes = [
  {type: 'path', commands: [['M', -.28, .44], ['L', -.26, .30], ['Q', -.23, .24, -.12, .24],
   ['L', .12, .24], ['Q', .23, .24, .26, .30], ['L', .28, .44], ['Z']], fill: uniform, stroke: ink, stroke_width: .034},
  {type: 'rect', x: -.073, y: .15, width: .146, height: .13, fill: skin, stroke: ink, stroke_width: .025},
  {type: 'path', commands: [['M', -.144, .038], ['Q', -.14, -.11, 0, -.115], ['Q', .14, -.11, .144, .038],
   ['L', .138, .142], ['Q', .127, .20, .08, .22], ['Q', 0, .25, -.08, .22], ['Q', -.127, .20, -.138, .142], ['Z']],
   fill: skin, stroke: ink, stroke_width: .035},
  {type: 'path', commands: [['M', -.176, .03], ['Q', -.173, -.16, -.08, -.213], ['Q', 0, -.242, .08, -.213],
   ['Q', .173, -.16, .176, .03], ['L', .114, .03], ['L', .111, -.095],
   ['Q', 0, -.14, -.111, -.095], ['L', -.114, .03], ['Z']], fill: helmet, stroke: ink, stroke_width: .034},
  {type: 'path', commands: [['M', -.17, -.018], ['Q', -.10, -.012, -.12, .056], ['M', .17, -.018],
   ['Q', .10, -.012, .12, .056]], stroke: ink, stroke_width: .021},
  {type: 'path', commands: [['M', -.07, -.2], ['L', -.064, -.137], ['M', .036, -.215], ['L', .045, -.143]],
   stroke: '#c6d0b9', stroke_width: .025},
  {type: 'path', commands: [['M', -.126, .164], ['Q', -.063, .189, -.056, .211],
   ['M', .126, .164], ['Q', .063, .189, .056, .211]], stroke: ink, stroke_width: .02},
  {type: 'rect', x: -.20, y: .275, width: .052, height: .151, fill: '#bdc4ad', stroke: ink, stroke_width: .017},
  {type: 'rect', x: .148, y: .275, width: .052, height: .151, fill: '#bdc4ad', stroke: ink, stroke_width: .017},
  {type: 'rect', x: -.118, y: .331, width: .096, height: .073, fill: '#bfc6b1', stroke: ink, stroke_width: .017},
  {type: 'rect', x: .022, y: .331, width: .096, height: .073, fill: '#bfc6b1', stroke: ink, stroke_width: .017},
 ];
 for (const shape of shapes) paint(context, shape);
}
function createBadgeCanvas(profile) {
 const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
 const context = canvas.getContext('2d', {alpha: true}); context.translate(128, 128); context.scale(256, 256);
 context.save(); octagon(context, .48); context.fillStyle = profile.background ?? '#ffffff'; context.fill(); context.clip();
 for (const shape of profile.flag_shapes) paint(context, shape);
 soldier(context, profile); context.restore();
 octagon(context, .48); context.strokeStyle = '#0b1010'; context.lineWidth = .045; context.stroke();
 octagon(context, .48); context.strokeStyle = profile.border_color ?? '#ffffff'; context.lineWidth = .022; context.stroke();
 octagon(context, .443); context.strokeStyle = '#0b1010'; context.lineWidth = .013; context.stroke();
 return canvas;
}
function shader(gl, type, source) {
 const result = gl.createShader(type); gl.shaderSource(result, source); gl.compileShader(result);
 if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) throw Error(`REFERENCE_COMBAT_SHADER:${gl.getShaderInfoLog(result)}`);
 return result;
}

/** Draw only transparent authored unit badges on the existing default framebuffer. */
export async function createReferenceCombatOverlay({canvas, width = 1080, height = 1920, units, profiles} = {}) {
 const fixture = validateReferenceCombatUnits(units, profiles);
 if (!canvas || canvas.width !== width || canvas.height !== height) throw Error('REFERENCE_COMBAT_NATIVE_CANVAS_REQUIRED');
 const gl = canvas.getContext('webgl2'); if (!gl) throw Error('REFERENCE_COMBAT_WEBGL2_REQUIRED');
 const {captureFlowNativeGlState, restoreFlowNativeGlState} = await import('./flow_graphic_pass_v2.mjs');
 const surface = document.createElement('canvas'); surface.width = width; surface.height = height;
 const context = surface.getContext('2d', {alpha: true});
 const badges = new Map(Object.entries(profiles).map(([id, profile]) => [id, createBadgeCanvas(profile)]));
 const saved = captureFlowNativeGlState(gl);
 let program, texture, vao, buffer;
 try {
  program = gl.createProgram();
  const vertex = shader(gl, gl.VERTEX_SHADER, `#version 300 es\nprecision highp float;\nlayout(location=0) in vec2 p;out vec2 uv;void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0.,1.);}`);
  const fragment = shader(gl, gl.FRAGMENT_SHADER, `#version 300 es\nprecision highp float;\nuniform sampler2D symbols;in vec2 uv;out vec4 color;void main(){color=texture(symbols,vec2(uv.x,1.-uv.y));}`);
  gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
  gl.deleteShader(vertex); gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error(`REFERENCE_COMBAT_LINK:${gl.getProgramInfoLog(program)}`);
  vao = gl.createVertexArray(); buffer = gl.createBuffer(); gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  texture = gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
 } finally {restoreFlowNativeGlState(gl, saved);}
 return {
  version: REFERENCE_COMBAT_OVERLAY_V2_VERSION,
  evidence: {version: REFERENCE_COMBAT_OVERLAY_V2_VERSION,
   artwork: 'AUTHORED_GENERIC_HELMET_OVER_FIXTURE_FLAG_SHAPES',
   sourceVideoPixelsAsTexture: false, frameBackgroundReadOrCopied: false,
   noRoutesArrowsOrText: true, motionEngine: 'NONE_SUPPLIED_GEOGRAPHIC_FRAME_ANCHORS'},
  fixture,
  draw({frame, project, protectedGraphics = [], safeArea = [48, 72, width - 48, height - 72]} = {}) {
   const controls = evaluateReferenceCombatLayout(units, frame, {project, protectedGraphics, safeArea});
   context.clearRect(0, 0, width, height);
   for (const item of controls.units) {
    context.save(); context.translate(...item.position); context.rotate(item.rotation_degrees * Math.PI / 180);
    // Sprite includes two-pixel black outline support outside the authored octagon.
    context.drawImage(badges.get(item.profile_id), -item.size_px / 2, -item.size_px / 2, item.size_px, item.size_px);
    context.restore();
   }
   const native = captureFlowNativeGlState(gl);
   try {
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, width, height); gl.disable(gl.SCISSOR_TEST);
    gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE); gl.disable(gl.STENCIL_TEST); gl.disable(gl.RASTERIZER_DISCARD);
    gl.enable(gl.BLEND); gl.blendEquation(gl.FUNC_ADD); gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.colorMask(true, true, true, true); gl.useProgram(program); gl.bindVertexArray(vao);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, texture); gl.bindSampler(0, null);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 4); gl.pixelStorei(gl.UNPACK_ROW_LENGTH, 0);
    gl.pixelStorei(gl.UNPACK_SKIP_PIXELS, 0); gl.pixelStorei(gl.UNPACK_SKIP_ROWS, 0); gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER, null);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, surface);
    gl.uniform1i(gl.getUniformLocation(program, 'symbols'), 0); gl.drawArrays(gl.TRIANGLES, 0, 6);
    const error = gl.getError(); if (error !== gl.NO_ERROR) throw Error(`REFERENCE_COMBAT_DRAW_GL_ERROR:${error}`);
   } finally {restoreFlowNativeGlState(gl, native);}
   const error = gl.getError(); if (error !== gl.NO_ERROR) throw Error(`REFERENCE_COMBAT_RESTORE_GL_ERROR:${error}`);
   return {...controls, artwork: 'AUTHORED_GENERIC_HELMET_OVER_FIXTURE_FLAG_SHAPES',
    frameBackgroundReadOrCopied: false, motionOwner: 'SUPPLIED_REFERENCE_GEOGRAPHIC_FRAME_ANCHORS', glError: error};
  },
  dispose() {gl.deleteProgram(program); gl.deleteTexture(texture); gl.deleteVertexArray(vao); gl.deleteBuffer(buffer); badges.clear();},
 };
}
