import type { ReactNode } from 'react'
import { Link } from 'react-router'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="bg-aubergine text-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5 rounded-sm font-bold tracking-[-0.2px] focus-visible:outline-white">
            <img src="/favicon.svg" alt="" className="size-7 rounded-md ring-1 ring-aubergine-tint" />
            Resume Reviewer
          </Link>
          <nav aria-label="Main" className="text-sm">
            <Link to="/" className="rounded-sm text-aubergine-mute transition-colors duration-150 hover:text-white focus-visible:outline-white">
              Jobs
            </Link>
          </nav>
          <span className="ml-auto hidden text-xs text-aubergine-mute sm:block">Runs locally · advice only, you decide</span>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
