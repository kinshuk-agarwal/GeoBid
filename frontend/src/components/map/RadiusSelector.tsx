interface Props {
  value: number
  options: number[]
  onChange: (km: number) => void
  className?: string
}

export function RadiusSelector({ value, options, onChange, className = '' }: Props) {
  return (
    <div role="radiogroup" aria-label="Search radius" className={`flex gap-1 rounded-lg bg-slate-100 p-1 ${className}`}>
      {options.map((km) => {
        const active = km === value
        return (
          <button
            key={km}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(km)}
            className={`flex-1 whitespace-nowrap rounded-md px-2.5 py-1 text-sm font-medium transition-colors ${
              active ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {km} km
          </button>
        )
      })}
    </div>
  )
}
