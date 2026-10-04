import * as THREE from 'three';

/**
 * Original, lightweight civil airliner. No external mesh, logo or texture.
 * Local axes: +Y forward, +Z up, X span. Scene/controller owns scale and alpha.
 * Length 1.45; span approximately 1.10; all local surfaces above Z=-0.095.
 * Dimensions are a visual proxy, not an aircraft manufacturer's specification.
 */
const mix = (a, b, t) => a + (b - a) * t;
const BODY_Z = 0.004;
const BODY_PROFILE = [
  [-0.72, 0], [-0.698, 0.008], [-0.64, 0.026], [-0.54, 0.047],
  [-0.425, 0.062], [-0.29, 0.070], [0.36, 0.070], [0.47, 0.065],
  [0.55, 0.053], [0.625, 0.037], [0.68, 0.022], [0.715, 0.010], [0.73, 0],
];

// Monotone cubic Hermite radius interpolation avoids ring-by-ring flat spots
// while keeping the silhouette inside its supplied radius profile.
function radialProfile(keys) {
  const d = keys.slice(0, -1).map((p, i) =>
    (keys[i + 1][1] - p[1]) / (keys[i + 1][0] - p[0]));
  const slope = keys.map((p, i) => {
    if (i === 0) return d[0];
    if (i === keys.length - 1) return d.at(-1);
    if (d[i - 1] * d[i] <= 0) return 0;
    const h0 = p[0] - keys[i - 1][0], h1 = keys[i + 1][0] - p[0];
    const w0 = 2 * h1 + h0, w1 = h1 + 2 * h0;
    return (w0 + w1) / (w0 / d[i - 1] + w1 / d[i]);
  });
  return y => {
    if (y <= keys[0][0]) return keys[0][1];
    if (y >= keys.at(-1)[0]) return keys.at(-1)[1];
    let i = 0;
    while (keys[i + 1][0] < y) i++;
    const h = keys[i + 1][0] - keys[i][0], t = (y - keys[i][0]) / h;
    const r = (2*t*t*t - 3*t*t + 1)*keys[i][1]
      + (t*t*t - 2*t*t + t)*h*slope[i]
      + (-2*t*t*t + 3*t*t)*keys[i + 1][1]
      + (t*t*t - t*t)*h*slope[i + 1];
    return Math.max(0, r);
  };
}
const bodyRadius = radialProfile(BODY_PROFILE);

function sampledLathe(keys, sections, radialSegments) {
  const radius = radialProfile(keys), points = [];
  for (let i = 0; i <= sections; i++) {
    const y = mix(keys[0][0], keys.at(-1)[0], i / sections);
    points.push(new THREE.Vector2(radius(y), y));
  }
  return new THREE.LatheGeometry(points, radialSegments);
}

function buffer(positions, indices) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setIndex(indices);
  g.computeVertexNormals();
  g.computeBoundingBox();
  return g;
}

// The two curved surfaces and their span-end caps form a closed foil.
// Cosine chord sampling resolves the leading-edge radius; a closed NACA-style
// thickness law and a small camber replace flat extruded wing polygons.
function foil({span, leading, chord, baseZ = 0, dihedral = 0, camber = 0.012,
  thickness = 0.105, tipThickness = thickness, spanSteps = 20, chordSteps = 40}) {
  const p = [], idx = [], row = chordSteps + 1, layer = (spanSteps + 1) * row;
  for (let side = 0; side < 2; side++) {
    for (let j = 0; j <= spanSteps; j++) {
      const s = j / spanSteps, c = mix(chord[0], chord[1], s);
      for (let i = 0; i <= chordSteps; i++) {
        const u = (1 - Math.cos(Math.PI * i / chordSteps)) / 2;
        const ratio = mix(thickness, tipThickness, s);
        const half = 5 * ratio * c * (0.2969*Math.sqrt(u) - 0.126*u
          - 0.3516*u*u + 0.2843*u*u*u - 0.1036*u*u*u*u);
        const arch = 4 * camber * c * u * (1-u);
        p.push(mix(span[0], span[1], s), mix(leading[0], leading[1], s) - u*c,
          baseZ + s*dihedral + arch + (side === 0 ? half : -half));
      }
    }
  }
  for (let side = 0; side < 2; side++) {
    for (let j = 0; j < spanSteps; j++) for (let i = 0; i < chordSteps; i++) {
      const a = side*layer + j*row + i, b = a+1, c = a+row, d = c+1;
      if (side === 0) idx.push(a,b,c,b,d,c);
      else idx.push(a,c,b,b,c,d);
    }
  }
  for (let i = 0; i < chordSteps; i++) {
    const a = i, b = layer+i, c = a+1, d = b+1;
    idx.push(a,b,c,b,d,c);
    const e = spanSteps*row+i, f = layer+e;
    idx.push(e,e+1,f,e+1,f+1,f);
  }
  return buffer(p, idx);
}

// Small details are batched into a few meshes. Vertex normals survive merging;
// no animated geometry, instancing, shader extensions or local lights required.
function mergeGeometry(geometries) {
  const positions = [], normals = [], indices = [];
  let offset = 0;
  for (const g of geometries) {
    const p = g.getAttribute('position'), n = g.getAttribute('normal');
    for (let i = 0; i < p.count; i++) {
      positions.push(p.getX(i), p.getY(i), p.getZ(i));
      normals.push(n.getX(i), n.getY(i), n.getZ(i));
    }
    if (g.index) for (const i of g.index.array) indices.push(i + offset);
    else for (let i = 0; i < p.count; i++) indices.push(i + offset);
    offset += p.count;
    g.dispose();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  g.setIndex(indices);
  g.computeBoundingBox();
  return g;
}

function roundedRect(width, height, radius) {
  const x = -width/2, y = -height/2, s = new THREE.Shape();
  s.moveTo(x+radius,y);s.lineTo(x+width-radius,y);
  s.quadraticCurveTo(x+width,y,x+width,y+radius);
  s.lineTo(x+width,y+height-radius);
  s.quadraticCurveTo(x+width,y+height,x+width-radius,y+height);
  s.lineTo(x+radius,y+height);
  s.quadraticCurveTo(x,y+height,x,y+height-radius);
  s.lineTo(x,y+radius);s.quadraticCurveTo(x,y,x+radius,y);s.closePath();
  return s;
}

// Conform a rounded window/door outline to the actual curved fuselage, rather
// than attaching boxes or a second blue sphere to its sides.
function bodyDetail(shape, centerY, angle, side, lift = 0.00045) {
  const g = new THREE.ShapeGeometry(shape, 5), p = g.getAttribute('position');
  for (let i = 0; i < p.count; i++) {
    const y = centerY+p.getX(i), r = bodyRadius(y)+lift;
    const theta = angle+p.getY(i)/Math.max(bodyRadius(y),0.018);
    p.setXYZ(i,side*r*Math.cos(theta),y,BODY_Z+r*Math.sin(theta));
  }
  if (side < 0) {
    for (let i = 0; i < g.index.count; i += 3) {
      const a = g.index.array[i+1];g.index.array[i+1]=g.index.array[i+2];g.index.array[i+2]=a;
    }
  }
  g.computeVertexNormals();
  return g;
}

function cockpitPane(a, b) {
  const p = [], idx = [], nx = 8, ny = 4;
  for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) {
    const u = i/nx, v = j/ny, theta = mix(a,b,v);
    const y = mix(0.515,0.642,u), r = bodyRadius(y)+0.00065;
    p.push(r*Math.cos(theta),y,BODY_Z+r*Math.sin(theta));
  }
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const a0 = j*(nx+1)+i, b0 = a0+1, c0 = a0+nx+1, d0 = c0+1;
    idx.push(a0,b0,c0,b0,d0,c0);
  }
  return buffer(p,idx);
}

function fanGeometry() {
  const p = [], idx = [], blades = 22;
  for (let k = 0; k < blades; k++) {
    const offset = p.length/3, base = k*Math.PI*2/blades;
    for (let r = 0; r <= 3; r++) for (let w = 0; w <= 2; w++) {
      const u=r/3, radius=mix(0.0070,0.0298,u);
      const theta=base+mix(0.22,-0.13,u)+(w/2-.5)*mix(.21,.10,u);
      p.push(radius*Math.cos(theta),.053+Math.sin(u*Math.PI)*.0022,
        radius*Math.sin(theta));
    }
    for (let r = 0; r < 3; r++) for (let w = 0; w < 2; w++) {
      const a=offset+r*3+w,b=a+1,c=a+3,d=c+1;
      idx.push(a,b,c,b,d,c);
    }
  }
  return buffer(p,idx);
}

function bodyRibbons() {
  const pieces=[];
  for (const side of [-1,1]) {
    const p=[],idx=[],steps=48;
    for (let j=0;j<=steps;j++) {
      const y=mix(-.49,.455,j/steps),r=bodyRadius(y)+.0003;
      for (const theta of [-.102,-.074])
        p.push(side*r*Math.cos(theta),y,BODY_Z+r*Math.sin(theta));
    }
    for (let j=0;j<steps;j++) {
      const a=j*2,b=a+1,c=a+2,d=c+1;
      if(side>0)idx.push(a,c,b,b,c,d);else idx.push(a,b,c,b,d,c);
    }
    pieces.push(buffer(p,idx));
  }
  return mergeGeometry(pieces);
}

export function createAircraftV3() {
  const group = new THREE.Group();
  group.name = 'ORIGINAL_CIVIL_AIRLINER_V3';
  group.userData = {
    authorship: 'Original procedural project geometry; no external model or logo',
    localAxes: {forward:'+Y',up:'+Z',span:'X'}, visualProxy:true,
  };
  const paint = new THREE.MeshStandardMaterial({color:0xf2f1eb,metalness:.08,roughness:.29});
  const navy = new THREE.MeshStandardMaterial({color:0x182838,metalness:.08,roughness:.33});
  const glass = new THREE.MeshStandardMaterial({color:0x102330,metalness:.30,roughness:.16});
  const seam = new THREE.MeshStandardMaterial({color:0xaaaeb0,metalness:.08,roughness:.38});
  const intake = new THREE.MeshStandardMaterial({color:0x14202a,metalness:.20,roughness:.40});
  const fan = new THREE.MeshStandardMaterial({color:0x58636a,metalness:.45,roughness:.36,side:THREE.DoubleSide});
  const lip = new THREE.MeshStandardMaterial({color:0xe1e3e1,metalness:.28,roughness:.24});
  for(const m of [paint,navy,glass,seam,intake,fan,lip]) {
    m.name='V3_'+(m===paint?'IVORY_PAINT':m===navy?'NAVY_PAINT':m===glass?'GLAZING':m===seam?'DOOR_SEAM':m===intake?'INTAKE':m===fan?'FAN':'INLET_LIP');
    m.userData.originalAircraftPBR=true;
  }
  const add = (name, geometry, material, xyz=[0,0,0]) => {
    const mesh=new THREE.Mesh(geometry,material);mesh.name=name;
    mesh.position.set(...xyz);group.add(mesh);return mesh;
  };
  const pair = (name, geometry, material, x=0, y=0, z=0) => {
    for(const side of [-1,1]) {
      const mesh=add(`${name}_${side<0?'PORT':'STARBOARD'}`,geometry,material,[side*x,y,z]);
      if(side<0)mesh.scale.x=-1;
    }
  };

  add('FUSELAGE_SMOOTH_MONOCOQUE',sampledLathe(BODY_PROFILE,80,64),paint,[0,0,BODY_Z]);
  const fairing=new THREE.SphereGeometry(1,24,16);
  fairing.scale(.087,.198,.032);
  add('WING_BODY_FAIRING',fairing,paint,[0,-.024,-.027]);

  const mainWing=foil({span:[.052,.537],leading:[.175,-.285],chord:[.326,.100],
    baseZ:-.012,dihedral:.047,camber:.012,thickness:.105,tipThickness:.075});
  pair('SWEPT_CAMBERED_MAIN_WING',mainWing,paint);
  const stab=foil({span:[.020,.235],leading:[-.440,-.601],chord:[.247,.090],
    baseZ:.025,dihedral:.022,camber:.003,thickness:.08,tipThickness:.07,
    spanSteps:12,chordSteps:28});
  pair('HORIZONTAL_STABILIZER',stab,paint);
  const vertical=foil({span:[0,.218],leading:[-.412,-.599],chord:[.290,.094],
    camber:0,thickness:.085,tipThickness:.070,spanSteps:16,chordSteps:28});
  vertical.rotateY(-Math.PI/2);
  add('SWEPT_VERTICAL_FIN',vertical,navy,[0,0,.045]);
  const winglet=foil({span:[0,.043],leading:[-.285,-.315],chord:[.100,.058],
    camber:0,thickness:.060,spanSteps:10,chordSteps:20});
  winglet.rotateY(-75*Math.PI/180);
  pair('CANTED_WINGLET',winglet,paint,.537,0,.035);

  // Rounded nacelle, open inlet lip, recessed fan and a separate rear throat.
  // Maximum radius .044 at Z=-.047 keeps the static underside above -.095.
  const nacelle=sampledLathe([
    [-.117,.026],[-.106,.034],[-.085,.040],[-.035,.044],
    [.035,.0435],[.080,.0415],[.106,.038],[.116,.0358],
  ],28,40);
  const inletWall=sampledLathe([[.049,.0300],[.075,.0308],[.098,.0325],[.116,.0326]],12,40);
  // Reverse winding and normals, not vertex positions, for the inside wall.
  for(let i=0;i<inletWall.index.count;i+=3) {
    const b=inletWall.index.array[i+1];
    inletWall.index.array[i+1]=inletWall.index.array[i+2];
    inletWall.index.array[i+2]=b;
  }
  const innerNormals=inletWall.getAttribute('normal');
  for(let i=0;i<innerNormals.count;i++)
    innerNormals.setXYZ(i,-innerNormals.getX(i),-innerNormals.getY(i),-innerNormals.getZ(i));
  const inletLip=new THREE.TorusGeometry(.0342,.0026,8,40);
  inletLip.rotateX(Math.PI/2);inletLip.translate(0,.115,0);
  const exhaust=sampledLathe([[-.127,.019],[-.116,.022],[-.106,.027]],8,40);
  const exhaustShadow=new THREE.CircleGeometry(.0191,40);
  exhaustShadow.rotateX(Math.PI/2);exhaustShadow.translate(0,-.126,0);
  const fanDisk=new THREE.CircleGeometry(.0302,40);
  fanDisk.rotateX(-Math.PI/2);fanDisk.translate(0,.050,0);
  const fanBlades=fanGeometry();
  const spinner=sampledLathe([[.049,.0076],[.059,.0058],[.072,.0001]],8,32);
  const pylon=foil({span:[0,.030],leading:[.010,-.006],chord:[.118,.098],
    camber:0,thickness:.085,tipThickness:.075,spanSteps:8,chordSteps:20});
  pylon.rotateY(-Math.PI/2);
  pair('NACELLE_WHITE_CURVED_COWL',nacelle,paint,.235,-.015,-.047);
  pair('NACELLE_ROUNDED_INLET_LIP',inletLip,lip,.235,-.015,-.047);
  pair('NACELLE_RECESSED_INLET_WALL',inletWall,intake,.235,-.015,-.047);
  pair('NACELLE_FAN_SHADOW_DISK',fanDisk,intake,.235,-.015,-.047);
  pair('NACELLE_RECESSED_FAN_BLADES',fanBlades,fan,.235,-.015,-.047);
  pair('NACELLE_SPINNER',spinner,fan,.235,-.015,-.047);
  pair('NACELLE_REAR_THROAT',exhaust,intake,.235,-.015,-.047);
  pair('NACELLE_REAR_SHADOW',exhaustShadow,intake,.235,-.015,-.047);
  pair('NACELLE_PYLON',pylon,paint,.235,-.012,-.026);

  const cockpit=[];
  for(const [a,b] of [[.38,.91],[.98,1.50],[1.64,2.16],[2.23,2.76]])
    cockpit.push(cockpitPane(a,b));
  add('COCKPIT_FOUR_CONFORMAL_PANES',mergeGeometry(cockpit),glass);
  const windows=[],windowShape=roundedRect(.019,.017,.0047);
  for(const side of [-1,1]) for(let i=0;i<20;i++)
    windows.push(bodyDetail(windowShape,.408-i*.041,.30,side));
  add('CABIN_ROUNDED_WINDOW_ROWS',mergeGeometry(windows),glass);
  const doors=[];
  for(const y of [.463,-.462]) for(const side of [-1,1]) {
    const outline=roundedRect(.038,.060,.007);
    outline.holes.push(roundedRect(.0368,.0588,.0064));
    doors.push(bodyDetail(outline,y,.08,side,.0005));
  }
  add('CABIN_DOOR_FINE_OUTLINES',mergeGeometry(doors),seam);
  add('UNDERSTATED_NAVY_FUSELAGE_RIBBON',bodyRibbons(),navy);
  group.updateMatrixWorld(true);
  return group;
}
