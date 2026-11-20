import { afterEach, describe, expect, it, vi } from 'vitest'
import { systemApi } from '@/services/api'
import { useTask } from './useTask'
import type { TaskOut } from '@/types/api'

const task = (status: TaskOut['status'], extra: Partial<TaskOut> = {}): TaskOut => ({
  id: 1,
  kind: 'x',
  status,
  attempts: 1,
  error: null,
  result: null,
  ...extra,
})

afterEach(() => vi.restoreAllMocks())

describe('useTask', () => {
  it('consulta até terminar e devolve o resultado', async () => {
    vi.spyOn(systemApi, 'task')
      .mockResolvedValueOnce(task('pending'))
      .mockResolvedValueOnce(task('running'))
      .mockResolvedValueOnce(task('done', { result: { score: 80 } }))
    const t = useTask({ intervalMs: 1 })
    const result = await t.wait(1)
    expect(result.result).toEqual({ score: 80 })
    expect(t.running.value).toBe(false)
  })

  it('falha com a mensagem do worker sem o código técnico', async () => {
    vi.spyOn(systemApi, 'task').mockResolvedValue(
      task('failed', { error: 'AI_AUTH: Chave de API inválida ou revogada.' }),
    )
    const err = await useTask({ intervalMs: 1 }).wait(1).catch((e: unknown) => e)
    expect(err).toMatchObject({ code: 'AI_AUTH', message: 'Chave de API inválida ou revogada.' })
  })

  it('desiste após o tempo limite', async () => {
    vi.spyOn(systemApi, 'task').mockResolvedValue(task('pending'))
    const err = await useTask({ intervalMs: 1, timeoutMs: 5 }).wait(1).catch((e: unknown) => e)
    expect(err).toMatchObject({ code: 'TASK_TIMEOUT' })
  })
})
