/** Style-only extension over the existing, evaluated complementary control field.
 * No control plan, geographical vertex, camera, story, or moving path is authored here.
 * A destination RGB light multiplier preserves actual terrain relief through the
 * unchanged territorial fill. A finite luminous material edge samples the SAME
 * evaluated longitudinal boundary and is clipped by unchanged native land triangles.
 */
import {assertTerritoryControlPlan, evaluateTerritoryControlFrame, sampleControlBoundary}
 from './territory_control_adapter_v1.mjs';

export const REFERENCE_CONTROL_FRONTIER_LIGHT_V3_VERSION = 'REFERENCE_CONTROL_FRONTIER_LIGHT_V3';
const MAX_KNOTS = 64, MAX_RESERVATIONS = 64;
const clone = value => structuredClone(value);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const box = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
const point = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite);
const clamp = value => Math.max(0, Math.min(1, value));
const rgb = value => Array.isArray(value) && value.length === 3
 && value.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 1);

export function validateControlFrontierLightProfile(input) {
 if (!input || typeof input.profileName !== 'string' || !input.profileName.trim())
  throw Error('CONTROL_FRONTIER_EXPLICIT_STYLE_PROFILE_REQUIRED');
 const p = {...{
  centerColor: [1, .92, .79], haloColor: [1, .30, .46],
  centerWidthPixels: 1.4, haloSigmaPixels: 2.2, haloSupportPixels: 7.5,
  centerAlpha: .90, haloAlpha: .20, settledStrength: .20,
  velocityWindowFrames: 6, luminanceAnchor: .36, minimumLightingFactor: .58,
  reliefLightingEnabled: true
 }, ...clone(input)};
 if (!rgb(p.centerColor) || !rgb(p.haloColor)) throw Error('CONTROL_FRONTIER_RGB_REQUIRED');
 for (const [name, minimum, maximum] of [
  ['centerWidthPixels', .5, 2.5], ['haloSigmaPixels', .5, 4], ['haloSupportPixels', 2, 10],
  ['centerAlpha', 0, 1], ['haloAlpha', 0, .35], ['settledStrength', 0, .45],
  ['luminanceAnchor', .05, 1], ['minimumLightingFactor', .3, 1]
 ]) if (!Number.isFinite(p[name]) || p[name] < minimum || p[name] > maximum)
  throw Error('CONTROL_FRONTIER_STYLE_RANGE_REQUIRED_' + name);
 if (p.haloSupportPixels <= p.haloSigmaPixels || p.haloSupportPixels <= p.centerWidthPixels)
  throw Error('CONTROL_FRONTIER_FINITE_HALO_SUPPORT_REQUIRED');
 if (!Number.isSafeInteger(p.velocityWindowFrames) || p.velocityWindowFrames < 1 || p.velocityWindowFrames > 30)
  throw Error('CONTROL_FRONTIER_VELOCITY_WINDOW_REQUIRED');
 if (typeof p.reliefLightingEnabled !== 'boolean') throw Error('CONTROL_FRONTIER_LIGHTING_BOOLEAN_REQUIRED');
 return Object.freeze(p);
}

/** No timer, pulse cycle, random state or guessed end stop. The light responds
 * only to measured displacement of the existing evaluated boundary. A finite
 * temporal window settles the light when that boundary actually stops advancing.
 */
export function compileControlFrontierLightMotion(territoryPlan, profile) {
 const plan = assertTerritoryControlPlan(territoryPlan), p = validateControlFrontierLightProfile(profile),
  frames = Array.from({length: plan.totalFrames}, (_, index) =>
   evaluateTerritoryControlFrame(plan, plan.startFrame + index)), speeds = frames.map((_frame, index) => {
   const left = Math.max(0, index - p.velocityWindowFrames),
    right = Math.min(plan.totalFrames - 1, index + p.velocityWindowFrames),
    a = frames[left].boundaryLatitudes, b = frames[right].boundaryLatitudes;
   return b.reduce((sum, latitude, knot) => sum + Math.abs(latitude - a[knot]), 0)
    / a.length / Math.max(1, right - left);
  }), peakSpeed = Math.max(...speeds), strengths = speeds.map(speed =>
   p.settledStrength + (1 - p.settledStrength) * Math.sqrt(peakSpeed > 0 ? clamp(speed / peakSpeed) : 0));
 return Object.freeze({version: REFERENCE_CONTROL_FRONTIER_LIGHT_V3_VERSION,
  startFrame: plan.startFrame, totalFrames: plan.totalFrames, peakSpeed,
  speeds: Object.freeze(speeds), strengths: Object.freeze(strengths),
  domainGeometryBinding: plan.domainGeometryBinding, boundaryKeyframeBinding: plan.boundaryKeyframeBinding,
  timingSource: 'UNCHANGED_EVALUATED_CONTROL_BOUNDARY_DISPLACEMENT', syntheticPulse: false,
  stopAssumedAtOutputEnd: false});
}

export function evaluateControlFrontierLightMotion(motion, frame) {
 const index = frame - motion.startFrame;
 if (motion.version !== REFERENCE_CONTROL_FRONTIER_LIGHT_V3_VERSION || !Number.isSafeInteger(frame)
  || index < 0 || index >= motion.totalFrames) throw Error('CONTROL_FRONTIER_FRAME_OUT_OF_RANGE');
 return {frame, strength: motion.strengths[index], speedDegreesPerFrame: motion.speeds[index],
  advancing: motion.speeds[index] > 0, stopAssumedAtOutputEnd: false};
}

/** CPU oracle for the pointwise real-terrain destination light multiplier. */
export function controlTerrainLightingFactor(terrainRgb, profile) {
 const p = validateControlFrontierLightProfile(profile);
 if (!rgb(terrainRgb)) throw Error('CONTROL_FRONTIER_ACTUAL_TERRAIN_RGB_REQUIRED');
 const luminance = terrainRgb[0] * .2126 + terrainRgb[1] * .7152 + terrainRgb[2] * .0722;
 return p.minimumLightingFactor + (1 - p.minimumLightingFactor) * clamp(luminance / p.luminanceAnchor);
}

const vertexSource = `#version 300 es
precision highp float;
layout(location=0) in vec2 position;layout(location=1) in vec2 geographic;
uniform vec2 screenSize;out vec2 geo;
void main(){geo=geographic;gl_Position=vec4(position.x/screenSize.x*2.-1.,1.-position.y/screenSize.y*2.,0.,1.);}`;
const fragmentContext = `
precision highp float;precision highp int;
in vec2 geo;out vec4 frag;
uniform vec2 screenSize;uniform vec4 safeArea;
uniform vec4 reservations[64];uniform int reservationCount;
void protect(){vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y);
 if(p.x<safeArea.x||p.y<safeArea.y||p.x>safeArea.z||p.y>safeArea.w)discard;
 for(int i=0;i<64;i++){if(i>=reservationCount)break;vec4 b=reservations[i];
  if(p.x>=b.x&&p.y>=b.y&&p.x<=b.z&&p.y<=b.w)discard;}}
`;
const lightingFragment = `#version 300 es
${fragmentContext}
uniform sampler2D actualTerrain;uniform float luminanceAnchor,minimumLightingFactor;
void main(){protect();vec3 terrain=texture(actualTerrain,gl_FragCoord.xy/screenSize).rgb;
 float y=dot(terrain,vec3(.2126,.7152,.0722));
 float light=mix(minimumLightingFactor,1.,clamp(y/luminanceAnchor,0.,1.));
 frag=vec4(vec3(light),1.);}`;
const frontierFragment = `#version 300 es
${fragmentContext}
uniform vec2 controlKnots[64];uniform int knotCount;
uniform vec3 centerColor,haloColor;
uniform float centerWidthPixels,haloSigmaPixels,haloSupportPixels,centerAlpha,haloAlpha,strength;
float movingBoundary(float lon){
 if(lon<=controlKnots[0].x)return controlKnots[0].y;
 for(int i=1;i<64;i++){if(i>=knotCount)break;
  if(lon<=controlKnots[i].x){vec2 a=controlKnots[i-1],b=controlKnots[i];
   return mix(a.y,b.y,clamp((lon-a.x)/(b.x-a.x),0.,1.));}}
 return controlKnots[knotCount-1].y;
}
void main(){protect();
 // This scalar is the unchanged control shader's moving boundary, evaluated
 // from the same trusted frame. No separate line vertices or moving path exist.
 float field=movingBoundary(geo.x)-geo.y;
 float pixelDistance=abs(field)/max(length(vec2(dFdx(field),dFdy(field))),1.e-7);
 if(pixelDistance>=haloSupportPixels)discard;
 float core=(1.-smoothstep(max(0.,centerWidthPixels*.5-.35),centerWidthPixels*.5+.35,pixelDistance))*centerAlpha*strength;
 float halo=exp(-.5*pow(pixelDistance/haloSigmaPixels,2.))*haloAlpha*strength
  *(1.-smoothstep(haloSupportPixels-1.,haloSupportPixels,pixelDistance));
 float alpha=core+halo*(1.-core);
 if(alpha<=0.)discard;
 frag=vec4((centerColor*core+haloColor*halo*(1.-core))/alpha,alpha);
}`;

function createProgram(gl, fragment) {
 const program = gl.createProgram(), shaders = [];
 try {
  for (const [type, source] of [[gl.VERTEX_SHADER, vertexSource], [gl.FRAGMENT_SHADER, fragment]]) {
   const shader = gl.createShader(type); shaders.push(shader); gl.shaderSource(shader, source); gl.compileShader(shader);
   if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw Error('CONTROL_FRONTIER_SHADER_' + gl.getShaderInfoLog(shader));
   gl.attachShader(program, shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error('CONTROL_FRONTIER_LINK_' + gl.getProgramInfoLog(program));
  return program;
 } catch (error) { gl.deleteProgram(program); throw error; }
 finally { shaders.forEach(shader => gl.deleteShader(shader)); }
}

/** The native renderer owns projection/triangulation. Dynamic imports keep the
 * profile and timing oracles executable in Node without a browser THREE alias.
 */
export async function createControlFrontierLightPassV3({canvas, territoryPlan, landDomain, profile,
 width = 1080, height = 1920} = {}) {
 const plan = assertTerritoryControlPlan(territoryPlan), material = validateControlFrontierLightProfile(profile),
  motion = compileControlFrontierLightMotion(plan, material), domain = landDomain ?? plan.intent.domain;
 if (!same(domain, plan.intent.domain)) throw Error('CONTROL_FRONTIER_SOURCE_DOMAIN_BINDING_REQUIRED');
 if (width !== 1080 || height !== 1920 || canvas?.width !== width || canvas?.height !== height)
  throw Error('CONTROL_FRONTIER_CANONICAL_OUTPUT_REQUIRED');
 const gl = canvas.getContext('webgl2');
 if (!gl) throw Error('CONTROL_FRONTIER_NATIVE_WEBGL2_REQUIRED');
 const [{triangulateRegion, polygons}, {captureFlowNativeGlState, restoreFlowNativeGlState}] = await Promise.all([
  import('./renderer.mjs'), import('./flow_graphic_pass_v2.mjs')]);
 const domains = domain.map(item => {
  const record = {geometry_type: item.geometry.type, coordinates: item.geometry.coordinates},
   result = triangulateRegion(record, geographic => [...geographic]);
  try {
   const position = result.mesh.getAttribute('position'), index = result.mesh.getIndex(),
    geographic = new Float32Array(index.count * 2);
   for (let vertex = 0; vertex < index.count; vertex++) {
    const sourceVertex = index.getX(vertex);
    geographic.set([position.getX(sourceVertex), position.getY(sourceVertex)], vertex * 2);
   }
   return {id: item.id, geographic, parts: polygons(record).length, triangles: index.count / 3};
  } finally { result.mesh.dispose(); }
 }), state = captureFlowNativeGlState(gl), programs = {}, uniforms = {};
 let buffer, vao, disposed = false;
 try {
  programs.lighting = createProgram(gl, lightingFragment); programs.frontier = createProgram(gl, frontierFragment);
  const common = ['screenSize', 'safeArea', 'reservations[0]', 'reservationCount'];
  for (const [kind, names] of [['lighting', [...common, 'actualTerrain', 'luminanceAnchor', 'minimumLightingFactor']],
   ['frontier', [...common, 'controlKnots[0]', 'knotCount', 'centerColor', 'haloColor', 'centerWidthPixels',
    'haloSigmaPixels', 'haloSupportPixels', 'centerAlpha', 'haloAlpha', 'strength']]])
   uniforms[kind] = Object.fromEntries(names.map(name => [name, gl.getUniformLocation(programs[kind], name)]));
  vao = gl.createVertexArray(); buffer = gl.createBuffer(); gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  for (const [index, offset] of [[0, 0], [1, 8]]) {
   gl.enableVertexAttribArray(index); gl.vertexAttribPointer(index, 2, gl.FLOAT, false, 16, offset);
  }
 } catch (error) {
  Object.values(programs).forEach(program => gl.deleteProgram(program));
  if (buffer) gl.deleteBuffer(buffer); if (vao) gl.deleteVertexArray(vao); throw error;
 } finally { restoreFlowNativeGlState(gl, state); }
 const setCommon = (kind, safeArea, reservations) => {
  gl.useProgram(programs[kind]); gl.uniform2fv(uniforms[kind].screenSize, [width, height]);
  gl.uniform4fv(uniforms[kind].safeArea, safeArea);
  const packed = new Float32Array(MAX_RESERVATIONS * 4);
  reservations.forEach((reservation, index) => packed.set(reservation.box, index * 4));
  gl.uniform4fv(uniforms[kind]['reservations[0]'], packed);
  gl.uniform1i(uniforms[kind].reservationCount, reservations.length);
 };
 return {
  evidence: {version: REFERENCE_CONTROL_FRONTIER_LIGHT_V3_VERSION,
   composition: 'UNCHANGED_TERRITORY_FILL_THEN_ACTUAL_TERRAIN_DESTINATION_LIGHT_THEN_REAL_CONTROL_MATERIAL_EDGE',
   sourceGeometryMutation: false, controlEngine: 'UNCHANGED_TERRITORY_CONTROL_ADAPTER_V1',
   triangulation: 'UNCHANGED_NATIVE_RENDERER_TRIANGULATE_REGION', separateLineGeometry: false,
   arrowVisuals: false, routeVisuals: false, decorativePaths: false, referenceFrameTextureSampling: false,
   terrainSampler: 'ONLY_ACTUAL_CURRENT_NATIVE_TERRAIN_RGB_SNAPSHOT', lightProfile: clone(material),
   boundaryKeyframeBinding: plan.boundaryKeyframeBinding, domainGeometryBinding: plan.domainGeometryBinding},
  draw({controls, project, actualTerrainTexture, presentationScale, safeArea = [0, 0, width, height],
   protectedGraphics = []} = {}) {
   if (disposed) throw Error('CONTROL_FRONTIER_DISPOSED');
   if (!controls || typeof project !== 'function' || !box(safeArea)
    || !Number.isFinite(presentationScale) || presentationScale < 1 || presentationScale > 2)
    throw Error('CONTROL_FRONTIER_ACTUAL_FRAME_CONTEXT_REQUIRED');
   const expected = evaluateTerritoryControlFrame(plan, controls.frame);
   if (!same(controls, expected)) throw Error('CONTROL_FRONTIER_EVALUATED_FRAME_BINDING_REQUIRED');
   if (material.reliefLightingEnabled && (!actualTerrainTexture || !gl.isTexture(actualTerrainTexture)))
    throw Error('CONTROL_FRONTIER_CURRENT_ACTUAL_TERRAIN_TEXTURE_REQUIRED');
   if (!Array.isArray(protectedGraphics) || protectedGraphics.length > MAX_RESERVATIONS
    || protectedGraphics.some(reservation => !box(reservation.box))) throw Error('CONTROL_FRONTIER_PROTECTION_BOUNDS_REQUIRED');
   const energy = evaluateControlFrontierLightMotion(motion, controls.frame), packedKnots = new Float32Array(MAX_KNOTS * 2);
   controls.longitudinalKnots.forEach((longitude, index) => {
    // The old oracle validates the trusted frame and establishes the same exact
    // boundary used by the unchanged ownership field at every supplied knot.
    const latitude = sampleControlBoundary(controls, longitude);
    if (Math.abs(latitude - controls.boundaryLatitudes[index]) > 1e-10)
     throw Error('CONTROL_FRONTIER_ORACLE_BINDING_REQUIRED');
    packedKnots.set([longitude, latitude], index * 2);
   });
   const saved = captureFlowNativeGlState(gl), nativeWidths = {
    center: material.centerWidthPixels / presentationScale, sigma: material.haloSigmaPixels / presentationScale,
    support: material.haloSupportPixels / presentationScale};
   try {
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER, null); gl.drawBuffers([gl.BACK]); gl.viewport(0, 0, width, height);
    for (const flag of [gl.DEPTH_TEST, gl.STENCIL_TEST, gl.CULL_FACE, gl.POLYGON_OFFSET_FILL,
     gl.RASTERIZER_DISCARD, gl.SAMPLE_ALPHA_TO_COVERAGE, gl.SAMPLE_COVERAGE, gl.DITHER, gl.SCISSOR_TEST]) gl.disable(flag);
    gl.depthMask(false); gl.colorMask(true, true, true, true); gl.enable(gl.BLEND);
    gl.blendEquationSeparate(gl.FUNC_ADD, gl.FUNC_ADD); gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    const batches = domains.map(item => {
     const data = new Float32Array(item.geographic.length * 2);
     for (let index = 0; index < item.geographic.length; index += 2) {
      const geographic = [item.geographic[index], item.geographic[index + 1]], screen = project(geographic);
      if (!point(screen)) throw Error('CONTROL_FRONTIER_NATIVE_PROJECTION_REQUIRED');
      data.set([...screen, ...geographic], index * 2);
     }
     return data;
    });
    if (material.reliefLightingEnabled) {
     setCommon('lighting', safeArea, protectedGraphics); gl.activeTexture(gl.TEXTURE0); gl.bindSampler(0, null);
     gl.bindTexture(gl.TEXTURE_2D, actualTerrainTexture); gl.uniform1i(uniforms.lighting.actualTerrain, 0);
     gl.uniform1f(uniforms.lighting.luminanceAnchor, material.luminanceAnchor);
     gl.uniform1f(uniforms.lighting.minimumLightingFactor, material.minimumLightingFactor);
     // Multiply existing classified fill RGB, retaining destination alpha.
     // The source multiplier is bounded <=1 on a normalized framebuffer.
     gl.blendFuncSeparate(gl.DST_COLOR, gl.ZERO, gl.ZERO, gl.ONE);
     batches.forEach(data => { gl.bufferData(gl.ARRAY_BUFFER, data, gl.STREAM_DRAW); gl.drawArrays(gl.TRIANGLES, 0, data.length / 4); });
    }
    setCommon('frontier', safeArea, protectedGraphics);
    gl.uniform2fv(uniforms.frontier['controlKnots[0]'], packedKnots);
    gl.uniform1i(uniforms.frontier.knotCount, controls.longitudinalKnots.length);
    gl.uniform3fv(uniforms.frontier.centerColor, material.centerColor); gl.uniform3fv(uniforms.frontier.haloColor, material.haloColor);
    for (const [name, value] of [['centerWidthPixels', nativeWidths.center], ['haloSigmaPixels', nativeWidths.sigma],
     ['haloSupportPixels', nativeWidths.support], ['centerAlpha', material.centerAlpha],
     ['haloAlpha', material.haloAlpha], ['strength', energy.strength]]) gl.uniform1f(uniforms.frontier[name], value);
    gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    batches.forEach(data => { gl.bufferData(gl.ARRAY_BUFFER, data, gl.STREAM_DRAW); gl.drawArrays(gl.TRIANGLES, 0, data.length / 4); });
   } finally { restoreFlowNativeGlState(gl, saved); }
   const glError = gl.getError(); if (glError !== gl.NO_ERROR) throw Error('CONTROL_FRONTIER_GL_ERROR_' + glError);
   return {version: REFERENCE_CONTROL_FRONTIER_LIGHT_V3_VERSION, frame: controls.frame,
    geometryUnchanged: true, controlKeyframesUnchanged: true, evaluatedBoundaryBinding: plan.boundaryKeyframeBinding,
    ownershipClassifierRewritten: false, separateLineGeometry: false, arrows: 0, routeTraces: 0,
    landClippedByActualSourceTriangles: true, parts: domains.map(({geographic, ...item}) => item),
    actualTerrainSnapshotConsumed: material.reliefLightingEnabled,
    lighting: {blend: 'DST_COLOR_ZERO_DESTINATION_RGB_MULTIPLICATION', luminanceAnchor: material.luminanceAnchor,
     minimumFactor: material.minimumLightingFactor, maximumFactor: 1, glowOutsideLand: false},
    frontier: {...energy, centerWidthOutputPixels: material.centerWidthPixels,
     haloSupportOutputPixels: material.haloSupportPixels, haloSigmaOutputPixels: material.haloSigmaPixels,
     nativeWidths, presentationScale, temporalBlink: false, stopAssumedAtOutputEnd: false},
    nativeStateRestored: true, glError};
  },
  dispose() {
   if (disposed) return; const saved = captureFlowNativeGlState(gl);
   try { Object.values(programs).forEach(program => gl.deleteProgram(program));
    gl.deleteBuffer(buffer); gl.deleteVertexArray(vao); disposed = true;
   } finally { restoreFlowNativeGlState(gl, saved); }
  }
 };
}
