/**
 * Admin · Cuộc thi — toàn bộ contest trên hệ thống + đổi status (FR-2).
 */
"use client";

import { useState } from "react";

import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconGrid } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField } from "@/components/common/Field";
import { Spinner } from "@/components/common/Spinner";
import { ContestStatusBadge } from "@/components/contests/ContestStatusBadge";
import { useAsync } from "@/hooks/useAsync";
import { listAllContests, updateContestStatus } from "@/services/admin";
import { toRequestError } from "@/services/api";
import { difficultyLabel, templateLabel } from "@/utils/contest";
import { formatDateTime } from "@/utils/format";

export default function AdminContestsPage() {
  const [statusFilter, setStatusFilter] = useState("");

  const { data, loading, error, reload } = useAsync(
    () =>
      listAllContests({
        status: statusFilter || undefined,
        limit: 100,
      }),
    [statusFilter],
  );

  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleStatusChange = async (contestId: string, status: string) => {
    if (status !== "draft" && status !== "active" && status !== "ended") {
      return;
    }
    setActionError(null);
    setBusyId(contestId);
    try {
      await updateContestStatus(contestId, { status });
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
        title="Cuộc thi"
        description="Toàn bộ cuộc thi của mọi host — admin can thiệp trạng thái từng contest."
      />

      <div className="mb-4 max-w-[280px]">
        <SelectField
          label="Trạng thái"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
        >
          <option value="">Tất cả</option>
          <option value="draft">Nháp</option>
          <option value="active">Đang chạy</option>
          <option value="ended">Đã kết thúc</option>
        </SelectField>
      </div>

      {actionError !== null && (
        <div className="mb-4">
          <ErrorPanel error={actionError} />
        </div>
      )}
      {error !== null && <ErrorPanel error={error} />}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error === null && (data?.items.length ?? 0) === 0 && (
        <EmptyState
          title="Không có cuộc thi nào"
          icon={<IconGrid className="h-6 w-6" />}
        />
      )}

      {!loading && error === null && (data?.items.length ?? 0) > 0 && (
        <Card>
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-400 dark:border-ink-700">
                    <th className="px-4 py-3 font-semibold">Cuộc thi</th>
                    <th className="px-4 py-3 font-semibold">Khuôn · Độ khó</th>
                    <th className="px-4 py-3 font-semibold">Thành viên</th>
                    <th className="px-4 py-3 font-semibold">Tạo lúc</th>
                    <th className="px-4 py-3 font-semibold">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100 dark:divide-ink-700/60">
                  {data?.items.map((contest) => {
                    const busy = busyId === contest.id;
                    return (
                      <tr key={contest.id}>
                        <td className="px-4 py-3">
                          <p className="font-medium text-ink-900 dark:text-ink-100">
                            {contest.name}
                          </p>
                          <p className="text-xs text-ink-400">/contests/{contest.slug}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-ink-500">
                          {templateLabel(contest.config.template)} ·{" "}
                          {difficultyLabel(contest.config.difficulty)} ·{" "}
                          {contest.config.company_count} công ty
                        </td>
                        <td className="px-4 py-3 text-sm text-ink-700 dark:text-ink-200">
                          {contest.member_count}
                        </td>
                        <td className="px-4 py-3 text-xs text-ink-500">
                          {formatDateTime(contest.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <select
                              className="input max-w-[150px] py-1.5 text-xs"
                              value={contest.status}
                              disabled={busy}
                              onChange={(event) => handleStatusChange(contest.id, event.target.value)}
                            >
                              <option value="draft">Nháp</option>
                              <option value="active">Đang chạy</option>
                              <option value="ended">Đã kết thúc</option>
                            </select>
                            <ContestStatusBadge status={contest.status} />
                          </div>
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
