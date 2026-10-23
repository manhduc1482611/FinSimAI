/**
 * Capybara3D — Linh vật AI Mentor (Capia) hình chuột lang Capybara chibi siêu cute.
 *
 * Thiết kế mascot:
 * - Đứng thẳng bằng hai chân sau vững chãi, hai bàn chân ngắn tròn trĩnh cưng xỉu.
 * - Thân béo tròn dáng quả lê ấm áp với mảng bụng sữa kem phúng phính.
 * - Hai tay trước ngắn cũn cỡn ôm đồng tiền vàng Mentor FinSimAI sáng lấp lánh.
 * - Đầu sọ vuông tròn đặc trưng capybara, mõm kem bo góc mềm mại, mũi hạt nút đáng yêu,
 *   miệng cười chúm chím hiền hòa, đôi má ửng hồng ngọt ngào.
 * - Đôi mắt to tròn đen láy long lanh hai đốm sáng lung linh (kawaii eyes), không còn
 *   mí mắt sụp u uất.
 * - Đặc trưng capybara meme nổi tiếng thế giới: trên đầu đội một quả cam yuzu mọng nước
 *   với chiếc lá non xanh tươi lúc lắc!
 * - Hệ thống ánh sáng 3 điểm (Key + Fill + Rim Light vàng ấm) tạo hiệu ứng khối 3D cao cấp.
 * - Chuyển động hoạt hình sống động: thở phập phồng, lắc lư tò mò, tai giật giật,
 *   chớp mắt tự nhiên, và vẫy tay reo hò khi đang stream câu trả lời.
 */
"use client";

import { useEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

interface Capybara3DProps {
  className?: string;
  /** Khi Mentor đang stream câu trả lời → cử động vui tươi, reo hò nhanh hơn. */
  excited?: boolean;
}

// Bảng màu Capybara Kawaii
const FUR_MAIN = "#C88746";      // Nâu vàng caramel mật ong ấm áp
const FUR_DARK = "#8A5428";      // Nâu socola dịu cho tai, đuôi, bàn chân
const FUR_CREAM = "#FDF1DC";     // Màu kem sữa mềm mại cho mõm và bụng tròn
const NOSE_DARK = "#352014";     // Mũi nút đen nâu bóng nhẹ
const EYE_COLOR = "#1C140E";     // Mắt đen láy hạt cườm
const BLUSH_PINK = "#FFAAA6";    // Má hồng đào phúng phính
const INNER_EAR = "#F2A79D";     // Tai trong hồng phấn
const ORANGE_FRUIT = "#FF9500";  // Quả cam yuzu rực rỡ
const LEAF_GREEN = "#4CAF50";    // Chiếc lá non xanh tươi
const STEM_BROWN = "#5D4037";    // Cuống cam nhỏ
const COIN_GOLD = "#FFC107";     // Đồng xu vàng tài chính Mentor
const COIN_INNER = "#FFE082";

export function Capybara3D({ className, excited = false }: Capybara3DProps) {
  return (
    <Canvas
      className={className}
      dpr={[1, 2]}
      shadows="soft"
      camera={{ position: [0.3, 1.02, 4.05], fov: 27.5, near: 0.1, far: 50 }}
      gl={{ alpha: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
      onCreated={({ camera }) => {
        camera.lookAt(0, 0.92, 0);
      }}
    >
      {/* Ánh sáng môi trường mềm mại */}
      <ambientLight intensity={0.75} color="#FFF8F0" />

      {/* Đèn chính (Key Light) — ánh nắng ấm áp phía trước */}
      <directionalLight
        position={[3.5, 5.5, 4]}
        intensity={1.35}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-2}
        shadow-camera-right={2}
        shadow-camera-top={2}
        shadow-camera-bottom={-2}
        shadow-camera-near={1}
        shadow-camera-far={15}
        shadow-bias={-0.0005}
      />

      {/* Đèn phụ (Fill Light) — ánh sáng xanh ngọc dịu nhẹ xóa góc chết tối */}
      <directionalLight position={[-3.5, 2.5, 2]} intensity={0.5} color="#E0F2FE" />

      {/* Đèn viền (Rim Light / Backlight) — viền sáng vàng hào quang tạo khối sang trọng */}
      <directionalLight position={[0, 4, -3.5]} intensity={1.5} color="#FFE0B2" />

      {/* Đèn hắt từ dưới lên (Bounce light) — làm sáng nhẹ vùng cằm và bụng */}
      <directionalLight position={[0, -2, 1.5]} intensity={0.3} color="#FFE8D6" />

      <Float
        speed={excited ? 3.2 : 1.6}
        rotationIntensity={excited ? 0.28 : 0.15}
        floatIntensity={excited ? 0.45 : 0.25}
        floatingRange={[-0.02, 0.04]}
      >
        <CapybaraModel excited={excited} />
      </Float>

      <CameraRig />
    </Canvas>
  );
}

/** Giữ camera luôn hướng thẳng vào tâm của Capybara khi resize */
function CameraRig() {
  const camera = useThree((state) => state.camera);
  useEffect(() => {
    camera.lookAt(0, 0.92, 0);
  }, [camera]);
  return null;
}

function CapybaraModel({ excited }: { excited: boolean }) {
  const swayRef = useRef<THREE.Group>(null);
  const bodyRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const orangeRef = useRef<THREE.Group>(null);
  const earLRef = useRef<THREE.Group>(null);
  const earRRef = useRef<THREE.Group>(null);
  const armLRef = useRef<THREE.Group>(null);
  const armRRef = useRef<THREE.Group>(null);
  const coinRef = useRef<THREE.Group>(null);
  const eyeLRef = useRef<THREE.Mesh>(null);
  const eyeRRef = useRef<THREE.Mesh>(null);

  const eyeOpenRef = useRef(1);
  const eyeTargetRef = useRef(1);
  const nextBlinkRef = useRef(2.2);
  const nextEarTwitchRef = useRef(3.5);
  const earTwitchTimerRef = useRef(0);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const speed = excited ? 2.2 : 1;

    // 1. Lắc lư nhẹ nhàng toàn thân, hơi hướng về phía chuột người dùng
    if (swayRef.current) {
      const pointerX = state.pointer.x * 0.25;
      const autoSway = Math.sin(t * 0.6 * speed) * 0.12;
      swayRef.current.rotation.y = THREE.MathUtils.lerp(
        swayRef.current.rotation.y,
        autoSway + pointerX + 0.12,
        Math.min(1, delta * 4),
      );
    }

    // 2. Thở phập phồng (Breathing squash & stretch)
    if (bodyRef.current) {
      const breath = Math.sin(t * 2.0 * speed) * 0.025;
      bodyRef.current.scale.set(1 + breath * 0.5, 1 - breath, 1 + breath * 0.5);
    }

    // 3. Đầu cử động tò mò, gật nhẹ hiền từ
    if (headRef.current) {
      const pointerY = -state.pointer.y * 0.12;
      headRef.current.rotation.x =
        Math.sin(t * 1.1 * speed) * 0.03 - 0.01 + pointerY + (excited ? Math.sin(t * 5.5) * 0.03 : 0);
      headRef.current.rotation.z = Math.sin(t * 0.7 * speed) * 0.035;
      headRef.current.position.y = 1.15 + Math.sin(t * 1.5 * speed) * 0.015;
    }

    // 4. Quả cam trên đầu lúc lắc tự nhiên theo chuyển động quán tính
    if (orangeRef.current && headRef.current) {
      orangeRef.current.rotation.z = -headRef.current.rotation.z * 1.3;
      orangeRef.current.rotation.x = -headRef.current.rotation.x * 1.2;
    }

    // 5. Hai tay trước ngắn ngắn ôm đồng xu hoặc vẫy vui vẻ khi excited
    if (armLRef.current && armRRef.current) {
      if (excited) {
        // Vẫy tay chúc mừng vui vẻ khi AI đang trả lời
        armLRef.current.rotation.z = 0.35 + Math.sin(t * 8.5) * 0.25;
        armRRef.current.rotation.z = -0.35 - Math.sin(t * 8.5) * 0.25;
        armLRef.current.position.y = 0.72 + Math.sin(t * 8.5) * 0.03;
        armRRef.current.position.y = 0.72 + Math.sin(t * 8.5) * 0.03;
      } else {
        // Ôm nhẹ nhàng trước bụng
        armLRef.current.rotation.z = 0.28 + Math.sin(t * 1.5) * 0.04;
        armRRef.current.rotation.z = -0.28 - Math.sin(t * 1.5) * 0.04;
        armLRef.current.position.y = 0.72;
        armRRef.current.position.y = 0.72;
      }
    }

    // 6. Đồng xu vàng xoay lấp lánh nhẹ
    if (coinRef.current) {
      coinRef.current.rotation.y = Math.sin(t * 1.4) * 0.15;
    }

    // 7. Giật tai (Ear twitch) ngẫu nhiên như động vật thật
    if (t > nextEarTwitchRef.current) {
      earTwitchTimerRef.current = t + 0.35;
      nextEarTwitchRef.current = t + 3.0 + Math.random() * 4.0;
    }
    if (earLRef.current && earRRef.current) {
      if (t < earTwitchTimerRef.current) {
        const twitch = Math.sin((earTwitchTimerRef.current - t) * 35) * 0.15;
        earLRef.current.rotation.x = 0.1 + twitch;
        earRRef.current.rotation.x = 0.1 - twitch;
      } else {
        earLRef.current.rotation.x = 0.1;
        earRRef.current.rotation.x = 0.1;
      }
    }

    // 8. Chớp mắt tự nhiên
    if (t > nextBlinkRef.current) {
      eyeTargetRef.current = 0.08;
      if (t > nextBlinkRef.current + 0.11) {
        eyeTargetRef.current = 1;
        nextBlinkRef.current = t + (excited ? 1.5 : 2.8) + Math.random() * 2.5;
      }
    }
    eyeOpenRef.current += (eyeTargetRef.current - eyeOpenRef.current) * Math.min(1, delta * 18);
    const eyeScale = eyeOpenRef.current;
    eyeLRef.current?.scale.set(1, eyeScale, 1);
    eyeRRef.current?.scale.set(1, eyeScale, 1);
  });

  return (
    <group ref={swayRef}>
      {/* Bóng tiếp đất mềm mịn */}
      <mesh position={[0, 0.015, 0.04]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.55, 36]} />
        <meshBasicMaterial color="#3D2614" transparent opacity={0.16} depthWrite={false} />
      </mesh>
      <mesh position={[0, 0.02, 0.04]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.34, 32]} />
        <meshBasicMaterial color="#2B1A0E" transparent opacity={0.2} depthWrite={false} />
      </mesh>

      {/* HAI CHÂN SAU ĐỨNG THẲNG — bàn chân tròn trĩnh vững vàng */}
      <group position={[0, 0, 0]}>
        {/* Bàn chân trái */}
        <group position={[-0.2, 0.07, 0.04]} rotation={[0, -0.15, 0]}>
          <RoundedBox args={[0.19, 0.12, 0.28]} radius={0.05} smoothness={4} castShadow>
            <meshStandardMaterial color={FUR_DARK} roughness={0.75} />
          </RoundedBox>
          {/* Ngón chân tròn nhỏ xinh */}
          <mesh position={[-0.05, -0.02, 0.13]} castShadow>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
          <mesh position={[0, -0.02, 0.14]} castShadow>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
          <mesh position={[0.05, -0.02, 0.13]} castShadow>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
        </group>

        {/* Bàn chân phải */}
        <group position={[0.2, 0.07, 0.04]} rotation={[0, 0.15, 0]}>
          <RoundedBox args={[0.19, 0.12, 0.28]} radius={0.05} smoothness={4} castShadow>
            <meshStandardMaterial color={FUR_DARK} roughness={0.75} />
          </RoundedBox>
          {/* Ngón chân tròn nhỏ xinh */}
          <mesh position={[-0.05, -0.02, 0.13]} castShadow>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
          <mesh position={[0, -0.02, 0.14]} castShadow>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
          <mesh position={[0.05, -0.02, 0.13]} castShadow>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
        </group>

        {/* Chân sau ngắn mũm mĩm */}
        <mesh position={[-0.2, 0.25, 0]} castShadow>
          <capsuleGeometry args={[0.1, 0.16, 8, 16]} />
          <meshStandardMaterial color={FUR_MAIN} roughness={0.65} />
        </mesh>
        <mesh position={[0.2, 0.25, 0]} castShadow>
          <capsuleGeometry args={[0.1, 0.16, 8, 16]} />
          <meshStandardMaterial color={FUR_MAIN} roughness={0.65} />
        </mesh>
      </group>

      {/* THÂN BÉO TRÒN DÁNG QUẢ LÊ — êm ái, đáng yêu */}
      <group ref={bodyRef}>
        {/* Thân dưới (bụng bự) */}
        <mesh position={[0, 0.52, 0.01]} scale={[1.06, 0.98, 0.98]} castShadow>
          <sphereGeometry args={[0.46, 36, 36]} />
          <meshStandardMaterial color={FUR_MAIN} roughness={0.65} />
        </mesh>

        {/* Thân trên (ngực) */}
        <mesh position={[0, 0.77, -0.02]} scale={[0.96, 0.94, 0.92]} castShadow>
          <sphereGeometry args={[0.4, 36, 36]} />
          <meshStandardMaterial color={FUR_MAIN} roughness={0.65} />
        </mesh>

        {/* Bụng tròn màu kem sữa ngọt ngào */}
        <mesh position={[0, 0.53, 0.22]} scale={[0.82, 0.94, 0.4]} castShadow>
          <sphereGeometry args={[0.38, 32, 32]} />
          <meshStandardMaterial color={FUR_CREAM} roughness={0.7} />
        </mesh>

        {/* Chiếc đuôi cụt tròn nhỏ xinh phía sau */}
        <mesh position={[0, 0.38, -0.41]} castShadow>
          <sphereGeometry args={[0.07, 16, 16]} />
          <meshStandardMaterial color={FUR_DARK} roughness={0.8} />
        </mesh>

        {/* HAI TAY TRƯỚC NGẮN NGẮN ÔM ĐỒNG XU */}
        {/* Tay trái */}
        <group ref={armLRef} position={[-0.32, 0.72, 0.1]}>
          <mesh rotation={[0.35, 0.15, 0.35]} castShadow>
            <capsuleGeometry args={[0.075, 0.2, 6, 12]} />
            <meshStandardMaterial color={FUR_MAIN} roughness={0.65} />
          </mesh>
          {/* Bàn tay trái nhỏ */}
          <mesh position={[0.08, -0.16, 0.14]} castShadow>
            <sphereGeometry args={[0.08, 16, 16]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.75} />
          </mesh>
        </group>

        {/* Tay phải */}
        <group ref={armRRef} position={[0.32, 0.72, 0.1]}>
          <mesh rotation={[0.35, -0.15, -0.35]} castShadow>
            <capsuleGeometry args={[0.075, 0.2, 6, 12]} />
            <meshStandardMaterial color={FUR_MAIN} roughness={0.65} />
          </mesh>
          {/* Bàn tay phải nhỏ */}
          <mesh position={[-0.08, -0.16, 0.14]} castShadow>
            <sphereGeometry args={[0.08, 16, 16]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.75} />
          </mesh>
        </group>

        {/* ĐỒNG TIỀN VÀNG MENTOR FINSIMAI — lấp lánh trước bụng */}
        <group ref={coinRef} position={[0, 0.57, 0.35]} rotation={[0.12, 0, 0]}>
          {/* Viền ngoài đồng xu */}
          <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry args={[0.11, 0.11, 0.03, 32]} />
            <meshStandardMaterial color={COIN_GOLD} metalness={0.8} roughness={0.25} />
          </mesh>
          {/* Tâm đồng xu sáng bóng */}
          <mesh position={[0, 0, 0.012]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.085, 0.085, 0.012, 32]} />
            <meshStandardMaterial color={COIN_INNER} metalness={0.85} roughness={0.2} />
          </mesh>
          {/* Biểu tượng ngôi sao may mắn trên đồng xu */}
          <mesh position={[0, 0, 0.02]}>
            <sphereGeometry args={[0.024, 12, 12]} />
            <meshStandardMaterial color="#FFFFFF" roughness={0.2} metalness={0.5} />
          </mesh>
        </group>
      </group>

      {/* ĐẦU CAPYBARA CHIBI — siêu cấp đáng yêu */}
      <group ref={headRef} position={[0, 1.15, 0.04]}>
        {/* Sọ đầu vuông tròn bo góc đặc trưng của Capybara */}
        <RoundedBox args={[0.62, 0.52, 0.54]} radius={0.22} smoothness={6} castShadow>
          <meshStandardMaterial color={FUR_MAIN} roughness={0.6} />
        </RoundedBox>

        {/* Đôi má phúng phính hai bên */}
        <mesh position={[-0.25, -0.06, 0.08]} scale={[1, 0.9, 0.95]} castShadow>
          <sphereGeometry args={[0.2, 24, 24]} />
          <meshStandardMaterial color={FUR_MAIN} roughness={0.6} />
        </mesh>
        <mesh position={[0.25, -0.06, 0.08]} scale={[1, 0.9, 0.95]} castShadow>
          <sphereGeometry args={[0.2, 24, 24]} />
          <meshStandardMaterial color={FUR_MAIN} roughness={0.6} />
        </mesh>

        {/* ĐÔI MÁ HỒNG ĐÀO PHÚNG PHÍNH (Blush) */}
        <mesh position={[-0.28, -0.06, 0.26]} rotation={[0, -0.35, 0]} scale={[1, 0.65, 0.2]}>
          <sphereGeometry args={[0.075, 16, 16]} />
          <meshStandardMaterial color={BLUSH_PINK} roughness={0.9} />
        </mesh>
        <mesh position={[0.28, -0.06, 0.26]} rotation={[0, 0.35, 0]} scale={[1, 0.65, 0.2]}>
          <sphereGeometry args={[0.075, 16, 16]} />
          <meshStandardMaterial color={BLUSH_PINK} roughness={0.9} />
        </mesh>

        {/* MÕM KEM BO TRÒN (Snout) — mấu chốt để trông ngọt ngào hiền hòa */}
        <RoundedBox position={[0, -0.07, 0.3]} args={[0.4, 0.3, 0.26]} radius={0.12} smoothness={5} castShadow>
          <meshStandardMaterial color={FUR_CREAM} roughness={0.7} />
        </RoundedBox>
        {/* Cằm dưới mềm mại */}
        <mesh position={[0, -0.16, 0.26]} scale={[1.1, 0.6, 0.9]} castShadow>
          <sphereGeometry args={[0.16, 20, 20]} />
          <meshStandardMaterial color={FUR_CREAM} roughness={0.7} />
        </mesh>

        {/* MŨI HẠT NÚT ĐÁNG YÊU */}
        <RoundedBox position={[0, 0.05, 0.43]} args={[0.15, 0.09, 0.08]} radius={0.04} smoothness={4} castShadow>
          <meshStandardMaterial color={NOSE_DARK} roughness={0.35} />
        </RoundedBox>
        {/* Hai lỗ mũi nhỏ xinh */}
        <mesh position={[-0.035, 0.045, 0.47]}>
          <sphereGeometry args={[0.015, 8, 8]} />
          <meshBasicMaterial color="#1F120A" />
        </mesh>
        <mesh position={[0.035, 0.045, 0.47]}>
          <sphereGeometry args={[0.015, 8, 8]} />
          <meshBasicMaterial color="#1F120A" />
        </mesh>

        {/* MIỆNG CƯỜI CHÚM CHÍM ":3" */}
        {/* Đường nhân trung nhỏ */}
        <mesh position={[0, -0.015, 0.435]}>
          <capsuleGeometry args={[0.01, 0.035, 4, 8]} />
          <meshBasicMaterial color={NOSE_DARK} />
        </mesh>
        {/* Cung khóe miệng trái cười hiền */}
        <mesh position={[-0.032, -0.042, 0.43]} rotation={[0, 0, -Math.PI * 0.85]}>
          <torusGeometry args={[0.04, 0.01, 8, 16, Math.PI * 0.7]} />
          <meshBasicMaterial color={NOSE_DARK} />
        </mesh>
        {/* Cung khóe miệng phải cười hiền */}
        <mesh position={[0.032, -0.042, 0.43]} rotation={[0, 0, Math.PI * 0.15]}>
          <torusGeometry args={[0.04, 0.01, 8, 16, Math.PI * 0.7]} />
          <meshBasicMaterial color={NOSE_DARK} />
        </mesh>

        {/* ĐÔI MẮT KAWAII TO TRÒN ĐEN LÁY CÓ ĐỐM SÁNG LUNG LINH */}
        {/* Mắt trái */}
        <group position={[-0.21, 0.1, 0.26]}>
          <mesh ref={eyeLRef} scale={[1, 1, 0.8]}>
            <sphereGeometry args={[0.072, 24, 24]} />
            <meshStandardMaterial color={EYE_COLOR} roughness={0.1} metalness={0.08} />
            {/* Đốm sáng lớn (Catchlight 1) */}
            <mesh position={[-0.015, 0.022, 0.058]}>
              <sphereGeometry args={[0.025, 14, 14]} />
              <meshBasicMaterial color="#FFFFFF" />
            </mesh>
            {/* Đốm sáng nhỏ (Catchlight 2) */}
            <mesh position={[0.018, -0.018, 0.058]}>
              <sphereGeometry args={[0.012, 10, 10]} />
              <meshBasicMaterial color="#FFFFFF" />
            </mesh>
          </mesh>
          {/* Lông mày/nét mắt hiền từ trên mắt trái */}
          <mesh position={[0, 0.09, -0.02]} rotation={[0, 0, -0.15]}>
            <capsuleGeometry args={[0.01, 0.065, 4, 8]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
        </group>

        {/* Mắt phải */}
        <group position={[0.21, 0.1, 0.26]}>
          <mesh ref={eyeRRef} scale={[1, 1, 0.8]}>
            <sphereGeometry args={[0.072, 24, 24]} />
            <meshStandardMaterial color={EYE_COLOR} roughness={0.1} metalness={0.08} />
            {/* Đốm sáng lớn (Catchlight 1) */}
            <mesh position={[-0.015, 0.022, 0.058]}>
              <sphereGeometry args={[0.025, 14, 14]} />
              <meshBasicMaterial color="#FFFFFF" />
            </mesh>
            {/* Đốm sáng nhỏ (Catchlight 2) */}
            <mesh position={[0.018, -0.018, 0.058]}>
              <sphereGeometry args={[0.012, 10, 10]} />
              <meshBasicMaterial color="#FFFFFF" />
            </mesh>
          </mesh>
          {/* Lông mày/nét mắt hiền từ trên mắt phải */}
          <mesh position={[0, 0.09, -0.02]} rotation={[0, 0, 0.15]}>
            <capsuleGeometry args={[0.01, 0.065, 4, 8]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
        </group>

        {/* HAI TAI TRÒN VỂNH XINH XẮN — có tai trong màu hồng phấn */}
        {/* Tai trái */}
        <group ref={earLRef} position={[-0.32, 0.27, -0.02]} rotation={[0.1, -0.2, -0.35]}>
          <mesh scale={[1, 1.15, 0.5]} castShadow>
            <sphereGeometry args={[0.12, 20, 20]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
          {/* Lòng tai trong màu hồng phấn */}
          <mesh position={[0.01, 0, 0.028]} scale={[0.9, 1.05, 0.4]}>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshStandardMaterial color={INNER_EAR} roughness={0.8} />
          </mesh>
        </group>

        {/* Tai phải */}
        <group ref={earRRef} position={[0.32, 0.27, -0.02]} rotation={[0.1, 0.2, 0.35]}>
          <mesh scale={[1, 1.15, 0.5]} castShadow>
            <sphereGeometry args={[0.12, 20, 20]} />
            <meshStandardMaterial color={FUR_DARK} roughness={0.7} />
          </mesh>
          {/* Lòng tai trong màu hồng phấn */}
          <mesh position={[-0.01, 0, 0.028]} scale={[0.9, 1.05, 0.4]}>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshStandardMaterial color={INNER_EAR} roughness={0.8} />
          </mesh>
        </group>

        {/* ĐẶC TRƯNG MÙA ĐÔNG CAPYBARA: QUẢ CAM YUZU VỚI CHIẾC LÁ NON TRÊN ĐẦU */}
        <group ref={orangeRef} position={[0, 0.34, 0.02]}>
          {/* Trái cam mọng nước căng tròn */}
          <mesh scale={[1.1, 0.92, 1.1]} castShadow>
            <sphereGeometry args={[0.16, 32, 32]} />
            <meshStandardMaterial color={ORANGE_FRUIT} roughness={0.4} metalness={0.05} />
          </mesh>
          {/* Cuống cam nhỏ */}
          <mesh position={[0, 0.16, 0]} rotation={[0.12, 0, -0.15]} castShadow>
            <cylinderGeometry args={[0.015, 0.018, 0.075, 8]} />
            <meshStandardMaterial color={STEM_BROWN} roughness={0.8} />
          </mesh>
          {/* Chiếc lá non xanh biếc */}
          <mesh
            position={[0.065, 0.165, 0.02]}
            rotation={[0.2, 0.4, 0.3]}
            scale={[1.3, 0.18, 0.75]}
            castShadow
          >
            <sphereGeometry args={[0.085, 16, 16]} />
            <meshStandardMaterial color={LEAF_GREEN} roughness={0.35} />
          </mesh>
        </group>
      </group>
    </group>
  );
}
