/**
 * Nav theo role cho các giao diện riêng (host/admin) — FR-9.
 * Không dùng chung nav sàn giao dịch của user.
 */
import {
  IconBook,
  IconBuilding,
  IconGrid,
  IconSocial,
  IconUser,
} from "@/components/common/Icon";
import type { NavGroup } from "@/components/layout/Sidebar";

export const HOST_NAV_GROUPS: NavGroup[] = [
  {
    section: "Cuộc thi của tôi",
    items: [
      {
        href: "/host/contests",
        label: "Danh sách",
        description: "Quản lý & kích hoạt",
        icon: IconGrid,
      },
      {
        href: "/host/contests/new",
        label: "Tạo cuộc thi",
        description: "Chọn khuôn + tự sinh",
        icon: IconBook,
      },
    ],
  },
  {
    section: "Xem trước",
    items: [
      {
        href: "/contests",
        label: "Cuộc thi công khai",
        description: "Trang đích của contest",
        icon: IconSocial,
      },
    ],
  },
];

export const ADMIN_NAV_GROUPS: NavGroup[] = [
  {
    section: "Quản trị hệ thống",
    items: [
      {
        href: "/admin/users",
        label: "Người dùng",
        description: "Role & khóa tài khoản",
        icon: IconUser,
      },
      {
        href: "/admin/contests",
        label: "Cuộc thi",
        description: "Toàn bộ hệ thống",
        icon: IconGrid,
      },
      {
        href: "/admin/content",
        label: "Nội dung",
        description: "News · bài đăng · công ty",
        icon: IconBuilding,
      },
    ],
  },
];
