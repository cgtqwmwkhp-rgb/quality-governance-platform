import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import {
  CaseCapaActionsPanel,
  CaseCapaHeaderButton,
} from '../CaseCapaActionsPanel'
import type { Action } from '../../../api/client'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: string | { defaultValue?: string; count?: number }) => {
      if (typeof opts === 'string') return opts
      if (opts?.defaultValue) {
        return opts.defaultValue.replace('{{count}}', String(opts.count ?? ''))
      }
      return key
    },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const sampleAction = {
  id: 7,
  title: 'Guard winch cable',
  status: 'open',
  due_date: '2026-08-01',
} as Action

describe('CaseCapaActionsPanel', () => {
  it('lists actions and opens detail on click', () => {
    const onOpen = vi.fn()
    render(
      <CaseCapaActionsPanel
        sourceType="incident"
        actions={[sampleAction]}
        onAdd={vi.fn()}
        onOpen={onOpen}
        testIdPrefix="incident"
      />,
    )
    expect(screen.getByTestId('incident-capa-actions-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('incident-capa-action-7'))
    expect(onOpen).toHaveBeenCalledWith(sampleAction)
  })

  it('shows empty state and Add', () => {
    const onAdd = vi.fn()
    render(
      <CaseCapaActionsPanel
        sourceType="rta"
        actions={[]}
        onAdd={onAdd}
        onOpen={vi.fn()}
        testIdPrefix="rta"
      />,
    )
    expect(screen.getByText(/No actions yet/i)).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('rta-capa-add'))
    expect(onAdd).toHaveBeenCalled()
  })
})

describe('CaseCapaHeaderButton', () => {
  it('opens CAPA when actions exist', () => {
    const onOpenCapa = vi.fn()
    render(
      <CaseCapaHeaderButton
        sourceType="complaint"
        actionsCount={3}
        capaHref="/actions?sourceType=complaint&sourceId=9"
        onAdd={vi.fn()}
        onOpenCapa={onOpenCapa}
        testIdPrefix="complaint"
      />,
    )
    fireEvent.click(screen.getByTestId('complaint-open-capa'))
    expect(onOpenCapa).toHaveBeenCalled()
  })

  it('adds action when none exist', () => {
    const onAdd = vi.fn()
    render(
      <CaseCapaHeaderButton
        sourceType="near_miss"
        actionsCount={0}
        capaHref="/actions?sourceType=near_miss&sourceId=3"
        onAdd={onAdd}
        onOpenCapa={vi.fn()}
        testIdPrefix="near-miss"
      />,
    )
    fireEvent.click(screen.getByTestId('near-miss-add-action'))
    expect(onAdd).toHaveBeenCalled()
  })
})
