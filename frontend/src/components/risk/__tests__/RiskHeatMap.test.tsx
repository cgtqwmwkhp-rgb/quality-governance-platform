import { describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { TooltipProvider } from '../../ui/Tooltip'
import { RiskHeatMap, type HeatMapData, type HeatMapRiskDetail } from '../RiskHeatMap'
import '../../../i18n/i18n'

const sample: HeatMapData = {
  matrix: Array.from({ length: 5 }, (_, row) =>
    Array.from({ length: 5 }, (__, col) => {
      const likelihood = 5 - row
      const impact = col + 1
      const score = likelihood * impact
      const populated = likelihood === 2 && impact === 2
      return {
        likelihood,
        impact,
        score,
        level: score > 16 ? 'critical' : score > 9 ? 'high' : score > 4 ? 'medium' : 'low',
        color: '#22c55e',
        risk_count: populated ? 3 : 0,
        risk_ids: populated ? [1, 2, 3] : [],
        risk_titles: populated ? ['Alpha', 'Beta', 'Gamma'] : [],
        owners_sample: populated ? ['Alice'] : [],
        overdue_count: populated ? 1 : 0,
        outside_appetite_count: populated ? 1 : 0,
        intensity: populated ? 1 : 0,
        above_appetite_band: score > 12,
        movers: [],
      }
    }),
  ),
  summary: {
    total_risks: 3,
    critical_risks: 0,
    high_risks: 0,
    outside_appetite: 1,
    average_inherent_score: 4,
    average_residual_score: 2,
  },
  likelihood_labels: {
    1: 'Rare',
    2: 'Unlikely',
    3: 'Possible',
    4: 'Likely',
    5: 'Almost Certain',
  },
  impact_labels: {
    1: 'Insignificant',
    2: 'Minor',
    3: 'Moderate',
    4: 'Major',
    5: 'Catastrophic',
  },
  appetite_overlay: { threshold: 12, source: 'default' },
}

const riskDetails = new Map<number, HeatMapRiskDetail>([
  [
    1,
    {
      id: 1,
      title: 'Alpha',
      reference: 'RISK-0001',
      created_at: '2024-01-15T00:00:00Z',
      category: 'operational',
      owner: 'Alice',
      inherent_score: 8,
      residual_score: 4,
      status: 'monitoring',
      next_review_date: '2025-06-01',
    },
  ],
  [
    2,
    {
      id: 2,
      title: 'Beta',
      reference: 'RISK-0002',
      category: 'compliance',
      owner: 'Bob',
      inherent_score: 6,
      residual_score: 3,
      status: 'open',
    },
  ],
])

function renderHeatMap(
  props: Partial<ComponentProps<typeof RiskHeatMap>> = {},
) {
  return render(
    <TooltipProvider>
      <RiskHeatMap
        data={sample}
        scoreType="residual"
        focusMode="none"
        selectedCell={null}
        onScoreTypeChange={vi.fn()}
        onFocusModeChange={vi.fn()}
        onCellSelect={vi.fn()}
        onShowInRegister={vi.fn()}
        onClearCellFilter={vi.fn()}
        {...props}
      />
    </TooltipProvider>,
  )
}

describe('RiskHeatMap', () => {
  it('renders matrix and fires cell select', () => {
    const onCellSelect = vi.fn()
    renderHeatMap({ onCellSelect })
    expect(screen.getByTestId('risk-heatmap')).toBeInTheDocument()
    expect(screen.getByTestId('risk-heatmap-summary')).toHaveTextContent('3')
    expect(screen.getByTestId('risk-heatmap-detail-rail')).toBeInTheDocument()
    expect(screen.queryByTestId('risk-heatmap-cell-popup-2-2')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('risk-heatmap-cell-2-2'))
    expect(onCellSelect).toHaveBeenCalled()
  })

  it('shows empty detail rail prompt until a cell is selected', () => {
    renderHeatMap()
    expect(screen.getByTestId('risk-heatmap-detail-empty')).toHaveTextContent(
      'Select a cell to inspect risks',
    )
  })

  it('shows sticky detail rail with rich risk cards when a cell is selected', () => {
    const onOpenRisk = vi.fn()
    renderHeatMap({
      selectedCell: { likelihood: 2, impact: 2 },
      riskDetails,
      onOpenRisk,
    })
    expect(screen.getByTestId('risk-heatmap-detail-header')).toHaveTextContent('Unlikely × Minor')
    expect(screen.getByTestId('risk-heatmap-detail-card-1')).toHaveTextContent('Alpha')
    expect(screen.getByTestId('risk-heatmap-detail-card-1')).toHaveTextContent('RISK-0001')
    expect(screen.getByTestId('risk-heatmap-detail-card-1')).toHaveTextContent('Alice')
    expect(screen.queryByTestId('risk-heatmap-cell-popup-2-2')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('risk-heatmap-detail-open-1'))
    expect(onOpenRisk).toHaveBeenCalledWith(1)
  })

  it('falls back to cell titles when risk details are missing', () => {
    renderHeatMap({
      selectedCell: { likelihood: 2, impact: 2 },
    })
    expect(screen.getByTestId('risk-heatmap-detail-card-3')).toHaveTextContent('Gamma')
  })

  it('detail rail clear and show-in-register actions call handlers', () => {
    const onShowInRegister = vi.fn()
    const onClearCellFilter = vi.fn()
    renderHeatMap({
      selectedCell: { likelihood: 2, impact: 2 },
      onShowInRegister,
      onClearCellFilter,
    })
    fireEvent.click(screen.getByTestId('risk-heatmap-detail-show-register'))
    expect(onShowInRegister).toHaveBeenCalledWith(
      expect.objectContaining({ likelihood: 2, impact: 2, risk_count: 3 }),
    )
    fireEvent.click(screen.getByTestId('risk-heatmap-detail-clear'))
    expect(onClearCellFilter).toHaveBeenCalled()
  })

  it('does not render hover popup on mouse enter', () => {
    renderHeatMap({ selectedCell: null })
    fireEvent.mouseEnter(screen.getByTestId('risk-heatmap-cell-2-2'))
    expect(screen.queryByTestId('risk-heatmap-cell-popup-2-2')).not.toBeInTheDocument()
  })

  it('renders labeled placement and highlight controls', () => {
    renderHeatMap()
    expect(screen.getByText('Place on grid')).toBeInTheDocument()
    expect(screen.getByTestId('risk-heatmap-score-residual')).toHaveTextContent('After controls')
    expect(screen.getByTestId('risk-heatmap-score-inherent')).toHaveTextContent('Before controls')
    expect(screen.getByTestId('risk-heatmap-score-delta')).toHaveTextContent('Movement')
    expect(screen.getByText('Highlight')).toBeInTheDocument()
  })
})
