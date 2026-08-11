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

export type ViewMode = "solid" | "quad";

export type RoleColours = Record<string, string>;

type Props = {
  url: string | null;
  colours: RoleColours;
  /** Matte filament reads as a rougher surface; the fuzzy skin option more so. */
  fuzzy?: boolean;
  mode: ViewMode;
  status?: "idle" | "building" | "ready" | "failed";
  onReady?: () => void;
};

const BOWL_COLOUR = "#c9ccd1";

/** Labels drawn under each quadrant. Order matches the viewport table below. */
const QUAD_LABELS = ["Front", "Top", "Left", "Angled"];

export default function Viewer({
  url,
  colours,
  fuzzy = false,
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
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  // PCFSoftShadowMap is deprecated as of three 0.185 and silently falls back
  // to this anyway; asking for it directly stops the console warning.
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  // Tuned so a swatch reads as its palette hex. ACES plus an environment map
  // lifts mid-tones, and a customer choosing Caramel should see caramel rather
  // than a paler cousin of it.
  renderer.toneMappingExposure = 0.82;
  mount.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const root = new THREE.Group();
  scene.add(root);

  // A metal surface shows you its surroundings; with no environment the
  // stainless bowl rendered as a black mirror with two specular blobs on it.
  // RoomEnvironment is a procedural softbox — no asset to download — and it
  // also lifts the matte PLA out of flat shading.
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
  scene.environment = envRT.texture;

  // Warm key from the front-left, cool fill behind — the same lighting the
  // offline renders use, so what you see here matches the style thumbnails.
  const key = new THREE.DirectionalLight(0xfff4e6, 1.5);
  key.position.set(180, -260, 240);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.near = 10;
  key.shadow.camera.far = 900;
  const c = key.shadow.camera as THREE.OrthographicCamera;
  c.left = -180; c.right = 180; c.top = 180; c.bottom = -180;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xdce6ff, 0.55);
  fill.position.set(-220, 160, 120);
  scene.add(fill);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2119, 0.22));

  // Shadow catcher. On layer 1, which only the perspective camera looks at: from
  // the top camera this plane is a black slab lying across the model, and in an
  // orthographic elevation a contact shadow means nothing anyway.
  const PERSPECTIVE_ONLY = 1;
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(1400, 1400),
    new THREE.ShadowMaterial({ opacity: 0.34 }),
  );
  ground.receiveShadow = true;
  ground.layers.set(PERSPECTIVE_ONLY);
  scene.add(ground);

  const materials: Record<string, THREE.MeshStandardMaterial> = {};
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

  function materialFor(role: string) {
    if (!materials[role]) {
      materials[role] = new THREE.MeshStandardMaterial({
        color: new THREE.Color("#b0a79c"),
        roughness: 0.82,
        metalness: 0.0,
        flatShading: false,
      });
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
            m.geometry.computeVertexNormals();
            disposables.push(m.geometry);
            box.expandByObject(m);
          });
          root.add(gltf.scene);
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
        // environment instead of mirroring it.
        m.metalness = 0.86;
        m.roughness = 0.34;
      } else {
        m.metalness = 0.0;
        // Matte PLA is already rough; the fuzzy skin option is rougher still.
        // This is a cue, not a simulation — the real texture is per-facet.
        m.roughness = fuzzy && role === "stand" ? 0.98 : 0.82;
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

  return { load, clear, setColours, setMode, dispose };
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}
