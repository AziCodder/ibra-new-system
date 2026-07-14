import { useState, useRef, type DragEvent } from 'react'

export interface UploadedFile {
  key: string
  filename: string
  size: number
}

const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp'])

export function isImageKey(key: string): boolean {
  const dot = key.lastIndexOf('.')
  if (dot === -1) return false
  return IMAGE_EXTENSIONS.has(key.slice(dot).toLowerCase())
}

interface FileUploaderProps {
  files: UploadedFile[]
  onUpload: (file: UploadedFile) => void
  onRemove: (key: string) => void
  disabled?: boolean
}

export default function FileUploader({ files, onUpload, onRemove, disabled }: FileUploaderProps) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function upload(file: File) {
    setError('')
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Upload failed')
      }
      const uploaded: UploadedFile = await res.json()
      onUpload(uploaded)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && !disabled) upload(file)
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) upload(file)
    e.target.value = ''
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className="rounded-lg p-6 text-center text-sm transition-colors cursor-pointer"
        style={{
          border: `2px dashed ${dragging ? 'var(--color-primary)' : 'var(--color-border)'}`,
          background: dragging ? 'var(--color-primary-bg)' : 'var(--color-surface-2)',
          color: 'var(--color-muted)',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {uploading ? 'Загрузка...' : 'Перетащите файл или нажмите для выбора'}
        <input ref={inputRef} type="file" onChange={handleFileSelect} className="hidden" />
      </div>

      {error && (
        <div className="mt-2 text-xs" style={{ color: 'var(--color-danger)' }}>{error}</div>
      )}

      {files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {files.map((f) => (
            <li
              key={f.key}
              className="flex items-center justify-between rounded-lg px-3 py-2 text-sm"
              style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
            >
              <a
                href={`/api/files/${f.key}`}
                target="_blank"
                rel="noreferrer"
                className="truncate mr-2 hover:underline"
                style={{ color: 'var(--color-text)' }}
              >
                {f.filename}
              </a>
              <span className="flex items-center gap-3">
                <span style={{ color: 'var(--color-muted)' }}>{formatSize(f.size)}</span>
                {!disabled && (
                  <button
                    onClick={() => onRemove(f.key)}
                    className="text-xs cursor-pointer"
                    style={{ color: 'var(--color-danger)' }}
                  >
                    Удалить
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
