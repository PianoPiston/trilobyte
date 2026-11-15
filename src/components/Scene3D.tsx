import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Takeoff } from "../lib/takeoff";

const WALL = 0xf3f2ee, WALL_T = 0.14;
const ROOM_COLORS = [0xc9d8c6, 0xdccfb4, 0xc3d3de, 0xdfcac0, 0xcfcbe0, 0xc4ddd4];

// 3D model of the floor: the drawing lies on the ground, rooms are tinted slabs and walls are extruded to wallHeight.
// Walls come from the wall mask of a raster plan, or from the room outlines of a CAD/BIM drawing.
export default function Scene3D({ takeoff, mPerPx, imageUrl, wallHeight, roomId, onRoom }: {
  takeoff: Takeoff; mPerPx: number; imageUrl: string; wallHeight: number; roomId: string | null; onRoom: (id: string | null) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const pick = useRef(onRoom);
  pick.current = onRoom;

  useEffect(() => {
    const el = host.current!;
    const m = mPerPx;
    const [W, H] = [takeoff.image_size[0] * m, takeoff.image_size[1] * m];
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeeeeef);
    scene.fog = new THREE.Fog(0xeeeeef, 80, 400);
    const camera = new THREE.PerspectiveCamera(40, el.clientWidth / el.clientHeight, 0.1, 2000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xd5d8d4, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.03;
    scene.add(sun, sun.target);

    // content bounds, so the camera frames the building and not the empty sheet margin
    const pts = takeoff.rooms.flatMap((r) => r.polygon).concat(takeoff.walls.flatMap((w) => [[w[0], w[1]], [w[2], w[3]]]));
    const xs = pts.map((q) => q[0] * m), zs = pts.map((q) => q[1] * m);
    const box = pts.length ? [Math.min(...xs), Math.min(...zs), Math.max(...xs), Math.max(...zs)] : [0, 0, W, H];
    const cx = (box[0] + box[2]) / 2, cz = (box[1] + box[3]) / 2, span = Math.max(box[2] - box[0], box[3] - box[1], 4);

    const sheet = new THREE.Mesh(new THREE.PlaneGeometry(W, H),
      new THREE.MeshStandardMaterial({ map: new THREE.TextureLoader().load(imageUrl, (t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; }), roughness: 1 }));
    sheet.rotation.x = -Math.PI / 2;
    sheet.position.set(W / 2, 0, H / 2);
    sheet.receiveShadow = true;
    scene.add(sheet);

    const floors: THREE.Mesh[] = [];
    takeoff.rooms.forEach((r, i) => {
      const shape = new THREE.Shape(r.polygon.map((q) => new THREE.Vector2(q[0] * m, q[1] * m)));
      const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape),
        new THREE.MeshStandardMaterial({ color: ROOM_COLORS[i % ROOM_COLORS.length], transparent: true, opacity: 0.7, roughness: 1, side: THREE.DoubleSide }));
      mesh.rotation.x = Math.PI / 2; // shape (x, y) -> world (x, z)
      mesh.position.y = 0.02;
      mesh.userData.room = r.id;
      floors.push(mesh);
      scene.add(mesh);
    });

    const wallMat = new THREE.MeshStandardMaterial({ color: WALL, roughness: 0.85 });
    const boxes: { x: number; z: number; w: number; d: number; rot: number }[] = [];
    if (takeoff.walls.length) {
      for (const [x0, y0, x1, y1] of takeoff.walls) boxes.push({ x: ((x0 + x1) / 2) * m, z: ((y0 + y1) / 2) * m, w: (x1 - x0) * m, d: (y1 - y0) * m, rot: 0 });
    } else {
      for (const r of takeoff.rooms.filter((q) => !q.outdoor)) {
        r.polygon.forEach((a, i) => {
          const b = r.polygon[(i + 1) % r.polygon.length];
          const len = Math.hypot(b[0] - a[0], b[1] - a[1]) * m;
          if (len > 0.05) boxes.push({ x: ((a[0] + b[0]) / 2) * m, z: ((a[1] + b[1]) / 2) * m, w: len + WALL_T, d: WALL_T, rot: -Math.atan2(b[1] - a[1], b[0] - a[0]) });
        });
      }
    }
    const walls = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), wallMat, boxes.length);
    const o = new THREE.Object3D();
    boxes.forEach((b, i) => {
      o.position.set(b.x, wallHeight / 2, b.z);
      o.rotation.set(0, b.rot, 0);
      o.scale.set(b.w, wallHeight, b.d);
      o.updateMatrix();
      walls.setMatrixAt(i, o.matrix);
    });
    walls.castShadow = walls.receiveShadow = true;
    scene.add(walls);

    sun.position.set(cx - span * 0.35, span * 2, cz - span * 0.45);
    sun.target.position.set(cx, 0, cz);
    Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 0.1, far: span * 4 });
    camera.position.set(cx + span * 0.4, span * 1.25, cz + span * 0.8);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(cx, 0, cz);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.6;
    controls.addEventListener("start", () => { controls.autoRotate = false; });

    const ray = new THREE.Raycaster();
    let down = [0, 0];
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      pick.current(ray.intersectObjects(floors)[0]?.object.userData.room ?? null);
    };
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);

    const ro = new ResizeObserver(() => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    });
    ro.observe(el);
    renderer.setAnimationLoop(() => {
      for (const f of floors) {
        const mat = f.material as THREE.MeshStandardMaterial;
        const on = f.userData.room === el.dataset.room;
        mat.opacity = on ? 0.85 : 0.7;
        mat.color.setHex(on ? 0x2c412b : ROOM_COLORS[floors.indexOf(f) % ROOM_COLORS.length]);
      }
      controls.update();
      renderer.render(scene, camera);
    });
    return () => {
      renderer.setAnimationLoop(null);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [takeoff, mPerPx, imageUrl, wallHeight]);

  return <div className="scene3d" ref={host} data-room={roomId ?? ""} />;
}
