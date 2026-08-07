/**
 * Admin · Người dùng — bảng user + đổi role + khoá/mở khoá (FR-2, FR-3).
 */
"use client";

import { useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconSearch, IconUser } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField, TextField } from "@/components/common/Field";
import { Spinner } from "@/components/common/Spinner";
import { useAsync } from "@/hooks/useAsync";
import { listUsers, updateUserRole, updateUserStatus } from "@/services/admin";
import { toRequestError } from "@/services/api";
import { useAuthStore } from "@/store/useAuthStore";
import { formatDateTime } from "@/utils/format";

export default function AdminUsersPage() {
  const currentUser = useAuthStore((state) => state.user);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data, loading, error, reload } = useAsync(
    () =>
      listUsers({
        role: roleFilter || undefined,
        search: search.trim() || undefined,
        limit: 100,
      }),
    [roleFilter, search],
  );

  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleRoleChange = async (userId: string, role: string) => {
    if (role !== "user" && role !== "host" && role !== "admin") {
      return;
    }
    setActionError(null);
    setBusyId(userId);
    try {
      await updateUserRole(userId, { role });
      reload();
    } catch (err) {
      setActionError(toRequestError(err).detail);
    } finally {
      setBusyId(null);
    }
  };

  const handleStatusToggle = async (userId: string, isActive: boolean) => {
    setActionError(null);
    setBusyId(userId);
    try {
      await updateUserStatus(userId, { is_active: !isActive });
      reload();
    } catch (err) {
      setActionError(toRequestError(err).detail);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Người dùng"
        description="Toàn bộ tài khoản trên hệ thống — cấp/thu hồi quyền host, khoá tài khoản."
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[240px_1fr]">
        <SelectField
          label="Vai trò"
          value={roleFilter}
          onChange={(event) => setRoleFilter(event.target.value)}
        >
          <option value="">Tất cả</option>
          <option value="user">User</option>
          <option value="host">Host</option>
          <option value="admin">Admin</option>
        </SelectField>
        <TextField
          label="Tìm kiếm"
          placeholder="Email, tên đăng nhập hoặc tên hiển thị..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          icon={<IconSearch className="h-4 w-4" />}
        />
      </div>

      {actionError !== null && <div className="mb-4"><ErrorPanel error={actionError} /></div>}
      {error !== null && <ErrorPanel error={error} />}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error === null && (data?.items.length ?? 0) === 0 && (
        <EmptyState
          title="Không có người dùng nào"
          icon={<IconUser className="h-6 w-6" />}
        />
      )}

      {!loading && error === null && (data?.items.length ?? 0) > 0 && (
        <Card>
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-400 dark:border-ink-700">
                    <th className="px-4 py-3 font-semibold">Người dùng</th>
                    <th className="px-4 py-3 font-semibold">Role</th>
                    <th className="px-4 py-3 font-semibold">Trạng thái</th>
                    <th className="px-4 py-3 font-semibold">Tạo lúc</th>
                    <th className="px-4 py-3 font-semibold">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100 dark:divide-ink-700/60">
                  {data?.items.map((user) => {
                    const isSelf = user.id === currentUser?.id;
                    const busy = busyId === user.id;
                    return (
                      <tr key={user.id}>
                        <td className="px-4 py-3">
                          <p className="font-medium text-ink-900 dark:text-ink-100">
                            {user.display_name ?? user.username}
                          </p>
                          <p className="text-xs text-ink-400">{user.email}</p>
                        </td>
                        <td className="px-4 py-3">
                          <select
                            className="input max-w-[140px] py-1.5 text-xs"
                            value={user.role}
                            disabled={busy || isSelf}
                            onChange={(event) => handleRoleChange(user.id, event.target.value)}
                            title={isSelf ? "Không thể tự sửa role của chính mình" : undefined}
                          >
                            <option value="user">user</option>
                            <option value="host">host</option>
                            <option value="admin">admin</option>
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={user.is_active ? "success" : "danger"}>
                            {user.is_active ? "Hoạt động" : "Bị khoá"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-xs text-ink-500">
                          {formatDateTime(user.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          {!isSelf && (
                            <Button
                              size="sm"
                              variant={user.is_active ? "secondary" : "primary"}
                              disabled={busy}
                              onClick={() => handleStatusToggle(user.id, user.is_active)}
                            >
                              {user.is_active ? "Khoá" : "Mở khoá"}
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
