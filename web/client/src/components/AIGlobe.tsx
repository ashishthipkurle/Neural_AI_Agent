import { useEffect, useRef } from "react";
import * as THREE from "three";

interface AIGlobeProps {
  audioAnalyzer?: AnalyserNode | null;
  aiState?: "idle" | "listening" | "thinking" | "speaking";
  isMuted?: boolean;
}

export default function AIGlobe({ audioAnalyzer, aiState = "idle", isMuted = false }: AIGlobeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const analyzerRef = useRef<AnalyserNode | null>(null);
  const stateRef = useRef(aiState); // Ref for loop access
  const isMutedRef = useRef(isMuted); // Ref for mute state in loop
  const materialRef = useRef<THREE.ShaderMaterial | null>(null);
  const globeRef = useRef<THREE.Points | null>(null);

  /* =======================
     KEEP REFS STABLE
  ======================= */
  useEffect(() => {
    analyzerRef.current = audioAnalyzer ?? null;
  }, [audioAnalyzer]);

  useEffect(() => {
    stateRef.current = aiState;
  }, [aiState]);

  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  /* =======================
     SCENE SETUP (ONCE)
  ======================= */
  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const aspect = width / height;

    const camera = new THREE.PerspectiveCamera(
      aspect < 1 ? 60 : 45,
      aspect,
      0.1,
      100
    );
    camera.position.z = 5.5;

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
    });

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.sortObjects = false;
    renderer.autoClear = true;

    containerRef.current.appendChild(renderer.domElement);

    /* =======================
       PARTICLE GLOBE
    ======================= */
    const RADIUS = 1.2;
    const COUNT = 12000;

    const positions = new Float32Array(COUNT * 3);
    const phases = new Float32Array(COUNT);

    for (let i = 0; i < COUNT; i++) {
      const u = Math.random();
      const v = Math.random();

      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);

      positions[i * 3] = RADIUS * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = RADIUS * Math.cos(phi);
      positions[i * 3 + 2] = RADIUS * Math.sin(phi) * Math.sin(theta);

      phases[i] = Math.random() * Math.PI * 2;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("phase", new THREE.BufferAttribute(phases, 1));

    /* =======================
       SHADER MATERIAL
    ======================= */
    const material = new THREE.ShaderMaterial({
      transparent: true,
      depthTest: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uSize: { value: 8 },
        uColor: { value: new THREE.Color("#00c8d4") },
        uAudio: { value: 0 },
        uBass: { value: 0 },
        uMid: { value: 0 },
        uHigh: { value: 0 },
      },
      vertexShader: `
        attribute float phase;
        uniform float uTime;
        uniform float uSize;
        uniform float uAudio;
        uniform float uBass;
        uniform float uMid;
        varying float vPulse;

        void main() {
          float pulse = sin(uTime * 1.5 + phase) * 0.5 + 0.5;
          vPulse = pulse;

          float audioOffset = uBass * 0.3 + uMid * 0.2;
          vec3 displaced = position * (1.0 + audioOffset * sin(phase + uTime));

          vec4 mv = modelViewMatrix * vec4(displaced, 1.0);
          gl_PointSize =
            uSize *
            (1.0 + pulse * 0.6) *
            (1.0 + uAudio) *
            (1.0 / -mv.z);

          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uAudio;
        varying float vPulse;

        void main() {
          float d = length(gl_PointCoord - vec2(0.5));
          float alpha = smoothstep(0.5, 0.05, d);

          vec3 bright = vec3(0.5, 1.0, 1.0);
          vec3 color = mix(uColor, bright, uAudio);
          color *= 0.5 + vPulse * 0.5;

          gl_FragColor = vec4(color, alpha);
        }
      `,
    });

    materialRef.current = material;

    const globe = new THREE.Points(geometry, material);
    globeRef.current = globe;
    scene.add(globe);

    /* =======================
       GLOWS
    ======================= */
    const glow = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS * 1.03, 64, 64),
      new THREE.MeshBasicMaterial({
        color: "#00c8d4",
        transparent: true,
        opacity: 0.04,
      })
    );
    scene.add(glow);

    const innerGlow = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS * 0.95, 32, 32),
      new THREE.MeshBasicMaterial({
        color: "#00b4c8",
        transparent: true,
        opacity: 0.02,
      })
    );
    scene.add(innerGlow);

    /* =======================
       RESIZE
    ======================= */
    const onResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    /* =======================
       ANIMATION LOOP
    ======================= */
    const clock = new THREE.Clock();
    let raf = 0;

    let freqData: Uint8Array | null = null;
    let a = 0, b = 0, m = 0, h = 0;

    // State interpolation
    const currentStateColor = new THREE.Color("#00c8d4");
    const targetStateColor = new THREE.Color("#00c8d4");

    const clamp = (v: number) => Math.min(Math.max(v, 0), 1);

    const animate = () => {
      const t = clock.getElapsedTime();
      const analyzer = analyzerRef.current;
      const state = stateRef.current;
      const muted = isMutedRef.current;

      // Only process audio if not muted
      if (analyzer && !muted) {
        // ===== AUDIO ACTIVE =====
        const bins = analyzer.frequencyBinCount;
        if (!freqData || freqData.length !== bins) {
          freqData = new Uint8Array(bins);
        }

        analyzer.getByteFrequencyData(freqData);

        let bass = 0, mid = 0, high = 0;
        const bEnd = Math.floor(bins * 0.08);
        const mEnd = Math.floor(bins * 0.4);

        for (let i = 0; i < bEnd; i++) bass += freqData[i];
        for (let i = bEnd; i < mEnd; i++) mid += freqData[i];
        for (let i = mEnd; i < bins; i++) high += freqData[i];

        bass /= bEnd * 255;
        mid /= (mEnd - bEnd) * 255;
        high /= (bins - mEnd) * 255;

        const overall = bass * 0.5 + mid * 0.35 + high * 0.15;

        a += (overall - a) * 0.12;
        b += (bass - b) * 0.18;
        m += (mid - m) * 0.15;
        h += (high - h) * 0.12;
      } else {
        // ===== MIC OFF → Activity based on state =====

        // If thinking, simulate processing activity
        if (state === "thinking") {
          a += (0.4 - a) * 0.05;
          b += (0.3 - b) * 0.05;
        } else if (state === "listening") {
          // Listening: gentle pulse to show it's active
          const pulse = Math.sin(t * 3) * 0.15 + 0.2;
          a += (pulse - a) * 0.1;
          b += (pulse * 0.8 - b) * 0.1;
        } else {
          a += (0 - a) * 0.08;
          b += (0 - b) * 0.10;
        }

        m += (0 - m) * 0.10;
        h += (0 - h) * 0.10;
      }

      // STATE COLORS - Keep cyan/blue for all states except thinking
      if (state === "thinking") targetStateColor.set("#a855f7"); // Purple for processing
      else targetStateColor.set("#00c8d4"); // Cyan for idle, listening, speaking

      currentStateColor.lerp(targetStateColor, 0.05);
      material.uniforms.uColor.value.copy(currentStateColor);
      glow.material.color.copy(currentStateColor);
      innerGlow.material.color.copy(currentStateColor);

      material.uniforms.uAudio.value = clamp(a);
      material.uniforms.uBass.value = clamp(b);
      material.uniforms.uMid.value = clamp(m);
      material.uniforms.uHigh.value = clamp(h);

      glow.scale.setScalar(1 + b * 0.12);
      innerGlow.scale.setScalar(1 + a * 0.08);

      // ROTATION SPEED
      let rotationSpeed = 0.0007;
      if (state === "thinking") rotationSpeed = 0.003; // Moderate spin (was 0.02)

      globe.rotation.y += rotationSpeed + a * 0.002;
      globe.rotation.x += 0.00015 + m * 0.0005;

      material.uniforms.uTime.value = t;

      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };

    animate();

    /* =======================
       CLEANUP
    ======================= */
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      if (containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full"
      style={{ background: "transparent", overflow: "visible" }}
    />
  );
}
