import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// All assets (fonts, icons, scripts) are bundled locally – no CDN or internet access is needed at runtime.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', assetsDir: 'assets', sourcemap: false, chunkSizeWarningLimit: 1500 },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/ws': { target: 'ws://127.0.0.1:5000', ws: true },
      '/health': 'http://127.0.0.1:5000',
    },
  },
})
