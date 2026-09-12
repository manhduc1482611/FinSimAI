/**
 * Capybara3D — trợ lý chuột lang (capybara) tư thế mascot.
 *
 * Capybara đứng thẳng bằng hai chân sau trên bục tròn nhỏ, thân dựng đứng,
 * hai chân trước ngắn buông phía trước bụng. Đầu được dựng theo đặc điểm thật:
 * sọ rộng/vuông, mõm cụt dạng hộp, mũi to màu sẫm, tai nhỏ, mắt buồn uể oải
 * (không giống gấu), gần như không có đuôi. Model sinh bằng code (three.js
 * primitives), bóng đổ thật cho chân chạm bục tự nhiên.
 */
"use client";

import { useEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

interface Capybara3DProps {
  className?: string;
  /** Khi Mentor đang stream câu trả lời → động tác nhanh, vui hơn. */
  excited?: boolean;
}

const FUR = "#9A6B3F";
const FUR_DARK = "#7C5126";
const FUR_LIGHT = "#CBA57E";
const DARK = "#2E1F12";
const BLUSH = "#E5A29A";

export function Capybara3D({ className, excited = false }: Capybara3DProps) {
  return (
    <Canvas
      className={className}
      dpr={[1, 2]}
      shadows="soft"
      camera={{ position: [0.6, 1.1, 4.6], fov: 27, near: 0.1, far: 100 }}
      gl={{ alpha: true, antialias: true }}
      onCreated={({ camera }) => {
        camera.lookAt(0, 1.02, 0);
      }}
    >
      <ambientLight intensity={0.75} />
      <directionalLight
        position={[3, 6, 4]}
        intensity={1.15}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-3}
        shadow-camera-right={3}
        shadow-camera-top={3}
        shadow-camera-bottom={-3}
        shadow-camera-near={1}
        shadow-camera-far={20}
      />
      <directionalLight position={[-4, 3, -3]} intensity={0.35} color="#FFF0D6" />
      <Float
        speed={excited ? 3 : 1.6}
        rotationIntensity={excited ? 0.35 : 0.22}
        floatIntensity={excited ? 0.5 : 0.35}
        floatingRange={[-0.03, 0.06]}
      >
        <CapybaraModel excited={excited} />
      </Float>
      <CameraRig />
    </Canvas>
  );
}

/** Giữ camera nhìn vào trung tâm model khi kích thước viewport đổi. */
function CameraRig() {
  const camera = useThree((state) => state.camera);
  useEffect(() => {
    camera.lookAt(0, 1.02, 0);
  }, [camera]);
  return null;
}

function CapybaraModel({ excited }: { excited: boolean }) {
  const swayRef = useRef<THREE.Group>(null);
  const bodyRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const armLRef = useRef<THREE.Mesh>(null);
  const armRRef = useRef<THREE.Mesh>(null);
  const eyeLRef = useRef<THREE.Mesh>(null);
  const eyeRRef = useRef<THREE.Mesh>(null);
  const eyeOpenRef = useRef(1);
  const eyeTargetRef = useRef(1);
  const nextBlinkRef = useRef(2.2);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const speed = excited ? 1.55 : 1;

    // Lắc lư nhẹ quanh trục Y — chú ý tới người dùng.
    if (swayRef.current) {
      swayRef.current.rotation.y = Math.sin(t * 0.4 * speed) * 0.26 + 0.3;
    }

    // Thở: thân phồng/xẹp tinh tế.
    if (bodyRef.current) {
      const breath = Math.sin(t * 1.7 * speed) * 0.02;
      bodyRef.current.scale.set(1 + breath, 1 - breath, 1 + breath);
    }

    // Đầu: hơi cúi xuống cho lộ mõm hộp, gật nhẹ.
    if (headRef.current) {
      headRef.current.rotation.x =
        -0.03 + Math.sin(t * 0.9 * speed) * 0.04 + (excited ? Math.sin(t * 4.2) * 0.02 : 0);
      headRef.current.rotation.z = Math.sin(t * 0.6 * speed) * 0.03;
      headRef.current.position.y = 1.26 + Math.sin(t * 1.2 * speed) * 0.02;
    }

    // Hai chân trước đung đưa nhẹ phía trước bụng.
    if (armLRef.current) {
      armLRef.current.rotation.z = 0.1 + Math.sin(t * 1.5 * speed) * 0.07;
    }
    if (armRRef.current) {
      armRRef.current.rotation.z = -0.1 - Math.sin(t * 1.5 * speed) * 0.07;
    }

    // Chớp mắt: mắt nhắm lại sau mí nặng (để mí màu lông cố định là trạng thái nhắm).
    if (t > nextBlinkRef.current) {
      eyeTargetRef.current = 0.08;
      if (t > nextBlinkRef.current + 0.12) {
        eyeTargetRef.current = 1;
        nextBlinkRef.current = t + (excited ? 1.4 : 2.4) + Math.random() * 3;
      }
    }
    eyeOpenRef.current +=
      (eyeTargetRef.current - eyeOpenRef.current) * Math.min(1, delta * 14);
    const s = eyeOpenRef.current;
    eyeLRef.current?.scale.set(1, s, 1);
    eyeRRef.current?.scale.set(1, s, 1);
  });

  return (
    <group ref={swayRef}>
      {/* Bóng đất: phóng to ra ngoài khung + gần như trong suốt → không còn vòng quanh con vật */}
      <mesh position={[0, -0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[2.6, 48]} />
        <meshBasicMaterial color="#20180D" transparent opacity={0.03} depthWrite={false} />
      </mesh>

      <group ref={bodyRef} position={[0, -0.42, 0]}>
        {/* Thân thùng — dựng đứng */}
        <mesh position={[0, 1.05, 0]} scale={[1, 1.28, 0.92]} castShadow>
          <sphereGeometry args={[0.5, 40, 40]} />
          <meshStandardMaterial color={FUR} roughness={0.85} />
        </mesh>

        {/* Bụng sáng màu phía trước (vàng nâu nhạt) */}
        <mesh position={[0, 0.72, 0.35]} scale={[0.55, 0.5, 0.38]} castShadow>
          <sphereGeometry args={[0.5, 32, 32]} />
          <meshStandardMaterial color={FUR_LIGHT} roughness={0.9} />
        </mesh>

        {/* Chân sau — ngắn, chắc, đứng trên bục */}
        <mesh position={[-0.4, 0.62, 0.02]} rotation={[0, 0, 0.08]} castShadow>
          <capsuleGeometry args={[0.1, 0.32, 6, 12]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </mesh>
        <mesh position={[0.4, 0.62, 0.02]} rotation={[0, 0, -0.08]} castShadow>
          <capsuleGeometry args={[0.1, 0.32, 6, 12]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </mesh>

        {/* Bàn chân sau (rộng, hơi dẹt như bàn chân capybara) */}
        <mesh position={[-0.4, 0.44, 0.18]} scale={[0.42, 0.15, 0.62]} castShadow>
          <sphereGeometry args={[0.5, 20, 20]} />
          <meshStandardMaterial color={FUR_LIGHT} roughness={0.9} />
        </mesh>
        <mesh position={[0.4, 0.44, 0.18]} scale={[0.42, 0.15, 0.62]} castShadow>
          <sphereGeometry args={[0.5, 20, 20]} />
          <meshStandardMaterial color={FUR_LIGHT} roughness={0.9} />
        </mesh>

        {/* Chân trước — ngắn, buông phía trước bụng */}
        <mesh ref={armLRef} position={[-0.33, 0.95, 0.42]} rotation={[0.18, 0, 0.1]} castShadow>
          <capsuleGeometry args={[0.07, 0.36, 6, 12]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </mesh>
        <mesh ref={armRRef} position={[0.33, 0.95, 0.42]} rotation={[0.18, 0, -0.1]} castShadow>
          <capsuleGeometry args={[0.07, 0.36, 6, 12]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </mesh>

        {/* Bàn tay trước */}
        <mesh position={[-0.34, 0.6, 0.52]} scale={[0.32, 0.22, 0.48]} castShadow>
          <sphereGeometry args={[0.5, 20, 20]} />
          <meshStandardMaterial color={FUR_LIGHT} roughness={0.9} />
        </mesh>
        <mesh position={[0.34, 0.6, 0.52]} scale={[0.32, 0.22, 0.48]} castShadow>
          <sphereGeometry args={[0.5, 20, 20]} />
          <meshStandardMaterial color={FUR_LIGHT} roughness={0.9} />
        </mesh>
      </group>

      {/* ĐẦU — sọ rộng + mõm hộp cụt "beaver-face" (đặc trưng capybara) */}
      <group ref={headRef} position={[0, 1.26, 0.42]}>
        {/* Sọ tròn rộng */}
        <mesh scale={[0.95, 0.9, 0.75]} castShadow>
          <sphereGeometry args={[0.42, 40, 40]} />
          <meshStandardMaterial color={FUR} roughness={0.85} />
        </mesh>

        {/* Mảng lông sẫm trên đỉnh đầu */}
        <mesh position={[0, 0.32, -0.16]} scale={[0.62, 0.2, 0.62]} castShadow>
          <sphereGeometry args={[0.4, 32, 32]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.9} />
        </mesh>

        {/* Tai NHỎ, nằm sát đỉnh-sau đầu (không to như tai gấu) */}
        <mesh position={[-0.37, 0.34, -0.06]} scale={[1, 1, 0.7]} castShadow>
          <sphereGeometry args={[0.11, 20, 20]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </mesh>
        <mesh position={[0.37, 0.34, -0.06]} scale={[1, 1, 0.7]} castShadow>
          <sphereGeometry args={[0.11, 20, 20]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </mesh>

        {/* Mõm CỤT hình hộp (như mặt hải ly) — mấu chốt để không giống gấu */}
        <RoundedBox
          position={[0, -0.05, 0.44]}
          args={[0.42, 0.34, 0.44]}
          radius={0.13}
          smoothness={4}
          castShadow
        >
          <meshStandardMaterial color={FUR_LIGHT} roughness={0.9} />
        </RoundedBox>

        {/* Sống mũi sẫm (kèm nốt "morrillo" đặc trưng) */}
        <RoundedBox
          position={[0, 0.15, 0.64]}
          args={[0.24, 0.14, 0.12]}
          radius={0.04}
          smoothness={3}
          castShadow
        >
          <meshStandardMaterial color={FUR_DARK} roughness={0.85} />
        </RoundedBox>

        {/* Mũi TO màu sẫm — thò ra đầu mõm */}
        <RoundedBox position={[0, 0.1, 0.76]} args={[0.22, 0.14, 0.22]} radius={0.06} smoothness={3}>
          <meshStandardMaterial color={DARK} roughness={0.4} />
        </RoundedBox>

        {/* Miệng nhỏ nằm trên mặt trước mõm */}
        <RoundedBox position={[0, -0.12, 0.66]} args={[0.14, 0.05, 0.06]} radius={0.02} smoothness={2}>
          <meshStandardMaterial color={DARK} roughness={0.6} />
        </RoundedBox>

        {/* Má hồng */}
        <mesh position={[-0.33, -0.08, 0.3]} scale={[0.16, 0.11, 0.05]}>
          <sphereGeometry args={[0.5, 20, 20]} />
          <meshStandardMaterial color={BLUSH} roughness={1} />
        </mesh>
        <mesh position={[0.33, -0.08, 0.3]} scale={[0.16, 0.11, 0.05]}>
          <sphereGeometry args={[0.5, 20, 20]} />
          <meshStandardMaterial color={BLUSH} roughness={1} />
        </mesh>

        {/* Mí mắt nặng (màu lông) — biểu cảm buồn uể oải, chặn nửa trên mắt */}
        <RoundedBox
          position={[-0.26, 0.205, 0.29]}
          args={[0.2, 0.05, 0.14]}
          radius={0.025}
          smoothness={2}
        >
          <meshStandardMaterial color={FUR} roughness={0.85} />
        </RoundedBox>
        <RoundedBox
          position={[0.26, 0.205, 0.29]}
          args={[0.2, 0.05, 0.14]}
          radius={0.025}
          smoothness={2}
        >
          <meshStandardMaterial color={FUR} roughness={0.85} />
        </RoundedBox>

        {/* Mắt nhỏ + highlight, nằm trên mõm */}
        <mesh ref={eyeLRef} position={[-0.26, 0.16, 0.28]}>
          <sphereGeometry args={[0.075, 20, 20]} />
          <meshStandardMaterial color={DARK} roughness={0.3} />
          <mesh position={[0.04, -0.01, 0.055]}>
            <sphereGeometry args={[0.028, 12, 12]} />
            <meshStandardMaterial color="#FFFFFF" roughness={0.2} />
          </mesh>
        </mesh>
        <mesh ref={eyeRRef} position={[0.26, 0.16, 0.28]}>
          <sphereGeometry args={[0.075, 20, 20]} />
          <meshStandardMaterial color={DARK} roughness={0.3} />
          <mesh position={[0.04, -0.01, 0.055]}>
            <sphereGeometry args={[0.028, 12, 12]} />
            <meshStandardMaterial color="#FFFFFF" roughness={0.2} />
          </mesh>
        </mesh>
      </group>
    </group>
  );
}