/** Đăng ký — tạo tài khoản mới, tự động đăng nhập và vào dashboard. */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { TextField } from "@/components/common/Field";
import { toRequestError } from "@/services/api";
import { useAuthStore } from "@/store/useAuthStore";

interface FieldErrors {
  email?: string;
  username?: string;
  password?: string;
  displayName?: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((state) => state.register);
  const status = useAuthStore((state) => state.status);

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: FieldErrors = {};
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      nextErrors.email = "Email không hợp lệ";
    }
    if (!/^[a-zA-Z0-9_]{3,}$/.test(username)) {
      nextErrors.username = "Ít nhất 3 ký tự, chỉ gồm chữ/số/gạch dưới";
    }
    if (password.length < 8) {
      nextErrors.password = "Mật khẩu tối thiểu 8 ký tự";
    }
    if (password !== confirmPassword) {
      nextErrors.password = "Xác nhận mật khẩu không khớp";
    }
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    setFormError(null);
    try {
      await register({
        email,
        username,
        password,
        display_name: displayName.trim() || null,
      });
      router.replace("/news");
    } catch (error) {
      setFormError(toRequestError(error).detail);
    }
  };

  return (
    <Card>
      <CardBody className="space-y-5 px-6 py-8">
        <div>
          <h1 className="text-xl font-bold text-ink-900">Tạo tài khoản</h1>
          <p className="mt-1 text-sm text-ink-500">
            Bắt đầu với vốn mô phỏng 100.000.000 ₫ và rèn kỷ luật cùng AI Mentor.
          </p>
        </div>

        {formError !== null && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {formError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <TextField
            label="Email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={fieldErrors.email}
            autoComplete="email"
          />
          <TextField
            label="Tên đăng nhập"
            placeholder="username"
            hint="(3-100 ký tự, chỉ chữ/số/_)"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            error={fieldErrors.username}
            autoComplete="username"
          />
          <TextField
            label="Tên hiển thị"
            placeholder="Tên hiển thị (tuỳ chọn)"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            error={fieldErrors.displayName}
          />
          <TextField
            label="Mật khẩu"
            type="password"
            placeholder="••••••••"
            hint="(tối thiểu 8 ký tự)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
            autoComplete="new-password"
          />
          <TextField
            label="Xác nhận mật khẩu"
            type="password"
            placeholder="••••••••"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
          />
          <Button
            type="submit"
            fullWidth
            size="lg"
            loading={status === "loading"}
            disabled={status === "loading"}
          >
            Đăng ký
          </Button>
        </form>

        <p className="text-center text-sm text-ink-500">
          Đã có tài khoản?{" "}
          <Link href="/login" className="font-semibold text-brand-600 hover:underline">
            Đăng nhập
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}
