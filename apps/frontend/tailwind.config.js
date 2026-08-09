/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#E9F7EF",
          100: "#CBEFDB",
          200: "#9EE0BD",
          300: "#6ACC9D",
          400: "#3CB67A",
          500: "#1F9E5F",
          600: "#19824E",
          700: "#146740",
          800: "#115234",
          900: "#0D4229",
        },
        ink: {
          50: "#F7F5F0",
          100: "#EDE9E0",
          200: "#DBD4C5",
          300: "#B7AE9C",
          400: "#787166",
          500: "#6B6456",
          600: "#4C473C",
          700: "#35322B",
          800: "#23211C",
          900: "#171610",
          950: "#0E0D0B",
        },
        granite: {
          50: "#F2F1EE",
          100: "#E2E0DC",
          200: "#C2BFB8",
          300: "#9E9A91",
          400: "#8B867C",
          500: "#58554F",
          600: "#3F3D38",
          700: "#2D2B27",
          800: "#211F1C",
          900: "#171615",
          950: "#0D0C0B",
        },
        slip: {
          DEFAULT: "#F8F5EF",
          line: "#E3DCCB",
        },
        mkt: {
          up: {
            DEFAULT: "#16A34A",
            400: "#2AC364",
            500: "#1CAE56",
          },
          down: {
            DEFAULT: "#DC2626",
            400: "#F04949",
            500: "#E23636",
          },
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Aptos",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(13 12 11 / 0.18), 0 8px 24px -12px rgb(13 12 11 / 0.35)",
        board: "inset 0 1px 0 0 rgb(255 255 255 / 0.04), 0 1px 0 0 rgb(0 0 0 / 0.6)",
        press: "inset 0 2px 4px 0 rgb(13 12 11 / 0.3)",
      },
      borderRadius: {
        slip: "0.625rem",
      },
      letterSpacing: {
        board: "0.12em",
      },
      keyframes: {
        "stamp-in": {
          "0%": { transform: "scale(1.9) rotate(-14deg)", opacity: "0" },
          "55%": { transform: "scale(0.96) rotate(-8deg)", opacity: "1" },
          "100%": { transform: "scale(1) rotate(-8deg)", opacity: "1" },
        },
        "flicker-on": {
          "0%": { opacity: "0", transform: "translateY(2px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "stamp-in": "stamp-in 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) both",
        "flicker-on": "flicker-on 0.2s ease-out both",
      },
    },
  },
  plugins: [],
};
