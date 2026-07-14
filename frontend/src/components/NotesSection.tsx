import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchNotes, createNote, type Note } from '../api/notes'
import ErrorState from './ErrorState'
import Skeleton from './Skeleton'
import { useAuth } from '../contexts/AuthContext'

export default function NotesSection({ orderId }: { orderId: number }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [text, setText] = useState('')

  const { data: notes, isLoading, isError, refetch } = useQuery({
    queryKey: ['notes', orderId],
    queryFn: () => fetchNotes(orderId),
  })

  const mutation = useMutation({
    mutationFn: (trimmed: string) => createNote(orderId, trimmed),
    onMutate: async (trimmed) => {
      await queryClient.cancelQueries({ queryKey: ['notes', orderId] })
      const previous = queryClient.getQueryData<Note[]>(['notes', orderId])
      const optimistic: Note = {
        id: -Date.now(),
        order_id: orderId,
        author_id: user?.id ?? 0,
        author_name: user?.full_name || user?.login || 'Вы',
        text: trimmed,
        created_at: new Date().toISOString(),
      }
      queryClient.setQueryData<Note[]>(['notes', orderId], (old) => [...(old ?? []), optimistic])
      setText('')
      return { previous }
    },
    onError: (_err, trimmed, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(['notes', orderId], ctx.previous)
      setText(trimmed)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['notes', orderId] })
    },
  })

  return (
    <div className="mt-8">
      <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>
        Заметки
      </h3>

      <div className="flex flex-col gap-3 mb-4">
        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} height={72} radius={12} />
            ))}
          </div>
        )}

        {!isLoading && isError && (
          <ErrorState message="Не удалось загрузить заметки" onRetry={() => refetch()} />
        )}

        {!isLoading && !isError && notes?.length === 0 && (
          <div
            className="rounded-[8px] p-4 text-sm"
            style={{ background: 'var(--color-surface)', border: '1px dashed var(--color-border)', color: 'var(--color-muted)' }}
          >
            Заметок пока нет
          </div>
        )}

        {notes?.map((note) => (
          <div
            key={note.id}
            className="rounded-[8px] p-4 text-sm"
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

      {user?.role !== 'observer' && (
      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          placeholder="Добавить заметку..."
          className="flex-1 rounded-lg px-3 py-2.5 text-sm outline-none resize-none"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <button
          onClick={() => mutation.mutate(text.trim())}
          disabled={!text.trim() || mutation.isPending}
          className="rounded-lg px-4 py-2 text-sm font-medium cursor-pointer disabled:opacity-50 self-end"
          style={{ background: 'var(--color-primary)', color: '#fff' }}
        >
          {mutation.isPending ? 'Сохранение...' : 'Добавить'}
        </button>
      </div>
      )}
    </div>
  )
}
