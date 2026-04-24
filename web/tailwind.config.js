/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#4a7df8",
        "primary-dark": "#3a6de8",
        "primary-light": "#7aa5fc",
        navy: {
          950: "#060d1f",
          900: "#08122a",
          800: "#0d1e3d",
          750: "#112448",
          700: "#162d5a",
          600: "#1e3a6e",
          500: "#2d52a0",
        },
        success: "#22c55e",
        danger: "#ef4444",
        warning: "#f59e0b",
        neutral: "#64748b",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
