/**
 * Avatar — hiển thị ảnh đại diện (URL) nếu có, ngược lại hiện chữ cái đầu.
 * Tránh trường hợp render chuỗi URL thành chữ đè lên UI.
 */
"use client";

import { useState } from "react";

import { cn } from "@/utils/cn";

interface AvatarProps {
  src?: string | null;
  alt?: string;
  fallback: string;
  /** Vòng tròn chứa avatar: size + bo tròn + màu nền + canh giữa chữ cái đầu. */
  className?: string;
}

export function Avatar({ src, alt = "", fallback, className }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  const showImage = src !== null && src !== undefined && src !== "" && !failed;

  return (
    <div className={cn("shrink-0 overflow-hidden", className)}>
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src as string}
          alt={alt}
          onError={() => setFailed(true)}
          className="h-full w-full rounded-full object-cover"
        />
      ) : (
        fallback
      )}
    </div>
  );
}
