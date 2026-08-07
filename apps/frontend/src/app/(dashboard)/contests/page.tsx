/**
 * Cuộc thi — browse & join các contest đang mở (FR-6).
 */
"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconGrid } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { Spinner } from "@/components/common/Spinner";
import { ContestStatusBadge } from "@/components/contests/ContestStatusBadge";
import { useAsync } from "@/hooks/useAsync";
import { joinContest, listContests } from "@/services/contests";
import { toRequestError } from "@/services/api";
import { difficultyLabel, templateLabel } from "@/utils/contest";

export default function ContestsPage() {
  const { data, loading, error, reload } = useAsync(() => listContests({ limit: 100 }));
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [joinedSlug, setJoinedSlug] = useState<string | null>(null);

  const handleJoin = async (slug: string) => {
    setActionError(null);
    setBusySlug(slug);
    try {
      await joinContest(slug);
      setJoinedSlug(slug);
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
        title="Cuộc thi"
        description="Tham gia các đấu trường mô phỏng — mỗi contest là một bản web thu nhỏ riêng."
      />

      {actionError !== null && <ErrorPanel error={actionError} />}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error !== null && <ErrorPanel error={error} />}

      {!loading && error === null && (data?.items.length ?? 0) === 0 && (
        <EmptyState
          title="Chưa có cuộc thi nào đang mở"
          description="Quay lại sau khi host kích hoạt một cuộc thi mới."
          icon={<IconGrid className="h-6 w-6" />}
        />
      )}

      {!loading && error === null && (data?.items.length ?? 0) > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data?.items.map((contest) => {
            const config = contest.config;
            const isJoined = joinedSlug === contest.slug;
            return (
              <Card key={contest.id}>
                <CardBody className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/contests/${contest.slug}`}
                        className="text-sm font-semibold text-ink-900 hover:text-brand-700 dark:text-ink-100"
                      >
                        {contest.name}
                      </Link>
                      <p className="mt-0.5 text-xs text-ink-400 dark:text-ink-500">
                        /contests/{contest.slug}
                      </p>
                    </div>
                    <ContestStatusBadge status={contest.status} />
                  </div>

                  {contest.description !== null && contest.description !== "" && (
                    <p className="line-clamp-2 text-sm text-ink-500 dark:text-ink-400">
                      {contest.description}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant="info">{templateLabel(config.template)}</Badge>
                    <Badge variant="neutral">{difficultyLabel(config.difficulty)}</Badge>
                    <Badge variant="neutral">{config.company_count} công ty</Badge>
                    <Badge variant="neutral">{contest.member_count} thành viên</Badge>
                  </div>

                  <div className="flex items-center gap-2">
                    <Link href={`/contests/${contest.slug}`} className="btn-secondary px-3 py-1.5 text-xs">
                      Xem chi tiết
                    </Link>
                    {contest.status === "active" && (
                      <Button
                        size="sm"
                        variant={isJoined ? "secondary" : "primary"}
                        disabled={isJoined || busySlug === contest.slug}
                        onClick={() => handleJoin(contest.slug)}
                      >
                        {isJoined ? "Đã tham gia" : "Tham gia"}
                      </Button>
                    )}
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
