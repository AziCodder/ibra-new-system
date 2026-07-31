import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8012'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allows the backend container to probe this dev server by its compose
    // service name (Host: frontend:5173) for the system-health page.
    allowedHosts: ['frontend'],
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
})
