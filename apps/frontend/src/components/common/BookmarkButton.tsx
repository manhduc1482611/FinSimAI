/**
 * BookmarkButton — nút lưu/bỏ lưu một nội dung (tin tức / bài xã hội).
 * Tự quản lý trạng thái local (optimistic) + gọi `/saves/toggle`;
 * redirect sang /login nếu chưa đăng nhập (không demo).
 * `onRemove` giúp parent xoá item khỏi danh sách ĐÀ LƯU khi bỏ lưu.
 */
"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";

import { IconBookmark } from "@/components/common/Icon";
import { toggleSave } from "@/services/saves";
import { useAuthStore } from "@/store/useAuthStore";
import { cn } from "@/utils/cn";

export interface BookmarkButtonProps {
  contentId: string;
  contentType: "news" | "social";
  saved: boolean;
  /** Gọi khiserver xác nhận kết quả toggle (dùng để đồng bộ state ở parent). */
  onToggle?: (saved: boolean) => void;
  /** Gọi khi bỏ lưu — dùng để xoá item khỏi danh sách ĐÃ LƯU. */
  onRemove?: (contentId: string) => void;
  className?: string;
}

export function BookmarkButton({
  contentId,
  contentType,
  saved: initialSaved,
  onToggle,
  onRemove,
  className,
}: BookmarkButtonProps) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const [saved, setSaved] = useState(initialSaved);
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    if (!user) {
      router.push("/login");
      return;
    }
    if (loading) {
      return;
    }
    const next = !saved;
    setSaved(next);
    setLoading(true);
    try {
      const result = await toggleSave({ content_type: contentType, content_id: contentId });
      setSaved(result.saved);
      onToggle?.(result.saved);
      if (!result.saved) {
        onRemove?.(contentId);
      }
    } catch {
      // Lỗi mạng / hết token → hoàn tác trạng thái tối ưu.
      setSaved(saved);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      aria-pressed={saved}
      aria-label={saved ? "Bỏ lưu" : "Lưu"}
      title={saved ? "Bỏ lưu" : "Lưu"}
      className={cn(
        "flex items-center justify-center rounded-md text-ink-400 transition-colors hover:bg-brand-500/10 hover:text-brand-700 dark:text-granite-400 dark:hover:text-brand-300",
        saved && "text-brand-600 dark:text-brand-400",
        className,
      )}
    >
      <IconBookmark className={cn("h-4 w-4", saved && "fill-current")} />
    </button>
  );
}