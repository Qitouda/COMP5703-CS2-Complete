import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import paper005 from '../test/fixtures/credibility-paper-005.json'
import type { CredibilityAssessment, CredibilityReport } from '../types/credibility'
import { duration } from '../constants/credibility'
import { CredibilityProcess } from './CredibilityProcess'

const report = (value: unknown) => (value as CredibilityAssessment).report as CredibilityReport

describe('CredibilityProcess', () => {
  it('draws the fresh GPT check durations and partial code coverage', () => {
    render(<CredibilityProcess report={report(paper005)} />)
    const lanes = within(screen.getByRole('list', { name: 'Check timeline' })).getAllByRole('listitem')
    expect(lanes.map(lane => lane.textContent)).toEqual([
      'Claims & evidenceCompleted · 1 min 02 s',
      'ReferencesCompleted · 2 min 23 s',
      'Code & reproductionPartial · 1 min 43 s',
    ])
    expect(screen.getByText('Code search agent').nextSibling).toHaveTextContent('3×')
    expect(screen.getByText('"The Expressive Power of Transformers with Chain of Thought" site:github.com', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Tool calls').nextSibling).toHaveTextContent('7 / 10')
    expect(screen.getByText(/20 candidate links · 0 verified · 1 rejected/)).toBeInTheDocument()
  })

  it('counts references the agent verified and why the rest stayed unresolved', () => {
    render(<CredibilityProcess report={report(paper005)} />)
    expect(screen.getByText('Of those, found by the reference agent').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Unresolved · personal communication').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Reference agent: search for sources').nextSibling).toHaveTextContent('3×')
    expect(screen.getByText(/16 registered URLs remain unread/)).toBeInTheDocument()
  })

  it('formats durations for people', () => {
    expect([duration(0.2), duration(65.77), duration(119.6), duration(1317.5)]).toEqual(['1 s', '1 min 06 s', '2 min 00 s', '21 min 58 s'])
  })
})
