import { getCurrentScope, onScopeDispose, ref } from 'vue'
import { systemApi } from '@/services/api'
import type { TaskOut } from '@/types/api'
import { ApiError } from '@/utils/apiError'

/**
 * Acompanha uma tarefa do worker (análise, geração de PDF, envio...).
 * `wait` resolve com o resultado quando termina, ou rejeita com a mensagem do erro.
 */
export function useTask(options: { intervalMs?: number; timeoutMs?: number } = {}) {
  const { intervalMs = 1500, timeoutMs = 5 * 60_000 } = options
  const running = ref(false)
  const task = ref<TaskOut | null>(null)
  let cancelled = false

  if (getCurrentScope()) onScopeDispose(() => (cancelled = true))

  async function wait(taskId: number): Promise<TaskOut> {
    running.value = true
    cancelled = false
    const started = Date.now()
    try {
      while (!cancelled) {
        const t = await systemApi.task(taskId)
        task.value = t
        if (t.status === 'done') return t
        if (t.status === 'failed') {
          // O worker grava "CÓDIGO: mensagem"; mostramos só a mensagem.
          const [code, ...rest] = (t.error ?? 'TASK_FAILED: A tarefa falhou.').split(': ')
          throw new ApiError({ status: 422, code: code ?? 'TASK_FAILED', message: rest.join(': ') || 'A tarefa falhou.' })
        }
        if (Date.now() - started > timeoutMs) {
          throw new ApiError({ status: 0, code: 'TASK_TIMEOUT', message: 'A tarefa está demorando. Confira o worker.' })
        }
        await new Promise((r) => setTimeout(r, intervalMs))
      }
      throw new ApiError({ status: 0, code: 'CANCELLED', message: 'Cancelado.' })
    } finally {
      running.value = false
    }
  }

  return { running, task, wait }
}
