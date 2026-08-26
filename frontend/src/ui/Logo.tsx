/**
 * Знак Ibra Flow.
 *
 * Стрелка со следом движения: система про поток заказов — от закупки к
 * приёмке. Форма выбрана из расчёта на 16 пикселей фавикона и на круглую
 * обрезку аватарки в Telegram, поэтому элементов мало, а линии толстые:
 * тонкий рисунок в этих размерах превращается в кашу.
 */
export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="ibraflow-bg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#9d6bff" />
          <stop offset="1" stopColor="#6d28d9" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill="url(#ibraflow-bg)" />
      {/* След движения: две короткие полосы позади стрелки. */}
      <rect x="9" y="12.5" width="11" height="5" rx="2.5" fill="#fff" opacity="0.5" />
      <rect x="9" y="30.5" width="11" height="5" rx="2.5" fill="#fff" opacity="0.5" />
      {/* Сама стрелка: древко и остриё. */}
      <rect x="9" y="21" width="19" height="6" rx="3" fill="#fff" />
      <path d="M24 12.5 38.5 24 24 35.5Z" fill="#fff" />
    </svg>
  )
}
