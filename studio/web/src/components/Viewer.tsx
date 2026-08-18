"use client";

/**
 * The 3D stage.
 *
 * Two things shape this component:
 *
 * 1. **Geometry and colour are separate.** The GLB arrives with each part named
 *    `role::part` and no materials worth keeping. We build one material per
 *    role and assign by prefix, so changing a filament is `material.color.set()`
 *    — no fetch, no rebuild, no flicker. That is the whole reason the preview is
 *    affordable.
 *
 * 2. **Four views, one renderer.** The quadrant mode draws front / top / left /
 *    angled by scissoring a single canvas into four viewports rather than
 *    mounting four canvases. Four WebGL contexts on one page is how you find
 *    out browsers cap them at ~16 and start killing the oldest.
 *
 * Orbit control is hand-rolled (~40 lines) rather than pulled from
 * three/examples: it needs to drive four cameras at once in quadrant mode, and
 * OrbitControls binds to exactly one.
 */

import { useEffect, useEffectEvent, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { toCreasedNormals } from "three/examples/jsm/utils/BufferGeometryUtils.js";

export type ViewMode = "solid" | "quad";

export type RoleColours = Record<string, string>;

type Props = {
  url: string | null;
  colours: RoleColours;
  /** Matte filament reads as a rougher surface; the fuzzy skin option more so. */
  fuzzy?: boolean;
  /**
   * Roles to leave out of the render — currently `letters`, when the customer
   * has turned the glue-in letters off.
   *
   * Hiding rather than rebuilding is the point. The stand's name pockets are cut
   * into the body mesh either way, so the two variants share one GLB and one
   * cache entry; the toggle is a `visible` flag, not a fetch. That is the same
   * bargain colour and fuzzy already make — see `preview_keys` on the spec.
   */
  hiddenRoles?: string[];
  mode: ViewMode;
  status?: "idle" | "building" | "ready" | "failed";
  onReady?: () => void;
};

/**
 * The stainless bowl's base colour — a mid grey, not the near-white it was.
 *
 * #c9ccd1 is roughly what a steel bowl *photographs* as under bright light,
 * which already includes the lighting. Using it as a base colour double-counts
 * the exposure, and the bowl's flat floor then renders as a white disc with no
 * form. Same value and reasoning as BOWL_HEX in the offline renderer.
 */
const BOWL_COLOUR = "#9aa1a9";

/**
 * Above this angle, an edge is a real edge and shades sharp; below it, the
 * faces are approximating a curve and shade as one.
 *
 * The GLB ships welded vertices and no normals, so the only thing available
 * without this was `computeVertexNormals()`, which averages every face meeting
 * at a vertex — smoothing the bowl rim, the flat top and the letter sides as
 * though they were curved. That is most of why the render read as soft wax
 * rather than printed plastic.
 *
 * 12°, lowered from 25° (which was itself lowered from 40° after the honeycomb
 * grooves read as soft). This threshold turned out to control something bigger
 * than groove crispness: the vertical bands hanging below every paw.
 *
 * Cutting 16 paw recesses into the wall leaves the untouched part of that wall
 * retriangulated into slivers ~1 mm wide and up to 24 mm tall, running from each
 * recess down the drum. The geometry is exact — the wall is still a cylinder to
 * within 0.01 mm — but the recess rim is nearly tangent to the wall where the
 * two meet, so the dihedral there falls *under* a 25° threshold. Those rim faces
 * were therefore averaged into the wall's vertex normals, and a tilt of up to
 * 9.8° then interpolated down the full length of a sliver. That is the band.
 *
 * Measured, on the paw panel, as the shading normal's deviation from true radial
 * on the clean wall below the pads:
 *
 *   40°  26.1° max      25°  9.8° max      15°  2.4° max      12°  1.0° max
 *
 * 12° sits at the floor (1.0° is the cylinder's own 256-column faceting) while
 * staying above the recess interiors, whose dihedrals are 8.0° at the 90th
 * percentile — so the pads still shade smooth and only their rims go hard, which
 * is what a stamped impression should do anyway. The drums are ~200 columns,
 * under 2° between neighbours, so the cylinder itself is nowhere near this.
 *
 * Costs nothing: this is a normals fix, not a geometry one. Subdividing the wall
 * to bound the same smear needed 7× the triangles and blew the preview budget.
 */
const CREASE_ANGLE = (12 * Math.PI) / 180;

/**
 * Bambu's fuzzy skin, as the slicer actually produces it.
 *
 * These are not invented — they are read straight out of the generated 3MF's
 * `Metadata/project_settings.config`, so the picture is driven by the same
 * numbers the printer will be:
 *
 *   fuzzy_skin_thickness       0.3   mm of outward displacement
 *   fuzzy_skin_point_distance  0.8   mm between perturbed points along the path
 *   fuzzy_skin_octaves         4
 *   fuzzy_skin_persistence     0.5
 *   fuzzy_skin_mode            displacement
 *
 * The model is in millimetres, so object-space coordinates feed the noise
 * directly and the grain comes out at true scale.
 *
 * The anisotropy matters and is what makes it read as *printed* rather than as
 * generic bumpiness. Fuzzy skin perturbs each extrusion along its path, and
 * each layer is an independent pass — so variation is fine and uncorrelated in
 * Z at the layer pitch, and coarser around the wall at the point distance.
 * Isotropic noise looks like sandpaper; this looks like FDM.
 */
const FUZZ = {
  thicknessMm: 0.3,
  pointDistanceMm: 0.8,
  layerHeightMm: 0.2,
  octaves: 4,
  persistence: 0.5,
};

/** Labels drawn under each quadrant. Order matches the viewport table below. */
const QUAD_LABELS = ["Front", "Top", "Left", "Angled"];

export default function Viewer({
  url,
  colours,
  fuzzy = false,
  hiddenRoles,
  mode,
  status = "idle",
  onReady,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const canvasHost = useRef<HTMLDivElement>(null);
  const api = useRef<ReturnType<typeof createStage> | null>(null);
  // "Loading" is derived, not stored. Which URL we have finished with is the
  // fact; whether a spinner shows follows from comparing it to the URL we were
  // asked for. Setting a `loading` flag at the top of the effect instead would
  // be a synchronous setState inside an effect body — a cascading render, and
  // React's own lint rule says so.
  const [settledUrl, setSettledUrl] = useState<string | null>(null);
  const loading = !!url && url !== settledUrl;

  // Which roles the loaded model actually contains. Kept so a mismatch between
  // the generator's roles and the spec's filament roles is visible rather than
  // silently rendering everything the same colour.
  const [roles, setRoles] = useState<Set<string>>(new Set());

  // Stage lives for the life of the component; the model comes and goes.
  useEffect(() => {
    if (!canvasHost.current) return;
    const stage = createStage(canvasHost.current, (roles) => setRoles(roles));
    api.current = stage;
    return () => {
      stage.dispose();
      api.current = null;
    };
  }, []);

  // `onReady` is something this effect *does*, not something it depends on: a
  // parent that re-creates the callback each render would otherwise reload the
  // whole model every render. React 19.2's useEffectEvent says exactly that,
  // and replaces the exhaustive-deps suppression this used to carry.
  const announceReady = useEffectEvent(() => onReady?.());

  useEffect(() => {
    if (!api.current) return;
    if (!url) {
      api.current.clear();
      return;
    }
    let cancelled = false;
    api.current
      .load(url)
      .then(() => {
        if (cancelled) return;
        setSettledUrl(url);
        announceReady();
      })
      // A failed load still counts as settled: the spinner should stop, and the
      // parent already shows the failure from the job status.
      .catch(() => !cancelled && setSettledUrl(url));
    return () => {
      cancelled = true;
    };
  }, [url]);

  useEffect(() => {
    api.current?.setColours({ ...colours, bowl: BOWL_COLOUR }, fuzzy);
    // `roles` is a dependency so a freshly loaded model is painted immediately
    // rather than on the next unrelated state change.
  }, [colours, fuzzy, roles]);

  // Joined rather than passed as an array: a parent that rebuilds `["letters"]`
  // each render would otherwise re-run this effect every render. Same reason
  // `roles` is a dependency above — a newly loaded model must be re-hidden.
  const hiddenKey = (hiddenRoles ?? []).join(",");
  useEffect(() => {
    api.current?.setHidden(hiddenKey ? hiddenKey.split(",") : []);
  }, [hiddenKey, roles]);

  useEffect(() => {
    api.current?.setMode(mode);
  }, [mode]);

  const empty = !url && status !== "building";

  return (
    <div className="viewer" ref={host}>
      <div className="viewer-canvas" ref={canvasHost} />

      {mode === "quad" && url && !loading && (
        <div className="quad-labels" aria-hidden>
          {QUAD_LABELS.map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
      )}

      {(loading || status === "building") && (
        <div className="viewer-overlay">
          <div className="spinner" />
          <p>{status === "building" ? "Building your model…" : "Loading…"}</p>
          {status === "building" && <p className="dim">A few seconds — real geometry, not a mock-up.</p>}
        </div>
      )}

      {empty && (
        <div className="viewer-overlay viewer-empty">
          <div className="ghost" aria-hidden />
          <p>No preview yet</p>
          <p className="dim">Press Preview to build one from the real model.</p>
        </div>
      )}

      {status === "failed" && (
        <div className="viewer-overlay">
          <p>That preview didn&apos;t build.</p>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
   The three.js side. Deliberately plain functions over a class — nothing here
   needs inheritance, and a closure keeps the disposal list honest.
   ------------------------------------------------------------------------- */

/**
 * Which filament role a mesh belongs to.
 *
 * Two traps, both of which produced a model rendered entirely in one colour:
 *
 * - **The separator must survive three.js.** GLTFLoader passes every node name
 *   through `PropertyBinding.sanitizeNodeName`, which strips the characters its
 *   animation-binding syntax reserves — `. : / [ ]` and whitespace. A `::`
 *   separator arrived here as `standpaw_panel`. Hence `__` (see
 *   shared/ogma/preview.py, which must agree).
 * - **The name may be on a parent.** A glTF node becomes a Mesh or a Group with
 *   the mesh beneath it, at the loader's discretion; in the second case the Mesh
 *   is unnamed. So walk up until a name with the separator turns up.
 */
const ROLE_SEP = "__";

function roleOf(o: THREE.Object3D): string {
  for (let n: THREE.Object3D | null = o; n; n = n.parent) {
    const i = n.name?.indexOf(ROLE_SEP) ?? -1;
    if (i > 0) return n.name.slice(0, i);
  }
  return "stand";
}

function createStage(mount: HTMLElement, onRoles?: (roles: Set<string>) => void) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    // Ask for the discrete GPU where there is one; this scene is small but the
    // shading is not cheap, and integrated parts show banding on the drum.
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  // PCFSoftShadowMap is deprecated as of three 0.185 and silently falls back
  // to this anyway; asking for it directly stops the console warning.
  renderer.shadowMap.type = THREE.PCFShadowMap;
  // Khronos PBR Neutral, which exists for exactly this job: product viewers
  // where the rendered colour has to match the real material. It compresses
  // highlights without the hue shift and desaturation that both ACES Filmic
  // and AgX apply — AgX in particular washed Caramel out to a pale grey at
  // this exposure, which is the opposite of what a filament picker is for.
  renderer.toneMapping = THREE.NeutralToneMapping;
  // Below 1.0 deliberately. The three lights below sum to more than a single
  // key, and an over-exposed matte surface loses precisely the shading
  // gradient that the wall pattern is made of.
  renderer.toneMappingExposure = 0.9;
  mount.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const root = new THREE.Group();
  scene.add(root);

  // A metal surface shows you its surroundings; with no environment the
  // stainless bowl rendered as a black mirror with two specular blobs on it.
  // RoomEnvironment is a procedural softbox — no asset to download — and it
  // also lifts the matte PLA out of flat shading.
  const pmrem = new THREE.PMREMGenerator(renderer);
  // Blur 0.02 rather than 0.04: a sharper environment gives the stainless bowl
  // something with structure to reflect, which is what makes it read as metal.
  const envRT = pmrem.fromScene(new RoomEnvironment(), 0.02);
  scene.environment = envRT.texture;
  // Rotate the softbox so its bright panel sits off-axis from the key light.
  // Coincident reflections and highlights flatten a form; separating them is
  // most of what a product photographer is doing with a second light.
  scene.environmentRotation = new THREE.Euler(0, Math.PI * 0.35, 0);

  // Warm key from the front-left, cool fill behind — the same lighting the
  // offline renders use, so what you see here matches the style thumbnails.
  // A three-point setup, which is what a product shot actually is: a key to
  // model the form, a fill to keep the shadow side readable, and a rim to
  // separate the object from the background.
  // Intensities pulled back from an earlier pass that summed to a blown-out
  // image: the honeycomb rendered as near-white and the grooves vanished.
  // A pattern is read from the difference between a lit face and a shaded one,
  // so headroom above the key matters more than brightness.
  const key = new THREE.DirectionalLight(0xfff4e6, 1.45);
  key.position.set(180, -260, 240);
  key.castShadow = true;
  // 2048 with a tightened frustum: the shadow was the softest, blockiest thing
  // in the frame, and a contact shadow is a large part of why a render looks
  // like an object on a surface rather than a sprite floating over one.
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.near = 10;
  key.shadow.camera.far = 900;
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.6;
  key.shadow.radius = 3;
  const c = key.shadow.camera as THREE.OrthographicCamera;
  c.left = -180; c.right = 180; c.top = 180; c.bottom = -180;
  scene.add(key);

  // Fill is deliberately weak. Its job is to keep the shadow side readable,
  // not to flatten it — lift it and the relief goes with it.
  const fill = new THREE.DirectionalLight(0xdce6ff, 0.32);
  fill.position.set(-220, 160, 120);
  scene.add(fill);

  // Rim from behind and above, opposite the key: a bright edge on the far side
  // so the silhouette separates from the dark background. Grazing incidence,
  // so it costs the front face almost nothing.
  const rim = new THREE.DirectionalLight(0xffffff, 0.6);
  rim.position.set(-140, 240, 300);
  scene.add(rim);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2119, 0.18));

  // Shadow catcher. On layer 1, which only the perspective camera looks at: from
  // the top camera this plane is a black slab lying across the model, and in an
  // orthographic elevation a contact shadow means nothing anyway.
  const PERSPECTIVE_ONLY = 1;
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(1400, 1400),
    new THREE.ShadowMaterial({ opacity: 0.42 }),
  );
  ground.receiveShadow = true;
  ground.layers.set(PERSPECTIVE_ONLY);
  scene.add(ground);

  const materials: Record<string, THREE.MeshPhysicalMaterial> = {};
  const disposables: { dispose(): void }[] = [];

  // --- cameras -------------------------------------------------------------
  // One perspective camera for solid mode and the angled quadrant; three
  // orthographic cameras for the flat views. Orthographic is the honest choice
  // for front/top/left: it is what a technical drawing is, and it makes the
  // three views comparable to each other.
  const persp = new THREE.PerspectiveCamera(38, 1, 1, 3000);
  persp.layers.enable(PERSPECTIVE_ONLY);
  const ortho = {
    front: new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 2000),
    top: new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 2000),
    left: new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 2000),
  };

  const orbit = { theta: -Math.PI / 3.2, phi: 1.12, radius: 460 };
  let target = new THREE.Vector3();
  let radiusBase = 460;
  // Largest dimension of the loaded model, in model units (mm here).
  let modelExtent = 200;
  let mode: ViewMode = "solid";
  let raf = 0;
  let spin = true; // gentle idle rotation until the user touches it

  // Render on demand.
  //
  // The loop used to draw every frame forever, which in four-view mode means
  // re-rasterising ~90k triangles four times a frame for a picture that is not
  // changing. On a machine without a real GPU that saturates the main thread —
  // it was enough to visibly delay React from painting a validation error next
  // to the form. Nothing here animates unless someone moves it, so draw only
  // when something actually changed.
  let dirty = true;
  const invalidate = () => { dirty = true; };

  function applyPerspective() {
    const { theta, phi, radius } = orbit;
    persp.position.set(
      target.x + radius * Math.sin(phi) * Math.cos(theta),
      target.y + radius * Math.sin(phi) * Math.sin(theta),
      target.z + radius * Math.cos(phi),
    );
    persp.up.set(0, 0, 1);
    persp.lookAt(target);
  }

  /**
   * Fit an elevation to the model with a little air around it.
   *
   * Sized from the model's own bounding box rather than the orbit radius: the
   * radius is tuned for a perspective camera standing back from the subject, and
   * using it here left the stand as a small object adrift in a large frame.
   */
  function frameOrtho(cam: THREE.OrthographicCamera, w: number, h: number, pad = 1.12) {
    const aspect = w / Math.max(h, 1);
    const r = (modelExtent * 0.5) * pad;
    const [halfW, halfH] = aspect >= 1 ? [r * aspect, r] : [r, r / aspect];
    cam.left = -halfW; cam.right = halfW; cam.top = halfH; cam.bottom = -halfH;
    cam.updateProjectionMatrix();
  }

  function placeOrthoCameras() {
    const d = modelExtent * 4;
    ortho.front.position.set(target.x, target.y - d, target.z);
    ortho.front.up.set(0, 0, 1);
    ortho.front.lookAt(target);

    ortho.top.position.set(target.x, target.y, target.z + d);
    ortho.top.up.set(0, 1, 0);
    ortho.top.lookAt(target);

    ortho.left.position.set(target.x - d, target.y, target.z);
    ortho.left.up.set(0, 0, 1);
    ortho.left.lookAt(target);
  }

  // --- interaction ---------------------------------------------------------
  let dragging = false;
  let last = { x: 0, y: 0 };

  function onDown(e: PointerEvent) {
    dragging = true;
    spin = false;
    last = { x: e.clientX, y: e.clientY };
    renderer.domElement.setPointerCapture(e.pointerId);
  }
  function onMove(e: PointerEvent) {
    if (!dragging) return;
    orbit.theta -= (e.clientX - last.x) * 0.008;
    orbit.phi = clamp(orbit.phi - (e.clientY - last.y) * 0.008, 0.18, Math.PI - 0.18);
    last = { x: e.clientX, y: e.clientY };
    invalidate();
  }
  function onUp(e: PointerEvent) {
    dragging = false;
    try { renderer.domElement.releasePointerCapture(e.pointerId); } catch { /* already gone */ }
  }
  function onWheel(e: WheelEvent) {
    e.preventDefault();
    spin = false;
    orbit.radius = clamp(orbit.radius * (1 + Math.sign(e.deltaY) * 0.08), radiusBase * 0.45, radiusBase * 2.6);
    invalidate();
  }
  renderer.domElement.addEventListener("pointerdown", onDown);
  renderer.domElement.addEventListener("pointermove", onMove);
  renderer.domElement.addEventListener("pointerup", onUp);
  renderer.domElement.addEventListener("pointercancel", onUp);
  renderer.domElement.addEventListener("wheel", onWheel, { passive: false });

  // --- resize --------------------------------------------------------------
  let W = 1, H = 1;
  const ro = new ResizeObserver(() => {
    W = Math.max(1, mount.clientWidth);
    H = Math.max(1, mount.clientHeight);
    renderer.setSize(W, H, false);
    persp.aspect = W / H;
    persp.updateProjectionMatrix();
    invalidate();
  });
  ro.observe(mount);

  // --- render loop ---------------------------------------------------------
  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function tick() {
    raf = requestAnimationFrame(tick);
    // No idle rotation in four-view mode: three of the four are orthographic
    // elevations, so spinning redraws all four viewports to animate a quarter
    // of the picture — and a technical drawing that drifts is harder to read,
    // not nicer.
    if (spin && mode === "solid" && !reduceMotion) {
      orbit.theta += 0.0022;
      dirty = true;
    }
    if (!dirty) return;
    dirty = false;
    applyPerspective();

    renderer.setScissorTest(mode === "quad");
    if (mode === "solid") {
      renderer.setViewport(0, 0, W, H);
      renderer.render(scene, persp);
      return;
    }

    placeOrthoCameras();
    const hw = Math.floor(W / 2);
    const hh = Math.floor(H / 2);
    // Reading order — top-left first. WebGL's origin is bottom-left, hence the
    // inverted y.
    const cells: [THREE.Camera, number, number][] = [
      [ortho.front, 0, hh],
      [ortho.top, hw, hh],
      [ortho.left, 0, 0],
      [persp, hw, 0],
    ];
    for (const [cam, x, y] of cells) {
      if (cam !== persp) frameOrtho(cam as THREE.OrthographicCamera, hw, hh);
      renderer.setViewport(x, y, hw, hh);
      renderer.setScissor(x, y, hw, hh);
      renderer.render(scene, cam);
    }
  }
  tick();

  // --- model ---------------------------------------------------------------
  function clear() {
    for (const child of [...root.children]) root.remove(child);
    for (const d of disposables.splice(0)) d.dispose();
    invalidate();
  }

  /**
   * Roles the customer has switched off. Held on the stage rather than passed
   * into `load`, because it has to survive a model swap: change the lettering
   * font with letters hidden and the new GLB must arrive hidden too.
   */
  let hidden = new Set<string>();

  function applyVisibility() {
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) m.visible = !hidden.has(roleOf(m));
    });
    invalidate();
  }

  function setHidden(roles: string[]) {
    hidden = new Set(roles);
    applyVisibility();
  }

  /**
   * MeshPhysicalMaterial, not MeshStandardMaterial.
   *
   * Matte PLA is not a plain rough dielectric. It has a faint waxy sheen at
   * grazing angles that plain roughness cannot express, and the stainless bowl
   * needs anisotropy to read as spun metal rather than a chrome ball.
   * `physical` adds both for a small shader cost, on a scene that renders only
   * when something moves.
   */
  /**
   * Teach a material to shade fuzzy skin, driven by a uniform.
   *
   * Per-fragment normal perturbation rather than real displacement: the fuzz is
   * 0.3 mm on a 170 mm object, so displacing geometry would need a mesh far
   * denser than the printed one to resolve it — and the printed mesh is
   * smooth, because the fuzz is added by the slicer, not the model. Perturbing
   * the normal is both cheaper and more honest about where the texture comes
   * from.
   */
  function addFuzz(m: THREE.MeshPhysicalMaterial) {
    m.userData.fuzz = { value: 0 };
    m.onBeforeCompile = (shader) => {
      shader.uniforms.uFuzz = m.userData.fuzz;
      shader.uniforms.uFuzzPoint = { value: FUZZ.pointDistanceMm };
      shader.uniforms.uFuzzLayer = { value: FUZZ.layerHeightMm };

      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          `#include <common>
           varying vec3 vObjectPos;`,
        )
        .replace(
          "#include <begin_vertex>",
          `#include <begin_vertex>
           vObjectPos = position;`,
        );

      shader.fragmentShader = shader.fragmentShader
        .replace(
          "#include <common>",
          `#include <common>
           varying vec3 vObjectPos;
           uniform float uFuzz;
           uniform float uFuzzPoint;
           uniform float uFuzzLayer;

           float hash13(vec3 p) {
             p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
             p *= 17.0;
             return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
           }
           // Value noise: cheap, and the slicer's "classic" noise is not
           // gradient noise either.
           float vnoise(vec3 x) {
             vec3 i = floor(x), f = fract(x);
             f = f * f * (3.0 - 2.0 * f);
             return mix(
               mix(mix(hash13(i + vec3(0,0,0)), hash13(i + vec3(1,0,0)), f.x),
                   mix(hash13(i + vec3(0,1,0)), hash13(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(hash13(i + vec3(0,0,1)), hash13(i + vec3(1,0,1)), f.x),
                   mix(hash13(i + vec3(0,1,1)), hash13(i + vec3(1,1,1)), f.x), f.y),
               f.z);
           }
           // ${FUZZ.octaves} octaves at persistence ${FUZZ.persistence},
           // matching fuzzy_skin_octaves / fuzzy_skin_persistence.
           float fbm(vec3 p) {
             float a = 0.5, s = 0.0, n = 0.0;
             for (int i = 0; i < ${FUZZ.octaves}; i++) {
               s += a * vnoise(p); n += a; p *= 2.0; a *= ${FUZZ.persistence};
             }
             return s / n;
           }
           float fuzzField(vec3 mm) {
             // Anisotropic on purpose — see FUZZ. Z is sampled at the layer
             // pitch, X/Y at the point distance around the wall.
             vec3 q = vec3(mm.xy / uFuzzPoint, mm.z / uFuzzLayer);
             return fbm(q);
           }`,
        )
        .replace(
          "#include <normal_fragment_begin>",
          `#include <normal_fragment_begin>
           if (uFuzz > 0.0) {
             // Finite-difference gradient of the field, in millimetres.
             float e = 0.35;
             vec3 p = vObjectPos;
             float f0 = fuzzField(p);
             vec3 g = vec3(
               fuzzField(p + vec3(e, 0.0, 0.0)) - f0,
               fuzzField(p + vec3(0.0, e, 0.0)) - f0,
               fuzzField(p + vec3(0.0, 0.0, e * 0.5)) - f0);
             // Project the gradient into the surface so the perturbation tilts
             // the normal rather than inflating it.
             vec3 t = g - normal * dot(g, normal);
             normal = normalize(normal - t * uFuzz);
           }`,
        );
    };
    // Any change to onBeforeCompile needs a distinct cache key or three reuses
    // the previously compiled program for this material type.
    m.customProgramCacheKey = () => "ogma-fuzz-v1";
    return m;
  }

  function materialFor(role: string) {
    if (!materials[role]) {
      materials[role] = addFuzz(new THREE.MeshPhysicalMaterial({
        color: new THREE.Color("#b0a79c"),
        roughness: 0.72,
        metalness: 0.0,
        // A hint of sheen is what separates matte filament from matte paint:
        // the surface is slightly translucent fibre, so grazing angles lift.
        // Tinted, not white — see setColours.
        sheen: 0.18,
        sheenRoughness: 0.85,
        sheenColor: new THREE.Color("#ffffff"),
        // PLA is a dielectric with a real, if weak, specular response.
        specularIntensity: 0.32,
        // See the note in setColours: the environment is neutral, so it dilutes
        // the filament's hue as it brightens it.
        envMapIntensity: 0.55,
        flatShading: false,
      }));
    }
    return materials[role];
  }

  const loader = new GLTFLoader();

  function load(url: string) {
    return new Promise<void>((resolve, reject) => {
      loader.load(
        url,
        (gltf) => {
          clear();
          const box = new THREE.Box3();
          const seenRoles = new Set<string>();
          gltf.scene.traverse((o) => {
            const m = o as THREE.Mesh;
            if (!m.isMesh) return;
            const role = roleOf(m);
            seenRoles.add(role);
            m.material = materialFor(role);
            m.castShadow = true;
            m.receiveShadow = true;
            // Crease-aware normals, not a blanket average. See CREASE_ANGLE.
            // toCreasedNormals returns a new, non-indexed geometry, so the
            // original has to be disposed rather than leaked.
            const src = m.geometry;
            m.geometry = toCreasedNormals(src, CREASE_ANGLE);
            src.dispose();
            disposables.push(m.geometry);
            box.expandByObject(m);
          });
          root.add(gltf.scene);
          // Before the first frame, so a model loaded with letters already off
          // never flashes them. The framing box above deliberately still counts
          // them: the letters sit in pockets on the stand, so including them
          // keeps the camera still when the toggle moves.
          applyVisibility();
          onRoles?.(seenRoles);

          const size = new THREE.Vector3();
          const centre = new THREE.Vector3();
          box.getSize(size);
          box.getCenter(centre);
          target = centre;
          modelExtent = Math.max(size.x, size.y, size.z);
          radiusBase = modelExtent * 2.1;
          orbit.radius = radiusBase;
          ground.position.z = box.min.z - 0.4;
          const cam = key.shadow.camera as THREE.OrthographicCamera;
          const s = Math.max(size.x, size.y) * 1.4;
          cam.left = -s; cam.right = s; cam.top = s; cam.bottom = -s;
          cam.updateProjectionMatrix();
          spin = true;
          invalidate();
          resolve();
        },
        undefined,
        reject,
      );
    });
  }

  function setColours(byRole: RoleColours, fuzzy: boolean) {
    for (const [role, hex] of Object.entries(byRole)) {
      const m = materialFor(role);
      m.color.set(hex);
      if (role === "bowl") {
        // Brushed stainless, not chrome: enough roughness to scatter the
        // environment instead of mirroring it, plus anisotropy so the
        // highlight smears the way a spun bowl's does.
        //
        // Roughness raised from 0.28. The bowl's floor is flat, so at a tight
        // specular lobe the whole of it meets the highlight condition at once
        // and reads as a blown white disc rather than as a surface. Spreading
        // the lobe is what gives it a gradient, and therefore a shape.
        m.metalness = 0.82;
        m.roughness = 0.46;
        m.sheen = 0.0;
        m.anisotropy = 0.55;
        m.anisotropyRotation = Math.PI / 2;
        m.envMapIntensity = 1.5;
        m.specularIntensity = 1.0;
      } else {
        m.metalness = 0.0;
        m.anisotropy = 0.0;
        m.specularIntensity = 0.32;
        // 0.55, down from 1.0. RoomEnvironment is a bright *neutral* softbox, so
        // at full strength it adds white to every surface and the filament's own
        // hue washes out with it. Measured on Dark Red: the palette hex is 0.67
        // saturation, Bambu's own photo of the material is 0.65, and this viewer
        // was rendering it at 0.52 — visibly pink rather than deep red. The bowl
        // keeps a high value below, because a metal has nothing *but* the
        // environment to reflect.
        m.envMapIntensity = 0.55;

        // Fuzzy skin is painted onto the *stand's* outer wall only; the letters
        // print separately and smooth.
        const isFuzzy = fuzzy && role === "stand";

        // The visible texture is the normal perturbation below. Roughness and
        // sheen still move a little — a fuzzed wall genuinely scatters more —
        // but they were previously doing the whole job on their own, which is
        // why the option looked like almost nothing was happening.
        m.roughness = isFuzzy ? 0.88 : 0.72;
        // Sheen is an *additive* lobe on top of the diffuse term, so a white
        // one literally adds white to the surface — and unlike more light,
        // which scales albedo and preserves hue, that desaturates. It was the
        // main reason Dark Red rendered pink here: 0.67 saturation as a hex,
        // 0.65 in Bambu's own photograph of the material, and 0.51 on screen.
        //
        // Two changes. Weaker, because 0.35 (0.55 with fuzzy on, which is how
        // most stands are configured) is far more than a matte plastic shows.
        // And tinted toward the filament rather than left white: a pigmented
        // dielectric scatters its own colour at grazing angles, so this keeps
        // the effect the sheen was added for without bleaching the hue.
        m.sheen = isFuzzy ? 0.30 : 0.18;
        m.sheenRoughness = isFuzzy ? 1.0 : 0.85;
        // 80% filament, 20% white — enough lift to still read as translucent
        // fibre, not enough to wash the colour out.
        m.sheenColor.copy(m.color).lerp(new THREE.Color(0xffffff), 0.2);
        if (m.userData.fuzz) m.userData.fuzz.value = isFuzzy ? FUZZ.thicknessMm : 0.0;
      }
      m.needsUpdate = true;
    }
    invalidate();
  }

  function setMode(next: ViewMode) {
    mode = next;
    invalidate();
  }

  function dispose() {
    cancelAnimationFrame(raf);
    envRT.texture.dispose();
    pmrem.dispose();
    ro.disconnect();
    renderer.domElement.removeEventListener("pointerdown", onDown);
    renderer.domElement.removeEventListener("pointermove", onMove);
    renderer.domElement.removeEventListener("pointerup", onUp);
    renderer.domElement.removeEventListener("pointercancel", onUp);
    renderer.domElement.removeEventListener("wheel", onWheel);
    clear();
    for (const m of Object.values(materials)) m.dispose();
    renderer.dispose();
    mount.removeChild(renderer.domElement);
  }

  return { load, clear, setColours, setHidden, setMode, dispose };
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}
