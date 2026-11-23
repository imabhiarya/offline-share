/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'] },
      colors: {
        // Brand palette driven by CSS variables so the theme can be switched at runtime (see index.css)
        maroon: Object.fromEntries([50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map((k) => [k, `rgb(var(--brand-${k}) / <alpha-value>)`])),
        ink: { 50: '#f8f7f7', 100: '#efeced', 200: '#e1dcde', 300: '#c9c1c4', 400: '#9e9397', 500: '#7a6e72',
               600: '#5f5458', 700: '#4a4145', 800: '#332c2f', 900: '#211b1d' },
      },
      boxShadow: {
        card: '0 1px 2px rgba(90,34,49,.04), 0 4px 16px rgba(90,34,49,.06)',
        pop: '0 10px 40px rgba(51,15,25,.18)',
      },
      borderRadius: { xl: '14px', '2xl': '18px' },
    },
  },
  plugins: [],
}
