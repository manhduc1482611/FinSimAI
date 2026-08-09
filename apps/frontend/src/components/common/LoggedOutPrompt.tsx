/**
 * LoggedOutPrompt — trạng thái khi chưa đăng nhập cho các trang yêu cầu tài khoản
 * (nhiệm vụ, cuộc thi...): thay vì gọi API để nhận 401, hiển thị lối vào đăng nhập.
 */
import Link from "next/link";

export function LoggedOutPrompt({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="card p-8 text-center">
      <h3 className="text-sm font-black text-ink-900 dark:text-slip">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-500 dark:text-granite-300">
        {description}
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <Link href="/login" className="btn-primary">
          Đăng nhập
        </Link>
        <Link href="/register" className="btn-secondary">
          Tạo tài khoản
        </Link>
      </div>
    </div>
  );
}
