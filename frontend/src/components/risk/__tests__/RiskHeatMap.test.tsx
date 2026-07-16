import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TooltipProvider } from '../../ui/Tooltip'
import { RiskHeatMap, type HeatMapData } from '../RiskHeatMap'

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

describe('RiskHeatMap', () => {
  it('renders matrix and fires cell select', () => {
    const onCellSelect = vi.fn()
    render(
      <TooltipProvider>
        <RiskHeatMap
          data={sample}
          scoreType="residual"
          focusMode="none"
          selectedCell={null}
          onScoreTypeChange={vi.fn()}
          onFocusModeChange={vi.fn()}
          onCellSelect={onCellSelect}
          onShowInRegister={vi.fn()}
          onClearCellFilter={vi.fn()}
        />
      </TooltipProvider>,
    )
    expect(screen.getByTestId('risk-heatmap')).toBeInTheDocument()
    expect(screen.getByTestId('risk-heatmap-summary')).toHaveTextContent('3')
    expect(screen.queryByTestId('risk-heatmap-cell-sheet')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('risk-heatmap-cell-2-2'))
    expect(onCellSelect).toHaveBeenCalled()
  })

  it('shows interactive cell popup with selectable risks on hover', () => {
    const onOpenRisk = vi.fn()
    render(
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
          onOpenRisk={onOpenRisk}
        />
      </TooltipProvider>,
    )
    fireEvent.mouseEnter(screen.getByTestId('risk-heatmap-cell-2-2').parentElement!)
    expect(screen.getByTestId('risk-heatmap-cell-popup-2-2')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('risk-heatmap-popup-risk-1'))
    expect(onOpenRisk).toHaveBeenCalledWith(1)
  })

  it('renders labeled placement and highlight controls', () => {
    render(
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
        />
      </TooltipProvider>,
    )
    expect(screen.getByText('Place on grid')).toBeInTheDocument()
    expect(screen.getByTestId('risk-heatmap-score-residual')).toHaveTextContent('After controls')
    expect(screen.getByTestId('risk-heatmap-score-inherent')).toHaveTextContent('Before controls')
    expect(screen.getByTestId('risk-heatmap-score-delta')).toHaveTextContent('Movement')
    expect(screen.getByText('Highlight')).toBeInTheDocument()
  })
})
