/**
 * Field — nhóm label + input + thông báo lỗi dùng cho các form.
 */
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

import { cn } from "@/utils/cn";

export interface FieldWrapperProps {
  label?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

export function FieldWrapper({ label, hint, error, children }: FieldWrapperProps) {
  return (
    <div>
      {label !== undefined && (
        <label className="label">
          {label}
          {hint !== undefined && (
            <span className="ml-1 font-normal normal-case tracking-normal text-ink-400 dark:text-ink-500">
              {hint}
            </span>
          )}
        </label>
      )}
      {children}
      {error !== undefined && (
        <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}

export interface TextFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  hint?: string;
  error?: string;
  size?: "sm" | "md";
  /** Icon hiển thị phía trước (prefix). */
  icon?: ReactNode;
}

export function TextField({
  label,
  hint,
  error,
  className,
  size = "md",
  icon,
  ...rest
}: TextFieldProps) {
  return (
    <FieldWrapper label={label} hint={hint} error={error}>
      <div className="relative">
        {icon !== undefined && (
          <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-400">
            {icon}
          </span>
        )}
        <input
          className={cn(
            "input",
            icon !== undefined && "pl-9",
            size === "sm" && "py-1.5 text-xs",
            error !== undefined && "border-red-400 focus:border-red-500 focus:ring-red-500/20",
            className,
          )}
          aria-invalid={error !== undefined}
          {...rest}
        />
      </div>
    </FieldWrapper>
  );
}

export interface SelectFieldProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  label?: string;
  hint?: string;
  error?: string;
  size?: "sm" | "md";
  children: ReactNode;
}

export function SelectField({
  label,
  hint,
  error,
  className,
  size = "md",
  children,
  ...rest
}: SelectFieldProps) {
  return (
    <FieldWrapper label={label} hint={hint} error={error}>
      <select
        className={cn(
          "input",
          size === "sm" && "py-1.5 text-xs",
          error !== undefined && "border-red-400 focus:border-red-500 focus:ring-red-500/20",
          className,
        )}
        aria-invalid={error !== undefined}
        {...rest}
      >
        {children}
      </select>
    </FieldWrapper>
  );
}

export interface TextAreaFieldProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export function TextAreaField({
  label,
  hint,
  error,
  className,
  ...rest
}: TextAreaFieldProps) {
  return (
    <FieldWrapper label={label} hint={hint} error={error}>
      <textarea
        className={cn(
          "input min-h-[96px] resize-y",
          error !== undefined && "border-red-400 focus:border-red-500 focus:ring-red-500/20",
          className,
        )}
        aria-invalid={error !== undefined}
        {...rest}
      />
    </FieldWrapper>
  );
}
