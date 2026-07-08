import type { Config } from 'tailwindcss';
const config: Config = { content: ['./app/**/*.{js,ts,jsx,tsx}'], theme: { extend: { boxShadow: { glow: '0 0 0 1px rgba(117,85,255,.18), 0 18px 60px rgba(9,5,31,.46)' } } }, plugins: [] };
export default config;
