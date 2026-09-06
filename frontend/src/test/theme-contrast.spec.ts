import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const SRC = join(process.cwd(), 'src')
const HARDCODED_GREY = /\btext-(?:grey|blue-grey)-\d+\b/g

const NOT_YET_MIGRATED = new Set([
  'components/SensitivityHeatmap.vue',
  'pages/AccountPage.vue',
  'pages/AdminPage.vue',
  'pages/AuthPage.vue',
])

function vueFilesUnder(dir: string): string[] {
  return readdirSync(join(SRC, dir))
    .filter((name) => name.endsWith('.vue'))
    .map((name) => `${dir}/${name}`)
}

function offendingLines(relativePath: string): string[] {
  const lines = readFileSync(join(SRC, relativePath), 'utf8').split('\n')
  return lines.flatMap((line, index) => {
    const hits = line.match(HARDCODED_GREY)
    return hits ? [`${relativePath}:${index + 1} ${hits.join(', ')}`] : []
  })
}

function channel(value: number): number {
  const scaled = value / 255
  return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const digits = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((offset) =>
    channel(Number.parseInt(digits.slice(offset, offset + 2), 16)),
  )
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}

function contrastRatio(foreground: string, background: string): number {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

function tokenValues(scopePattern: RegExp): Record<string, string> {
  const css = readFileSync(join(SRC, 'css/tokens.css'), 'utf8')
  const scope = css.match(scopePattern)?.[1] ?? ''
  const values: Record<string, string> = {}
  for (const [, name, value] of scope.matchAll(/(--lot-[a-z0-9-]+):\s*(#[0-9a-f]{6})/g)) {
    values[name!] = value!
  }
  return values
}

const WCAG_AA_BODY_TEXT = 4.5

describe('dossier text uses theme tokens, not hardcoded Quasar greys', () => {
  const allFiles = [...vueFilesUnder('components'), ...vueFilesUnder('pages')]
  const migrated = allFiles.filter((file) => !NOT_YET_MIGRATED.has(file))

  it.each(migrated)('%s', (file) => {
    expect(offendingLines(file)).toEqual([])
  })

  it('keeps the not-yet-migrated list honest', () => {
    const stale = [...NOT_YET_MIGRATED].filter((file) => offendingLines(file).length === 0)
    expect(stale, 'these files are clean now — remove them from NOT_YET_MIGRATED').toEqual([])
  })
})

describe('text tokens clear WCAG AA against every surface they render on', () => {
  const themes = {
    light: tokenValues(/:root\s*\{([\s\S]*?)\}/),
    dark: tokenValues(/body\.body--dark\s*\{([\s\S]*?)\}/),
  }

  for (const [theme, tokens] of Object.entries(themes)) {
    for (const foreground of ['--lot-ink', '--lot-muted', '--lot-faint']) {
      for (const background of ['--lot-surface', '--lot-surface-2', '--lot-surface-3']) {
        it(`${theme}: ${foreground} on ${background}`, () => {
          const ratio = contrastRatio(tokens[foreground]!, tokens[background]!)
          expect(ratio).toBeGreaterThanOrEqual(WCAG_AA_BODY_TEXT)
        })
      }
    }
  }
})
