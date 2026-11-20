import axios, { type AxiosInstance } from 'axios'
import { toApiError } from '@/utils/apiError'

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** Registrado pelo router: sessão expirada leva para o login. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  onUnauthorized = handler
}

/**
 * Cliente único da API.
 * - mesma origem (/api): o Nginx em produção e o Vite em desenvolvimento fazem o proxy
 * - X-Requested-With: exigido pelo backend em toda escrita (proteção CSRF da sessão em cookie)
 */
export function createHttpClient(baseURL = '/api'): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout: 60_000,
    withCredentials: true,
    headers: { Accept: 'application/json', 'X-Requested-With': 'candidaturas' },
  })
  client.interceptors.response.use(
    (res) => res,
    (err: unknown) => {
      const apiErr = toApiError(err)
      if (apiErr.code === 'NOT_AUTHENTICATED') onUnauthorized?.()
      return Promise.reject(apiErr)
    },
  )
  return client
}

export const http = createHttpClient()
