import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import IssueList from './IssueList.vue'
import ResumeEditor from './ResumeEditor.vue'
import type { Profile, ResumeContent } from '@/types/api'

const profile: Profile = {
  contact: { name: 'Ana', email: '', phone: '', location: '', links: [] },
  headline: '',
  summary: '',
  availability: '',
  experiences: [
    { id: 'e1', role: 'Estagiária', company: 'X', start: '', end: '', location: '', highlights: ['Fiz A', 'Fiz B'] },
  ],
  education: [],
  skills: [
    { name: 'Python', category: '', level: '' },
    { name: 'Docker', category: '', level: '' },
  ],
  projects: [{ id: 'p1', name: 'Agenda', description: '', url: '', technologies: [] }],
  languages: [],
  certifications: [],
}

const content: ResumeContent = {
  headline: 'Dev',
  summary: 'Resumo',
  skills: ['Python'],
  experiences: [{ id: 'e1', highlights: ['Fiz A'] }],
  project_ids: [],
}

describe('ResumeEditor', () => {
  it('só oferece competências e projetos que existem no perfil', async () => {
    const w = mount(ResumeEditor, { props: { content, profile } })
    const offered = w.findAll('button').map((b) => b.text())
    expect(offered).toContain('+ Docker')
    expect(offered).toContain('+ Agenda')
    expect(offered).not.toContain('+ Python') // já está no currículo

    await w.findAll('button').find((b) => b.text() === '+ Docker')!.trigger('click')
    const value = (w.vm as unknown as { value: () => ResumeContent }).value()
    expect(value.skills).toEqual(['Python', 'Docker'])
  })

  it('itens de experiência são escolhidos do perfil, não digitados', async () => {
    const w = mount(ResumeEditor, { props: { content, profile } })
    const checkB = w.findAll('input[type="checkbox"]').find((i) => i.attributes('id')?.includes('Fiz B'))!
    await checkB.setValue(true)
    const value = (w.vm as unknown as { value: () => ResumeContent }).value()
    expect(value.experiences[0]!.highlights).toEqual(['Fiz A', 'Fiz B'])
    expect(w.findAll('textarea')).toHaveLength(1) // apenas o resumo é texto livre
  })

  it('reordena competências sem alterar o original', async () => {
    const w = mount(ResumeEditor, { props: { content: { ...content, skills: ['Python', 'Docker'] }, profile } })
    await w.find('button[aria-label="Descer Python"]').trigger('click')
    expect((w.vm as unknown as { value: () => ResumeContent }).value().skills).toEqual(['Docker', 'Python'])
    expect(content.skills).toEqual(['Python'])
  })
})

describe('IssueList', () => {
  it('separa erros (bloqueiam) de avisos (revisar)', () => {
    const w = mount(IssueList, {
      props: {
        issues: [
          { severity: 'error', field: 'skills', message: 'Competência “Kubernetes” não existe no seu perfil.' },
          { severity: 'warning', field: 'summary', message: '“AWS” não aparece no seu perfil.' },
        ],
      },
    })
    expect(w.find('[role="alert"]').text()).toContain('Kubernetes')
    expect(w.text()).toContain('Confira antes de enviar')
  })

  it('mostra confirmação quando está tudo certo', () => {
    expect(mount(IssueList, { props: { issues: [] } }).text()).toContain('Tudo confere')
  })
})
