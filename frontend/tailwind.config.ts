import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#F4F5F1",
          100: "#E8EBE3",
          200: "#D8DDD0",
          500: "#5E6D62",
          700: "#33453A",
          900: "#152A22",
        },
        brass: {
          DEFAULT: "#A9762E",
          50: "#F6EEDF",
          600: "#8C611F",
        },
      },
      fontFamily: {
        sans: ["Pretendard Variable", "Pretendard", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
