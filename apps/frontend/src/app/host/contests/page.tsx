/**
 * Host · Danh sách cuộc thi của mình — status, số member, kích hoạt/xoá (FR-4).
 */
"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconGrid, IconNews } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { Spinner } from "@/components/common/Spinner";
import { ContestStatusBadge } from "@/components/contests/ContestStatusBadge";
import { useAsync } from "@/hooks/useAsync";
import { activateContest, deleteContest, listContests } from "@/services/contests";
import { toRequestError } from "@/services/api";
import { useAuthStore } from "@/store/useAuthStore";
import { difficultyLabel, templateLabel } from "@/utils/contest";
import { formatDateTime } from "@/utils/format";

export default function HostContestsPage() {
  const currentUser = useAuthStore((state) => state.user);
  const { data, loading, error, reload } = useAsync(() => listContests({ limit: 100 }));
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const own =
    data?.items.filter((contest) => contest.owner_id === currentUser?.id) ?? [];

  const handleActivate = async (slug: string) => {
    setActionError(null);
    setBusySlug(slug);
    try {
      await activateContest(slug);
      reload();
    } catch (err) {
      setActionError(toRequestError(err).detail);
    } finally {
      setBusySlug(null);
    }
  };

  const handleDelete = async (slug: string) => {
    if (!window.confirm("Xoá cuộc thi này? (chuyển trạng thái kết thúc, không thể hoàn tác)")) {
      return;
    }
    setActionError(null);
    setBusySlug(slug);
    try {
      await deleteContest(slug);
      reload();
    } catch (err) {
      setActionError(toRequestError(err).detail);
    } finally {
      setBusySlug(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Cuộc thi của tôi"
        description="Tạo cuộc thi bằng vài lựa chọn, hệ thống tự sinh công ty/tin tức/giá khi kích hoạt."
        actions={
          <Link href="/host/contests/new" className="btn-primary">
            <IconNews className="h-4 w-4" />
            Tạo cuộc thi
          </Link>
        }
      />

      {actionError !== null && <ErrorPanel error={actionError} />}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error !== null && <ErrorPanel error={error} />}

      {!loading && error === null && own.length === 0 && (
        <EmptyState
          title="Chưa có cuộc thi nào"
          description="Bắt đầu bằng cách chọn khuôn, lĩnh vực và độ khó — hệ thống tự tạo toàn bộ nội dung."
          icon={<IconGrid className="h-6 w-6" />}
          action={
            <Link href="/host/contests/new" className="btn-primary">
              Tạo cuộc thi đầu tiên
            </Link>
          }
        />
      )}

      {!loading && error === null && own.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {own.map((contest) => {
            const config = contest.config;
            const isBusy = busySlug === contest.slug;
            return (
              <Card key={contest.id}>
                <CardBody className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/contests/${contest.slug}`}
                        className="text-sm font-semibold text-ink-900 hover:text-brand-700 dark:text-slip"
                      >
                        {contest.name}
                      </Link>
                      <p className="mt-0.5 text-xs text-ink-400 dark:text-granite-400">
                        /contests/{contest.slug}
                      </p>
                    </div>
                    <ContestStatusBadge status={contest.status} />
                  </div>

                  <p className="text-xs text-ink-500 dark:text-granite-400">
                    {templateLabel(config.template)} · {difficultyLabel(config.difficulty)} ·{" "}
                    {config.company_count} công ty · {contest.member_count} thành viên
                  </p>
                  <p className="text-xs text-ink-400 dark:text-granite-400">
                    Tạo lúc {formatDateTime(contest.created_at)}
                  </p>

                  <div className="flex flex-wrap items-center gap-2">
                    {contest.status === "draft" && (
                      <Button
                        size="sm"
                        loading={isBusy}
                        disabled={isBusy}
                        onClick={() => handleActivate(contest.slug)}
                      >
                        Kích hoạt
                      </Button>
                    )}
                    <Link
                      href={`/contests/${contest.slug}`}
                      className="btn-secondary px-3 py-1.5 text-xs"
                    >
                      Xem trước
                    </Link>
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={isBusy}
                      onClick={() => handleDelete(contest.slug)}
                    >
                      Xoá
                    </Button>
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
