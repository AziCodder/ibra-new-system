import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchNotes, createNote } from '../api/notes'

export default function NotesSection({ orderId }: { orderId: number }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')

  const { data: notes, isLoading } = useQuery({
    queryKey: ['notes', orderId],
    queryFn: () => fetchNotes(orderId),
  })

  const mutation = useMutation({
    mutationFn: () => createNote(orderId, text.trim()),
    onSuccess: () => {
      setText('')
      queryClient.invalidateQueries({ queryKey: ['notes', orderId] })
    },
  })

  return (
    <div className="mt-8">
      <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>
        Заметки
      </h3>

      <div className="flex flex-col gap-3 mb-4">
        {isLoading && <div style={{ color: 'var(--color-muted)' }}>Загрузка...</div>}

        {!isLoading && notes?.length === 0 && (
          <div
            className="rounded-xl p-4 text-sm"
            style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
          >
            Заметок пока нет
          </div>
        )}

        {notes?.map((note) => (
          <div
            key={note.id}
            className="rounded-xl p-4 text-sm"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            <div className="flex items-center justify-between mb-1.5 text-xs" style={{ color: 'var(--color-muted)' }}>
              <span style={{ color: 'var(--color-text)', fontWeight: 600 }}>{note.author_name}</span>
              <span>{new Date(note.created_at).toLocaleString('ru-RU')}</span>
            </div>
            <p style={{ color: 'var(--color-text)', whiteSpace: 'pre-wrap' }}>{note.text}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          placeholder="Добавить заметку..."
          className="flex-1 rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
          style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <button
          onClick={() => mutation.mutate()}
          disabled={!text.trim() || mutation.isPending}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50 self-end"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          {mutation.isPending ? 'Сохранение...' : 'Добавить'}
        </button>
      </div>
    </div>
  )
}
