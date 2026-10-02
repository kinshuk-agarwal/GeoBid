import type { FootfallCategory } from '@/types'

interface CategoryStyle {
  label: string
  /** marker fill */
  color: string
  /** marker outline — a darker shade so yellow stays visible on light tiles */
  stroke: string
  /** Tailwind classes for badges/chips */
  badge: string
  dot: string
}

export const CATEGORY: Record<FootfallCategory, CategoryStyle> = {
  HIGH: {
    label: 'High footfall',
    color: '#dc2626',
    stroke: '#7f1d1d',
    badge: 'bg-high-soft text-red-800 ring-red-200',
    dot: 'bg-high',
  },
  MEDIUM: {
    label: 'Medium footfall',
    color: '#eab308',
    stroke: '#854d0e',
    badge: 'bg-medium-soft text-yellow-900 ring-yellow-300',
    dot: 'bg-medium',
  },
  LOW: {
    label: 'Low footfall',
    color: '#16a34a',
    stroke: '#14532d',
    badge: 'bg-low-soft text-green-800 ring-green-200',
    dot: 'bg-low',
  },
}

export const CATEGORY_ORDER: FootfallCategory[] = ['HIGH', 'MEDIUM', 'LOW']
