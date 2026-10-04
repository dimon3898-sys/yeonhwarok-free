# 3D Space Objects

🇫🇷 [Version française](README.fr.md)

> Interactive 3D solar system visualization built with Three.js and Vite.

🔗 [space-objects.vercel.app](https://space-objects.vercel.app) · [GitHub](https://github.com/Tarasteed/SpaceObjects)

---

## Tech Stack

| Tool | Role |
|---|---|
| [Vite](https://vitejs.dev) | Dev server + bundler |
| [Three.js](https://threejs.org) | WebGL 3D engine |

---

## Installation

```bash
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.
Also hosted on Vercel: https://space-objects.vercel.app/

```bash
npm run build    # Production build → dist/ folder
npm run preview  # Preview production build locally
```

---

## Project Structure

```
SpaceObjects/
├── public/
│   ├── textures/        ← Planet + skybox JPG/PNG textures
│   ├── audio/           ← Music and sound effects
│   └── favicon.svg      ← SVG favicon
├── src/
│   ├── main.js          ← Entry point, animation loop, stars, skybox, galaxy
│   ├── scene.js         ← Renderer, camera, lights, OrbitControls
│   ├── objects.js       ← 3D sphere, ring and label creation
│   ├── camera.js        ← Camera animations (zoom lerp, planet following, FOV)
│   ├── ui.js            ← Sidebar, tooltips, HUD buttons, display panel
│   ├── data.js          ← Source of truth: 3D + UI data for each object
│   ├── i18n.js          ← FR/EN translations (auto-detected from browser language)
│   ├── state.js         ← Global simulation state (pause, speed)
│   ├── audio.js         ← Ambient music + sound effects + fades
│   ├── loader.js        ← Shared Three.js LoadingManager
│   └── style.css        ← Canvas layout + futuristic UI
├── index.html
└── package.json
```

---

## Textures

Planet textures from [solarsystemscope.com/textures](https://www.solarsystemscope.com/textures).
Pluto: [planet-texture-maps.fandom.com/wiki/Pluto](https://planet-texture-maps.fandom.com/wiki/Pluto)
Skybox: https://svs.gsfc.nasa.gov/4851

| File | Object |
|---|---|
| `8k_sun.jpg` | Sun |
| `8k_mercury.jpg` | Mercury |
| `4k_venus_atmosphere.jpg` | Venus (clouds) |
| `8k_venus_surface.jpg` | Venus (surface) |
| `8k_earth_daymap.jpg` | Earth (day) |
| `8k_earth_nightmap.jpg` | Earth (night — city lights) |
| `8k_earth_clouds.jpg` | Earth (clouds) |
| `8k_mars.jpg` | Mars |
| `8k_jupiter.jpg` | Jupiter |
| `8k_saturn.jpg` | Saturn |
| `8k_saturn_ring_alpha.png` | Saturn rings |
| `2k_uranus.jpg` | Uranus |
| `2k_neptune.jpg` | Neptune |
| `8k_moon.jpg` | Moon |
| `4k_Phobos.png` | Phobos |
| `4k_Deimos.png` | Deimos |
| `4k_Io.png` | Io |
| `4k_Europa.png` | Europa |
| `2k_Ganymede.png` | Ganymede |
| `4k_Callisto.png` | Callisto |
| `2k_Titan.png` | Titan |
| `4k_Tritton.png` | Triton |
| `4k_pluto.jpg` | Pluto |
| `4k_eris.jpg` | Eris |
| `4k_haumea.jpg` | Haumea |
| `4k_makemake.jpg` | Makemake |
| `starmap.jpg` | Skybox (NASA star map — [source](https://svs.gsfc.nasa.gov/4851)) |
| `lensflare0.png` | Sun lens flare |
| `asteroid_c.jpg` | C-type — [source](https://ambientcg.com/get?file=Rock026_1K-JPG.zip) |
| `asteroid_s.jpg` | S-type — [source](https://ambientcg.com/get?file=Rock023_1K-JPG.zip) |
| `asteroid_m.jpg` | M-type — [source](https://ambientcg.com/get?file=Rock032_1K-JPG.zip) |

---

## Credits

| Resource | Author | License |
|---|---|---|
| Music "Celestial" | [Scott Buckley](https://www.scottbuckley.com.au) | CC BY 4.0 |
| Planet textures | [Solar System Scope](https://www.solarsystemscope.com/textures) | CC BY 4.0 |
| Skybox | [NASA SVS](https://svs.gsfc.nasa.gov/4851) | Public domain |
| Asteroid textures | [ambientCG](https://ambientcg.com) | CC0 |
| Galaxy image | Pinwheel Galaxy M101 — NASA/ESA Hubble | Public domain |

---

## Objects

| Type | Objects |
|---|---|
| Star | Sun |
| Planets | Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune |
| Natural satellites | Moon, Phobos, Deimos, Io, Europa, Ganymede, Callisto, Titan, Triton |
| Belts | Asteroid Belt (Mars–Jupiter), Kuiper Belt (beyond Neptune) |
| Dwarf planets | Pluto, Eris, Haumea, Makemake |

---

## Features

- 3D WebGL rendering with Three.js + post-processing bloom (UnrealBloomPass)
- Photographic NASA skybox (Milky Way)
- Procedurally generated stars (4 types: orange, yellow, white, blue) — speed synced to simulation
- Orbital animations via pivots (`Object3D`) — no manual sin/cos
- Realistic orbital and axial tilts (Venus and Uranus retrograde)
- Realistic lighting from the Sun (`PointLight` decay + fill light)
- Solar convection shader (FBM noise, hot/cold cells)
- Sun lens flare (3 layers of additive sprites)
- Saturn rings with alpha texture and corrected radial UVs
- 13 procedural Uranus rings at true NASA proportions
- Planetary atmospheres (radial gradient additive sprites)
- Earth clouds + Venus atmosphere (semi-transparent sphere)
- City lights on Earth's dark side (emissiveMap)
- Procedural asteroid belt (InstancedMesh, 3 types C/S/M, Kepler's law)
- Procedural Kuiper Belt (beyond Neptune, encompasses dwarf planets)
- Pluto and dwarf planets to scale (Eris, Haumea, Makemake)
- Extra moons with dedicated textures (Phobos, Deimos, Io, Europa, Ganymede, Callisto, Titan, Triton)
- Smooth zoom to planet with real-time tracking (lerp)
- Speed effect in ZOOMING mode — widened FOV + CSS blur
- Progressive slowdown on pause, acceleration on resume (ease-out/ease-in over 1s)
- Orbit around selected planet (drag + scroll wheel + mobile pinch)
- Click on a planet in the scene to zoom (raycasting)
- Dedicated asteroid belt and Kuiper Belt views from sidebar
- Return to system view + Escape key
- Foldable futuristic sidebar with collapsible groups, hover highlight via halo/emissive
- Click tooltips with scientific data + real orbital speed (km/s) live
- Collapsible tooltip via toggle button — frees screen space on mobile
- Pause / simulation speed control (×0.01 to ×20, default ×0.5, logarithmic slider)
- Show / hide orbits, planet labels, moon labels, belt labels
- Orbital trails — per-vertex gradient, length scaled to real angular velocity
- Animated splash screen (SVG logo) with loading bar — Explorer button unlocked at 100%
- Keyboard shortcuts displayed on splash screen
- Followed planet name in browser tab title
- Cinematic mode (hide all HUDs) on double click / double tap
- Ambient space music in loop with progressive fade-in
- Volume control + music pause/play in HUD
- Atmospheric hum varying with distance to planet (volume fade)
- Volume fade synchronized with pause/resume slowdown
- Atmospheric sound and belt crackle properly managed on pause
- Sonar ping on sidebar click / raycasting
- Distinct pause and resume sounds
- Swoosh on solar system return
- Responsive mobile interface (collapsible sidebar, adaptive HUDs, collapsible tooltip, touch events)
- Auto-detected FR/EN language based on browser settings
- Layered galaxy image simulating disk thickness
- Debug panel accessible via `?debug=true` (FPS, frame time, draw calls, DPR)
- SVG favicon + animated logo

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Pause / resume simulation |
| `Escape` | Return to solar system view |
| `Double click` | Hide / show HUD |
| `P` | Log camera position to console (debug) |

---

## Known Bugs

| Status | Description |
|---|---|
| ✅ Fixed | Stars appearing as squares when zoomed in |
| ✅ Fixed | Zoom not tracking planet in real time |
| ✅ Fixed | Zoom locked after focusing on a planet |
| ✅ Fixed | Wrong UV mapping on Saturn rings |
| ✅ Fixed | Orbital trails going the wrong way / offset |
| ✅ Fixed | Camera sometimes unable to orbit around planet |
| ✅ Fixed | Atmospheric sound not restarting when switching planets |
| ✅ Fixed | HUD sim/audio different widths on mobile |
| ✅ Fixed | Unable to navigate between planets without going through sidebar |
| ✅ Fixed | Context sounds restarting on navigation while paused |
| ✅ Fixed | Belt focus → pause → return to system → click belt → play → no sound |
| ✅ Fixed | Labels overlapping the sidebar |
| ✅ Fixed | Triton orbiting in a wave due to axialTilt |
| ✅ Fixed | Titan's rotation speed identical to Neptune's |
| ✅ Fixed | Camera could pass through planet instead of following from outside |
| ✅ Fixed | City lights disappearing on sidebar click (emissiveIntensity overwritten) |
| ✅ Fixed | Unable to move in follow mode on mobile (missing touch events) |
| ✅ Fixed | Sidebar overlapping display button on mobile |
| | Slight snap at end of zoom due to planet moving during lerp |
| | Dwarf planet trails slightly ahead (angular velocity too low for vertex resolution) |

---

## Roadmap

### Camera & Navigation
- ✅ Smooth zoom to planet with real-time tracking
- ✅ Orbit around selected planet (mouse drag + mobile touch)
- ✅ Return to solar system view button
- ✅ Escape key to return from anywhere
- ✅ Click on a planet in the scene to zoom (raycasting)
- ✅ Planet-to-planet navigation without returning to system view
- ✅ Progressive dezoom to galaxy scale
- [ ] Scroll-wheel zoom from system view toward a planet (without click)?
- [ ] Free cam mode

### Interface
- ✅ Pause / simulation speed control (×0.01 to ×20)
- ✅ Slowdown effect before pause and acceleration on resume
- ✅ Show / hide orbits
- ✅ Show / hide planet, moon and belt labels
- ✅ Music control (volume + pause/play)
- ✅ Click belts from sidebar
- ✅ GitHub link in sidebar
- ✅ Collapsible sidebar with collapsible groups (desktop + mobile)
- ✅ Responsive mobile interface
- ✅ Collapsible tooltip (toggle button − / +)
- ✅ Real orbital speed in tooltip (follow mode, live jitter)
- ✅ Custom HUD-style cursor
- ✅ Hover highlight on sidebar items (halo for planets, emissive for belts)
- ✅ Hide all HUDs on double click / double tap
- ✅ Keyboard shortcuts in splash screen
- ✅ Followed planet name in browser tab title
- ✅ Moons grouped under their parent planet in sidebar
- ✅ FR/EN auto-translation

### Data
- ✅ Asteroid Belt (between Mars and Jupiter) — C/S/M-type textures
- ✅ Kuiper Belt (beyond Neptune)
- ✅ Uranus rings (13 rings at true NASA proportions)
- ✅ Pluto and dwarf planets to scale
- ✅ Real orbital speeds (km/s) in data.js — NASA Planetary Fact Sheets
- ✅ Extra moons — Mars (Phobos, Deimos), Jupiter (Io, Europa, Ganymede, Callisto), Saturn (Titan), Neptune (Triton)
- ✅ Wikipedia links in tooltip (FR + EN)

### Visual
- ✅ Realistic orbital and axial tilts
- ✅ Photographic NASA skybox (Milky Way)
- ✅ Multi-color procedural stars overlay
- ✅ Sun halo and lens flare
- ✅ Solar bloom flicker
- ✅ Solar convection shader (boiling surface)
- ✅ Planetary atmospheres
- ✅ Earth clouds / Venus atmosphere
- ✅ City lights on Earth's dark side
- ✅ 4k/8k textures
- ✅ Orbital trails (per-vertex gradient, length proportional to speed)
- ✅ Animated splash screen with SVG logo + loader
- ✅ SVG favicon
- ✅ Speed effect in ZOOMING mode (FOV + CSS blur)
- ✅ Galaxy image with layered disk thickness effect

### Technical
- ✅ Vercel hosting (`npm run build` → `dist/` folder)
- ✅ Splash screen with LoadingManager — button locked until fully loaded
- ✅ Shared LoadingManager via `loader.js` (avoids circular imports)
- ✅ Mobile optimization (collapsible sidebar, adaptive HUDs, touch events)
- ✅ `CameraMode` enum for camera states
- ✅ Debug panel via `?debug=true` URL param
- ✅ Mobile performance optimization (DPR cap, reduced bloom, damping)
- [ ] PWA — installable on mobile

### Sound Design
- ✅ Ambient space music (Scott Buckley — "Celestial", CC BY 4.0)
- ✅ Atmospheric hum in planet follow mode
- ✅ Atmospheric hum volume varying with distance to planet
- ✅ Atmospheric and belt sounds properly suspended/resumed on pause
- ✅ Volume fade synchronized with slowdown/acceleration
- ✅ Sonar ping on sidebar click / raycasting
- ✅ Swoosh on solar system return
- ✅ Distinct pause / resume sounds

### Bonus
- [ ] GLTF 3D models for probes (NASA 3D Models)
- [ ] Pull data from NASA Horizons instead of data.js
- [ ] Historical probes (Voyager 1 & 2, New Horizons, Juno) via satellite.js

---

## Ideas to Explore

### Cinematics & Visual
- **Cosmic dust particles** — in FOLLOWING mode, a few hundred very slow particles drifting in front of the camera. Gives a sense of vastness without impacting the system view.
- **Galaxies / Nebulae** — add distant galaxies and nebulae to the background.

### Sound Design
- **Planet-type differentiated sounds** — deep hum for gas giants (Jupiter, Saturn, Uranus, Neptune), dry mineral hum for rocky planets. Two audio files would be enough.

### Data & Realism
- **URL sharing** — `?planet=earth` in the URL to land directly on a planet. Useful for sharing a specific view.
- **Realistic mode** — distances, sizes and speeds at true scale with substitute sprites for planets too small to display (à la NASA Eyes).

### Interface
- **System minimap** — a small corner indicator showing the camera's relative position in the solar system. Helps with orientation during distant zooms.

---

## Development Notes

**Orbit pivots**
Each planet is a child of an invisible `Object3D` placed at the center. Rotating the pivot around Y makes the planet orbit without manually computing sin/cos. Moons are children of pivots attached to the parent mesh via the `extraMoons` system (parentId) — they automatically inherit all parent transformations.

**Orbital trails (vertexColors)**
Each orbit uses a `BufferAttribute` of per-vertex colors updated every frame. The conversion `planetAngle = -pivot.rotation.y` is required because Three.js Y rotation is in the opposite direction to vertex numbering. Trail length is `BASE_TRAIL + angularVelocity * EXT_FRAMES`.

**Belts (InstancedMesh)**
3 `InstancedMesh` per belt (one per C/S/M type) — 1 draw call per type regardless of count. Keplerian speeds (`v ∝ 1/√r`), individual eccentricity, logarithmic size distribution. `MeshBasicMaterial` to bypass distance falloff from the solar `PointLight`.

**Camera follow mode**
`OrbitControls` is `dispose()`d in follow mode. Camera position is computed manually via `THREE.Spherical` — drag, scroll wheel and mobile pinch are handled by dedicated canvas listeners. `setSkipControlsUpdate(true)` prevents `controls.update()` from overwriting the position. FOV rises from 55° to 70° during ZOOMING for a speed effect.

**Progressive pause slowdown**
`triggerPause()` animates `sim.speedFactor` toward 0 (ease-out) or back to `speedBeforePause` (ease-in) over 1 second via `requestAnimationFrame`. `_isPausingSlowly` blocks the `wasPaused` tracker in the Three.js loop during animation. `_fadeRatioTarget` is the only variable `triggerPause` modifies for volume — the Three.js loop applies `setAtmoFadeRatio` and `setAsteroidFadeRatio` in one place, avoiding conflicts between two independent RAFs.

**Audio management**
Context sounds (atmo, belt) are suspended via `pause()` / `audioCtx.suspend()` rather than stopped — resuming is instant with no source recreation. Atmo uses `startAtmoHumSilent()` on resume to start at volume 0 and let `_fadeRatioTarget` rise progressively. Atmospheric hum varies with camera/planet distance via `setAtmoVolume()` (ignored during `_isPausingSlowly`).

**Live orbital speed (tooltip)**
`obj.speedKms` in `data.js` stores the real NASA value (km/s). `updateTooltipSpeed()` in `ui.js` applies a ±0.06 km/s jitter per frame on the `#tt-speed-live` element to simulate a live telemetry reading — without rebuilding the tooltip DOM.

**Collapsible sidebar**
`updateSidebarDependents(isCollapsed)` in `ui.js` updates `--sidebar-width` on `:root` (inherited by the entire DOM) and repositions `#display-panel-wrapper`, `#sim-hud`, `#audio-hud` and `#tooltip` based on collapsed state and screen size. A `resize` listener automatically re-syncs.

**Shared LoadingManager**
`loader.js` exports a single `TextureLoader` and `LoadingManager`. Avoids the circular import `main.js ↔ objects.js` by centralizing the loader in a third-party module.

**Solar light intensity**
Three.js r155+ uses physical units. `PointLight(0xfffde0, 400, 0, 2.3)` + fill light `(0xfffde0, 0.4, 0, 0)` for distant planets.

**Textures and Vite**
Textures must be in `public/` — Vite serves this folder at the root, accessible via `/textures/file.jpg` without relative paths.

**i18n**
Language is auto-detected from `navigator.language` at load time. `LANG` is `"en"` if the browser language starts with `"en"`, `"fr"` otherwise. All UI strings and object data (name, description, facts, Wikipedia links) are translated via `i18n.js` — no page reload needed, detection is instant.