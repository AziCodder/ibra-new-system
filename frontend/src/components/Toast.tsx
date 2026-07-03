import { createContext, useCallback, useContext, useEffect, useState } from 'react'

export type ToastType = 'success' | 'error' | 'info'

type ToastItem = { id: number; message: string; type: ToastType }

const TOAST_STYLES: Record<ToastType, { bg: string; border: string; color: string }> = {
  success: { bg: 'var(--color-success-bg)', border: 'var(--color-success)', color: 'var(--color-success)' },
  error: { bg: 'var(--color-danger-bg)', border: 'var(--color-danger)', color: 'var(--color-danger)' },
  info: { bg: 'var(--color-info-bg)', border: 'var(--color-info)', color: 'var(--color-info)' },
}

type ToastListener = (message: string, type: ToastType) => void
const listeners = new Set<ToastListener>()

/** Callable from anywhere (QueryClient defaults, mutations, etc.). */
export function toast(message: string, type: ToastType = 'info') {
  listeners.forEach((fn) => fn(message, type))
}

const ToastContext = createContext<(message: string, type?: ToastType) => void>(() => {})

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const show = useCallback((message: string, type: ToastType = 'info') => {
    const toastId = Date.now() + Math.random()
    setItems((prev) => [...prev, { id: toastId, message, type }])
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== toastId))
    }, 4500)
  }, [])

  useEffect(() => {
    listeners.add(show)
    return () => { listeners.delete(show) }
  }, [show])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none"
        style={{ maxWidth: 360 }}
      >
        {items.map((t) => {
          const s = TOAST_STYLES[t.type]
          return (
            <div
              key={t.id}
              className="rounded-xl px-4 py-3 text-sm font-medium shadow-lg pointer-events-auto"
              style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.color }}
            >
              {t.message}
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
