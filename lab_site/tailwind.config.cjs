/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{astro,html,js,ts,jsx,tsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        'bg-2': 'var(--bg-2)',
        'bg-3': 'var(--bg-3)',
        rose: 'var(--rose)',
        'rose-deep': 'var(--rose-deep)',
        'rose-soft': 'var(--rose-soft)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        line: 'var(--line)',
      },
      fontFamily: {
        body: ['"Manrope"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        script: ['"Dancing Script"', 'cursive'],
      },
      maxWidth: {
        site: '1120px',
      },
    },
  },
  plugins: [],
};
