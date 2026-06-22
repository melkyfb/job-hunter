import { useTheme, type Theme } from '../hooks/useTheme'

const OPTIONS: { value: Theme; label: string; icon: string }[] = [
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'system', label: 'System', icon: '💻' },
  { value: 'dark', label: 'Dark', icon: '🌙' },
]

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <div
      role="group"
      aria-label="Color theme"
      style={{
        display: 'inline-flex',
        border: '1px solid var(--border)',
        borderRadius: 8,
        overflow: 'hidden',
        fontSize: 12,
      }}
    >
      {OPTIONS.map(opt => (
        <button
          key={opt.value}
          onClick={() => setTheme(opt.value)}
          aria-pressed={theme === opt.value}
          title={opt.label}
          style={{
            padding: '5px 10px',
            background: theme === opt.value ? 'var(--accent)' : 'transparent',
            color: theme === opt.value ? 'white' : 'var(--text)',
            border: 'none',
            cursor: 'pointer',
            fontSize: 13,
            lineHeight: 1,
            transition: 'background 0.15s, color 0.15s',
          }}
        >
          {opt.icon}
        </button>
      ))}
    </div>
  )
}
