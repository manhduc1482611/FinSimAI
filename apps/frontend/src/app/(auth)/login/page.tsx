/** Đăng nhập — xác thực qua `/auth/login`, chuyển vào dashboard sau thành công. */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { TextField } from "@/components/common/Field";
import { toRequestError } from "@/services/api";
import { useAuthStore } from "@/store/useAuthStore";
import { homePathForRole } from "@/utils/roles";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const status = useAuthStore((state) => state.status);

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    identifier?: string;
    password?: string;
  }>({});
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: { identifier?: string; password?: string } = {};
    if (!identifier.trim()) {
      nextErrors.identifier = "Vui lòng nhập tên đăng nhập hoặc email";
    }
    if (!password) {
      nextErrors.password = "Vui lòng nhập mật khẩu";
    }
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    setFormError(null);
    try {
      await login({ password, username: identifier.trim() });
      // FR-8, FR-9: 1 form chung → redirect theo role.
      router.replace(homePathForRole(useAuthStore.getState().user?.role));
    } catch (error) {
      setFormError(toRequestError(error).detail);
    }
  };

  return (
    <Card>
      <CardBody className="space-y-5 px-6 py-8">
        <div>
          <h1 className="text-xl font-bold text-ink-900">Đăng nhập</h1>
          <p className="mt-1 text-sm text-ink-500">
            Tiếp tục hành trình luyện tập đầu tư của bạn.
          </p>
        </div>

        {formError !== null && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {formError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <TextField
            label="Tên đăng nhập hoặc email"
            placeholder="username hoặc you@example.com"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            error={fieldErrors.identifier}
            autoComplete="username"
          />
          <TextField
            label="Mật khẩu"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
            autoComplete="current-password"
          />
          <Button
            type="submit"
            fullWidth
            size="lg"
            loading={status === "loading"}
            disabled={status === "loading"}
          >
            Đăng nhập
          </Button>
        </form>

        <p className="text-center text-sm text-ink-500">
          Chưa có tài khoản?{" "}
          <Link href="/register" className="font-semibold text-brand-600 hover:underline">
            Đăng ký
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}
