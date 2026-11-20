import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import type { Component } from 'vue'
import { BriefcaseBusiness, KanbanSquare, LayoutDashboard, Settings, Target, UserRound } from 'lucide-vue-next'
import AppLayout from '@/layouts/AppLayout.vue'
import { authApi } from '@/services/api'
import { setUnauthorizedHandler } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    public?: boolean
  }
}

export interface NavItem {
  label: string
  to: string
  icon: Component
}

export const navigation: NavItem[] = [
  { label: 'Painel', to: '/', icon: LayoutDashboard },
  { label: 'Vagas', to: '/vagas', icon: BriefcaseBusiness },
  { label: 'Candidaturas', to: '/candidaturas', icon: KanbanSquare },
  { label: 'Perfil', to: '/perfil', icon: UserRound },
  { label: 'Perfis-alvo', to: '/perfis-alvo', icon: Target },
  { label: 'Configurações', to: '/configuracoes', icon: Settings },
]

export const routes: RouteRecordRaw[] = [
  {
    path: '/configurar',
    name: 'setup',
    component: () => import('@/pages/SetupPage.vue'),
    meta: { title: 'Primeiro acesso', public: true },
  },
  {
    path: '/entrar',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { title: 'Entrar', public: true },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'dashboard', component: () => import('@/pages/DashboardPage.vue'), meta: { title: 'Painel' } },
      { path: 'vagas', name: 'jobs', component: () => import('@/pages/JobsPage.vue'), meta: { title: 'Vagas' } },
      {
        path: 'vagas/:id(\\d+)',
        name: 'job',
        component: () => import('@/pages/JobDetailPage.vue'),
        meta: { title: 'Vaga' },
      },
      {
        path: 'candidaturas',
        name: 'applications',
        component: () => import('@/pages/ApplicationsPage.vue'),
        meta: { title: 'Candidaturas' },
      },
      { path: 'perfil', name: 'profile', component: () => import('@/pages/ProfilePage.vue'), meta: { title: 'Perfil' } },
      {
        path: 'perfis-alvo',
        name: 'roles',
        component: () => import('@/pages/TargetRolesPage.vue'),
        meta: { title: 'Perfis-alvo' },
      },
      {
        path: 'configuracoes',
        name: 'settings',
        component: () => import('@/pages/SettingsPage.vue'),
        meta: { title: 'Configurações' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { title: 'Página não encontrada', public: true },
  },
]

export const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

let setupChecked = false

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // Instância nova: antes de tudo, cria a conta do dono.
  if (!setupChecked) {
    try {
      const { needs_owner } = await authApi.setupStatus()
      setupChecked = !needs_owner
      if (needs_owner) return to.name === 'setup' ? true : { name: 'setup' }
    } catch {
      return true // API fora: deixa a página mostrar o erro
    }
  }
  if (to.name === 'setup') return { name: 'login' }

  if (!auth.checked) await auth.load()
  if (!to.meta.public && !auth.user) return { name: 'login', query: { next: to.fullPath } }
  if (to.name === 'login' && auth.user) return { name: 'dashboard' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · Candidaturas` : 'Candidaturas'
})

setUnauthorizedHandler(() => {
  useAuthStore().clear()
  const current = router.currentRoute.value
  if (!current.meta.public) router.push({ name: 'login', query: { next: current.fullPath } })
})

export function markSetupDone() {
  setupChecked = true
}
