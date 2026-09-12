import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.BACKEND_URL || 'http://localhost:8092'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    allowedHosts: ['console'],
    watch: { ignored: ['**/e2e/**'] },
    proxy: {
      '/api': { target: backend, changeOrigin: true, timeout: 600000 },
      '/mcp': { target: backend, changeOrigin: true, timeout: 600000 },
    },
  },
})
