import path from "path";
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    path.join(__dirname, "src/**/*.{js,ts,jsx,tsx,mdx}"),
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./web/src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
