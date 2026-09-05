import { describe, expect, it } from 'vitest'

import { apply, type Turn } from '@/stores/analyst'

function turn(): Turn {
  return { runId: 1, question: 'q', answer: '', status: 'running', tools: [], error: null }
}

function frame(kind: string, payload: unknown): string {
  return `event: ${kind}\ndata: ${JSON.stringify(payload)}`
}

describe('SSE frames', () => {
  it('appends token deltas in order', () => {
    const t = turn()
    apply(t, frame('text_delta', { text: 'Six ' }))
    apply(t, frame('text_delta', { text: 'open ' }))
    apply(t, frame('text_delta', { text: 'violations.' }))
    expect(t.answer).toBe('Six open violations.')
  })

  it('opens a tool card the moment the tool starts, before it has a result', () => {
    const t = turn()
    apply(t, frame('tool_started', { tool: 'live_li', input: { parcel: 'phl:1' } }))
    expect(t.tools).toHaveLength(1)
    expect(t.tools[0].running).toBe(true)
    expect(t.tools[0].envelope).toBeNull()
  })

  it('fills the card in when the tool finishes', () => {
    const t = turn()
    apply(t, frame('tool_started', { tool: 'live_li', input: {} }))
    apply(
      t,
      frame('tool_finished', {
        tool: 'live_li',
        data: { diff: [] },
        sources: [{ name: 'violations (live)' }],
        unverified: [],
        duration_ms: 700,
      }),
    )
    expect(t.tools[0].running).toBe(false)
    expect(t.tools[0].durationMs).toBe(700)
    expect(t.tools[0].envelope?.sources[0].name).toBe('violations (live)')
  })

  it('matches a finish to the right call when one tool runs twice', () => {
    const t = turn()
    apply(t, frame('tool_started', { tool: 'add_to_pipeline', input: { parcel: 'a' } }))
    apply(t, frame('tool_started', { tool: 'add_to_pipeline', input: { parcel: 'b' } }))
    apply(
      t,
      frame('tool_finished', {
        tool: 'add_to_pipeline',
        data: { parcel_number: 'b' },
        duration_ms: 5,
      }),
    )

    // The newest still-running call is the one that finished; the first stays open.
    expect(t.tools[0].running).toBe(true)
    expect(t.tools[1].running).toBe(false)
    expect(t.tools[1].envelope?.data.parcel_number).toBe('b')
  })

  it('records an error as a failure rather than silence', () => {
    const t = turn()
    apply(t, frame('error', { detail: 'the model refused' }))
    expect(t.status).toBe('failed')
    expect(t.error).toBe('the model refused')
  })

  it('records a cancellation as its own state', () => {
    const t = turn()
    apply(t, frame('cancelled', { reason: 'stopped' }))
    expect(t.status).toBe('cancelled')
  })

  it('ignores a frame it cannot parse rather than corrupting the turn', () => {
    const t = turn()
    t.answer = 'kept'
    apply(t, 'event: text_delta\ndata: {not json')
    apply(t, 'retry: 3000')
    expect(t.answer).toBe('kept')
    expect(t.status).toBe('running')
  })

  it('survives a tool_finished with no matching start', () => {
    const t = turn()
    apply(t, frame('tool_finished', { tool: 'ghost', data: {} }))
    expect(t.tools).toHaveLength(0)
  })
})
