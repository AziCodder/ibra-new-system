interface PydanticErrorItem { type?: string; loc?: (string | number)[]; msg?: string }
interface StructuredDetail { message?: string; [key: string]: unknown }

/** An Error carrying the HTTP status, so callers can tell "not found" apart from a real fetch failure. */
export class HttpError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * FastAPI error bodies come in one of three shapes: a plain string `detail`,
 * a pydantic validation array, or a structured object with a `message` field
 * plus extra data (e.g. `order_numbers`). This turns any of them into one
 * readable line; pass `knownMessages` to translate specific known strings.
 */
export function extractErrorMessage(payload: unknown, fallback: string, knownMessages: Record<string, string> = {}): string {
  const detail = (payload as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') {
    return knownMessages[detail] || detail
  }
  if (Array.isArray(detail)) {
    const items = detail as PydanticErrorItem[]
    const msgs = items.map((d) => d.msg).filter(Boolean) as string[]
    if (msgs.length) return msgs.join('; ')
  }
  if (detail && typeof detail === 'object' && typeof (detail as StructuredDetail).message === 'string') {
    return (detail as StructuredDetail).message as string
  }
  return fallback
}

/** Pulls a structured field off a FastAPI error's `detail` object (e.g. `order_numbers`), if present. */
export function extractErrorDetail<T>(payload: unknown, key: string): T | undefined {
  const detail = (payload as { detail?: unknown } | null)?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return (detail as Record<string, unknown>)[key] as T | undefined
  }
  return undefined
}
