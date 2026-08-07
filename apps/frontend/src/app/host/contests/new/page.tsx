/**
 * Host · Tạo cuộc thi (contest builder) — FR-4.
 * Host chỉ chọn khuôn + vài lựa chọn; "Kích hoạt" chạy pipeline tự sinh.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/common/Button";
import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconCheck } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField, TextAreaField, TextField } from "@/components/common/Field";
import { activateContest, createContest } from "@/services/contests";
import { toRequestError } from "@/services/api";
import { cn } from "@/utils/cn";
import {
  resolveRulesPreview,
  TEMPLATE_OPTIONS,
  type Difficulty,
  type TemplateId,
} from "@/utils/contest";
import { formatCompactVND } from "@/utils/format";
import type { ContestResponse } from "@finsim/shared-types/generated/api-types";

type Phase = "form" | "created";

export default function NewContestPage() {
  const router = useRouter();

  const [template, setTemplate] = useState<TemplateId>("classic");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [industry, setIndustry] = useState("");
  const [companyCount, setCompanyCount] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("normal");
  const [autoNews, setAutoNews] = useState(true);
  const [autoSocial, setAutoSocial] = useState(true);
  const [primaryColor, setPrimaryColor] = useState("#0ea5e9");

  const [phase, setPhase] = useState<Phase>("form");
  const [created, setCreated] = useState<ContestResponse | null>(null);
  const [busy, setBusy] = useState<"create" | "activate" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeTemplate =
    TEMPLATE_OPTIONS.find((option) => option.id === template) ?? TEMPLATE_OPTIONS[0];

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setBusy("create");
    try {
      const contest = await createContest({
        name: name.trim(),
        slug: slug.trim() || null,
        description: description.trim() || null,
        template,
        industry: industry.trim() || activeTemplate.defaultIndustry,
        company_count: companyCount.trim() === "" ? null : Number(companyCount),
        difficulty,
        auto_news: autoNews,
        auto_social: autoSocial,
        theme: { primary_color: primaryColor },
      });
      setCreated(contest);
      setPhase("created");
    } catch (err) {
      setError(toRequestError(err).detail);
    } finally {
      setBusy(null);
    }
  };

  const handleActivate = async () => {
    if (created === null) {
      return;
    }
    setError(null);
    setBusy("activate");
    try {
      const contest = await activateContest(created.slug);
      setCreated(contest);
      router.push(`/contests/${contest.slug}`);
    } catch (err) {
      setError(toRequestError(err).detail);
      setBusy(null);
    }
  };

  if (phase === "created" && created !== null) {
    return (
      <div>
        <PageHeader
          title="Đã tạo cuộc thi"
          description="Chọn bước tiếp theo — hệ thống tự sinh dữ liệu khi bạn kích hoạt."
        />
        {error !== null && <ErrorPanel error={error} />}
        <Card>
          <CardBody className="space-y-4">
            <div>
              <p className="text-sm font-semibold text-ink-900">{created.name}</p>
              <p className="text-xs text-ink-400">/contests/{created.slug}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button loading={busy === "activate"} onClick={handleActivate}>
                Kích hoạt cuộc thi
              </Button>
              <Link href={`/contests/${created.slug}`} className="btn-secondary">
                Xem trước
              </Link>
              <Link href="/host/contests" className="btn-ghost">
                Về danh sách
              </Link>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  const rules = resolveRulesPreview(activeTemplate, difficulty);

  return (
    <div>
      <PageHeader
        title="Tạo cuộc thi"
        description="Chọn khuôn và vài lựa chọn — hệ thống tự sinh công ty, tin tức, bài viết và giá."
      />

      {error !== null && <ErrorPanel error={error} />}

      <form onSubmit={handleCreate} className="space-y-6">
        <Card>
          <CardHeader
            title="1 · Chọn khuôn (template)"
            description="Mỗi khuôn định sẵn số công ty, tỷ lệ tin/social và quy tắc giao dịch mặc định."
          />
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-2">
              {TEMPLATE_OPTIONS.map((option) => {
                const selected = option.id === template;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setTemplate(option.id)}
                    className={cn(
                      "rounded-xl border p-4 text-left transition-colors",
                      selected
                        ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/30 dark:bg-brand-500/10"
                        : "border-ink-200 hover:border-ink-300 dark:border-ink-700",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-ink-900 dark:text-ink-100">
                        {option.label}
                      </p>
                      {selected && <IconCheck className="h-4 w-4 text-brand-600" />}
                    </div>
                    <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">
                      {option.description}
                    </p>
                    <p className="mt-2 text-xs text-ink-400 dark:text-ink-500">
                      {option.defaultCompanyCount} công ty · {formatCompactVND(option.defaultStartCash)} vốn
                    </p>
                  </button>
                );
              })}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="2 · Thông tin cuộc thi"
            description="Tên + vài lựa chọn điều chỉnh theo ý host."
          />
          <CardBody className="space-y-4">
            <TextField
              label="Tên cuộc thi"
              placeholder="Ví dụ: Đấu trường chứng khoán mùa 1"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Slug (URL)"
                hint="để trống để tự sinh"
                placeholder="dau-truong-mua-1"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
              />
              <TextField
                label="Lĩnh vực"
                placeholder={activeTemplate.defaultIndustry}
                value={industry}
                onChange={(event) => setIndustry(event.target.value)}
              />
            </div>
            <TextAreaField
              label="Mô tả"
              placeholder="Giới thiệu ngắn về cuộc thi (không bắt buộc)"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Số công ty"
                hint="3–20"
                type="number"
                min={3}
                max={20}
                placeholder={String(activeTemplate.defaultCompanyCount)}
                value={companyCount}
                onChange={(event) => setCompanyCount(event.target.value)}
              />
              <SelectField
                label="Độ khó"
                value={difficulty}
                onChange={(event) => setDifficulty(event.target.value as Difficulty)}
              >
                <option value="easy">Dễ — giá ổn định, vốn nhiều hơn</option>
                <option value="normal">Thường</option>
                <option value="hard">Khó — giá biến động mạnh, vốn ít hơn</option>
              </SelectField>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex items-center gap-2 text-sm text-ink-700 dark:text-ink-200">
                <input
                  type="checkbox"
                  checked={autoNews}
                  onChange={(event) => setAutoNews(event.target.checked)}
                  className="h-4 w-4 rounded border-ink-300"
                />
                Tự sinh tin tức & bài viết
              </label>
              <label className="flex items-center gap-2 text-sm text-ink-700 dark:text-ink-200">
                <input
                  type="checkbox"
                  checked={autoSocial}
                  onChange={(event) => setAutoSocial(event.target.checked)}
                  className="h-4 w-4 rounded border-ink-300"
                />
                Tự sinh bài đăng xã hội
              </label>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="label">Màu chủ đạo</p>
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(event) => setPrimaryColor(event.target.value)}
                  className="h-10 w-16 cursor-pointer rounded-lg border border-ink-300 bg-white dark:border-ink-700"
                />
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="3 · Quy tắc giao dịch (tự sinh)"
            description="Hệ thống resolve từ khuôn + độ khó — không cần host nhập."
          />
          <CardBody>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-ink-400">Vốn khởi đầu</dt>
                <dd className="mt-1 text-sm font-semibold text-ink-900">
                  {formatCompactVND(rules.startCash)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-ink-400">Cooldown</dt>
                <dd className="mt-1 text-sm font-semibold text-ink-900">
                  {rules.cooldownSeconds} giây
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-ink-400">Đòn bẩy giá</dt>
                <dd className="mt-1 text-sm font-semibold text-ink-900">
                  ×{rules.volatilityMultiplier}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-ink-400">Bán khống</dt>
                <dd className="mt-1 text-sm font-semibold text-ink-900">
                  {activeTemplate.allowShort ? "Cho phép" : "Không cho phép"}
                </dd>
              </div>
            </dl>
          </CardBody>
        </Card>

        <div className="flex items-center justify-end gap-2">
          <Link href="/host/contests" className="btn-ghost">
            Huỷ
          </Link>
          <Button type="submit" loading={busy === "create"} disabled={busy !== null}>
            Tạo cuộc thi
          </Button>
        </div>
      </form>
    </div>
  );
}
