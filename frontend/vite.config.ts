import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8012'

// Правки с хоста попадают в контейнер через bind-mount, а события файловой
// системы по нему не проходят (Windows, macOS) — без опроса Vite их не видит,
// и контейнер приходилось перезапускать руками после каждого изменения.
// Вне докера опрос не нужен и только греет процессор, поэтому включается флагом.
const usePolling = process.env.VITE_DEV_POLLING === '1'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allows the backend container to probe this dev server by its compose
    // service name (Host: frontend:5173) for the system-health page.
    allowedHosts: ['frontend'],
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
})
