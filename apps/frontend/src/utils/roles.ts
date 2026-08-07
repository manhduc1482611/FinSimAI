/**
 * Roles & điều hướng theo role (FR-8, FR-9).
 *
 * 1 form đăng nhập chung; sau khi đăng nhập frontend tự redirect theo role:
 *   - `admin` → `/admin`   (giao diện quản trị riêng)
 *   - `host`  → `/host`    (giao diện host, có màn tạo cuộc thi)
 *   - `user`  → `/dashboard` (sàn giao dịch như hiện tại)
 */

export type AppRole = "user" | "host" | "admin";

export const ROLE_LABELS: Record<AppRole, string> = {
  user: "Nhà đầu tư",
  host: "Host",
  admin: "Admin",
};

export const ROLE_HOME: Record<AppRole, string> = {
  user: "/dashboard",
  host: "/host/contests",
  admin: "/admin/users",
};

/** Trang chủ theo role; role không nhận diện được → `/dashboard`. */
export function homePathForRole(role: string | undefined | null): string {
  if (role === "admin" || role === "host") {
    return ROLE_HOME[role];
  }
  return ROLE_HOME.user;
}
