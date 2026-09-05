import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, ApiError, apiUrl, currentAuthToken } from '@/lib/api'
import type {
  AnalystEnvelope,
  AnalystOpening,
  ConversationRead,
  ThreadStep,
  ThreadTurn,
} from '@/lib/types'

/** One tool call as the thread shows it: a headline first, the envelope on demand. */
export interface ToolCall {
  name: string
  input: Record<string, unknown> | null
  envelope: AnalystEnvelope | null
  durationMs: number | null
  running: boolean
}

export interface Turn {
  runId: number | null
  question: string
  answer: string
  status: 'running' | 'succeeded' | 'failed' | 'cancelled'
  tools: ToolCall[]
  error: string | null
}

function turnFrom(raw: ThreadTurn): Turn {
  return {
    runId: raw.run_id,
    question: raw.question,
    answer: raw.answer ?? '',
    status: (raw.status as Turn['status']) ?? 'succeeded',
    tools: raw.steps
      .filter((step: ThreadStep) => step.kind === 'tool')
      .map((step) => ({
        name: step.tool_name ?? 'tool',
        input: step.tool_input,
        envelope: step.envelope,
        durationMs: step.duration_ms,
        running: false,
      })),
    error: null,
  }
}

export const useAnalystStore = defineStore('analyst', () => {
  const conversations = ref<ConversationRead[]>([])
  const conversationId = ref<number | null>(null)
  const turns = ref<Turn[]>([])
  const opening = ref<AnalystOpening | null>(null)
  const streaming = ref(false)
  const error = ref<string | null>(null)
  const loadingThread = ref(false)

  let abort: AbortController | null = null

  const current = computed(() => turns.value[turns.value.length - 1] ?? null)

  async function loadConversations(): Promise<void> {
    conversations.value = await api.getConversations()
  }

  async function loadOpening(): Promise<void> {
    try {
      opening.value = await api.getOpening()
    } catch (cause) {
      error.value = cause instanceof ApiError ? cause.message : 'Could not reach the Analyst.'
    }
  }

  async function openConversation(id: number): Promise<void> {
    loadingThread.value = true
    try {
      const thread = await api.getThread(id)
      conversationId.value = thread.conversation_id
      turns.value = thread.turns.map(turnFrom)
    } finally {
      loadingThread.value = false
    }
  }

  function startNew(): void {
    conversationId.value = null
    turns.value = []
    error.value = null
  }

  function cancel(): void {
    abort?.abort()
    abort = null
    streaming.value = false
  }

  /**
   * Send one message and stream the answer.
   *
   * fetch, not EventSource: EventSource cannot carry an Authorization header, and the
   * events endpoint is authenticated like everything else.
   */
  async function send(text: string): Promise<void> {
    const question = text.trim()
    if (!question || streaming.value) return

    error.value = null
    const turn: Turn = {
      runId: null,
      question,
      answer: '',
      status: 'running',
      tools: [],
      error: null,
    }
    turns.value = [...turns.value, turn]
    streaming.value = true

    try {
      const started = await api.sendMessage(question, conversationId.value)
      turn.runId = started.run_id
      conversationId.value = started.conversation_id

      abort = new AbortController()
      const token = currentAuthToken()
      const response = await fetch(apiUrl(started.events_url), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: abort.signal,
      })
      if (!response.ok || response.body === null) {
        throw new Error(`The Analyst stream did not open (${response.status}).`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE frames are separated by a blank line; anything after the last one is partial.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''
        for (const frame of frames) apply(turn, frame)
      }
      if (turn.status === 'running') turn.status = 'succeeded'
    } catch (cause) {
      if ((cause as Error).name === 'AbortError') {
        turn.status = 'cancelled'
      } else {
        turn.status = 'failed'
        turn.error = cause instanceof Error ? cause.message : 'The Analyst stopped unexpectedly.'
        error.value = turn.error
      }
    } finally {
      streaming.value = false
      abort = null
      void loadConversations()
    }
  }

  return {
    conversations,
    conversationId,
    turns,
    current,
    opening,
    streaming,
    loadingThread,
    error,
    loadConversations,
    loadOpening,
    openConversation,
    startNew,
    send,
    cancel,
  }
})

/** Parse one SSE frame into the turn. Exported so a test can drive it without a network. */
export function apply(turn: Turn, frame: string): void {
  const lines = frame.split('\n')
  const kindLine = lines.find((line) => line.startsWith('event: '))
  const dataLine = lines.find((line) => line.startsWith('data: '))
  if (!kindLine) return
  const kind = kindLine.slice(7).trim()
  let payload: Record<string, unknown> = {}
  if (dataLine) {
    try {
      payload = JSON.parse(dataLine.slice(6)) as Record<string, unknown>
    } catch {
      return
    }
  }

  if (kind === 'text_delta') {
    turn.answer += String(payload.text ?? '')
    return
  }
  if (kind === 'tool_started') {
    turn.tools.push({
      name: String(payload.tool ?? 'tool'),
      input: (payload.input as Record<string, unknown>) ?? null,
      envelope: null,
      durationMs: null,
      running: true,
    })
    return
  }
  if (kind === 'tool_finished') {
    // Match the newest still-running call of that name: a turn can call one tool twice.
    const name = String(payload.tool ?? '')
    for (let i = turn.tools.length - 1; i >= 0; i -= 1) {
      const call = turn.tools[i]
      if (call.name === name && call.running) {
        call.running = false
        call.durationMs = (payload.duration_ms as number) ?? null
        call.envelope = {
          data: (payload.data as Record<string, unknown>) ?? {},
          sources: (payload.sources as AnalystEnvelope['sources']) ?? [],
          unverified: (payload.unverified as string[]) ?? [],
        }
        return
      }
    }
    return
  }
  if (kind === 'error') {
    turn.status = 'failed'
    turn.error = String(payload.detail ?? 'The Analyst hit an error.')
    return
  }
  if (kind === 'cancelled') {
    turn.status = 'cancelled'
  }
}
