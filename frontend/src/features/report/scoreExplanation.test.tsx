import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { CredibilityProcess } from '../../components/CredibilityProcess'
import attention from '../../test/fixtures/credibility-attention.json'
import paper005 from '../../test/fixtures/credibility-paper-005.json'
import type { CredibilityCodeChecks, CredibilityReport } from '../../types/credibility'
import { ReportDocument } from './documents'
import { buildModel } from './model'
import { CodeBody, VerdictBody, type Reported } from './widgets'

describe('score explanation', () => {
  it('shows the real Attention score calculation consistently without rounding its inputs to one decimal', () => {
    const assessment = attention as unknown as Reported
    const report = assessment.report
    const before = JSON.stringify(assessment)
    expect(report.overall).toMatchObject({ score: 7.95, category: 'some_concerns' })
    expect(report.dimensions.find(item => item.dimension_id === 'reference_verification')!.score).toBe(9.85)
    const widget = renderToStaticMarkup(<VerdictBody report={report} model={buildModel(report)} />)
    const document = renderToStaticMarkup(<ReportDocument assessment={assessment} modelName="GPT Review Model" />)
    for (const html of [widget, document]) {
      expect(html).toContain('(7.00 + 9.85 + 7.00) ÷ 3 ≈ 7.95')
      expect(html).not.toContain('(7.0 + 9.8 + 7.0) ÷ 3 = 8.0')
    }
    expect(widget).toContain('Trial score 8.0 out of 10.')
    expect(document).toContain('<b>8.0</b>')
    const code = renderToStaticMarkup(<CodeBody report={report} model={buildModel(report)} />)
    expect(code).toContain('Evidence or coverage gap')
    expect(code).toContain('Code trial score 7.0 out of 10, evidence or coverage gap')
    expect(code).not.toContain('fallback score')
    expect(report.checks.code.searches.find(item => item.scope_type === 'appendix')!.outcome).toBe('not_checked')
    expect(code).toContain('Recorded search areas: 3 checked; 3 not checked.')
    expect(code).not.toContain('The paper body and appendix were examined')
    expect(code).not.toContain('could not be accessed')
    expect(JSON.stringify(assessment)).toBe(before)
  })

  it.each<[CredibilityCodeChecks['code_availability'], string]>([
    ['available', 'A public implementation was located.'],
    ['not_found_in_scope', 'No public implementation was located within the checked scope.'],
    ['unable_to_verify', 'Code availability could not be verified.'],
    ['not_applicable', 'Code availability is not applicable to this paper.'],
  ])('preserves code availability %s without inventing checked or inaccessible areas', (availability, text) => {
    const report = structuredClone(paper005.report) as unknown as CredibilityReport
    report.checks.code.code_availability = availability
    report.checks.code.searches.find(item => item.scope_type === 'project_page')!.outcome = 'failed'
    const before = JSON.stringify(report)
    const html = renderToStaticMarkup(<CodeBody report={report} model={buildModel(report)} />)
    expect(html).toContain(text)
    expect(html).toContain('Recorded search areas: 2 checked; 1 failed; 3 not checked.')
    expect(html).not.toContain('could not be accessed')
    expect(html).not.toContain('The paper body and appendix were examined')
    if (availability === 'unable_to_verify' || availability === 'not_applicable') {
      expect(html).not.toContain('No public implementation was located')
    }
    expect(JSON.stringify(report)).toBe(before)
  })

  it('does not infer code absence or inspected sources when the reader stops before checking begins', () => {
    const report = structuredClone(paper005.report) as unknown as CredibilityReport
    const code = report.checks.code
    code.code_availability = 'unable_to_verify'
    code.searches.forEach(search => { search.outcome = 'not_checked' })
    code.repositories = []
    code.discussions = []
    report.execution.checks!.code_check = { status: 'failed', reused: false, elapsed_seconds: 0, stopped_by_user: true, error: { code: 'STOPPED_BY_USER', retryable: true } }
    const html = renderToStaticMarkup(<CodeBody report={report} model={buildModel(report)} />)
    expect(html).toContain('Code availability could not be verified. Recorded search areas: 6 not checked.')
    expect(html).not.toContain('No public implementation was located')
    expect(html).not.toContain('were examined')
    expect(html).not.toContain('could not be accessed')
  })

  it('keeps a completed claim analysis distinct from unresolved evidence in both report views', () => {
    const assessment = paper005 as unknown as Reported
    const report = assessment.report
    expect(report.dimensions.find(item => item.dimension_id === 'claim_evidence'))
      .toMatchObject({ check_status: 'completed', score: 3, score_rule_ids: expect.arrayContaining(['P_C_SCOPE_FALLBACK']) })
    expect(report.checks.claims.items.some(item => item.outcome === 'unable_to_determine')).toBe(true)
    for (const html of [renderToStaticMarkup(<VerdictBody report={report} model={buildModel(report)} />),
      renderToStaticMarkup(<ReportDocument assessment={assessment} modelName="GPT Review Model" />)]) {
      expect(html).toContain('Claim analysis completed with unresolved evidence')
      expect(html).not.toContain('Claim analysis did not complete')
      expect(html).toContain('The code score follows the availability rule and fixed cap.')
    }
  })

  it('still identifies a recorded execution failure without hiding completed checks', () => {
    const report = structuredClone(paper005.report) as unknown as CredibilityReport
    report.execution.checks!.reference_check = { status: 'failed', reused: false, elapsed_seconds: 21, error: { code: 'TimeoutError', retryable: true } }
    report.dimensions.find(item => item.dimension_id === 'reference_verification')!.check_status = 'failed'
    report.overall.calculation.fallback_dimension_ids!.push('reference_verification')
    const html = renderToStaticMarkup(<VerdictBody report={report} model={buildModel(report)} />)
    const timeline = renderToStaticMarkup(<CredibilityProcess report={report} />)
    expect(timeline).toContain('Failed')
    expect(timeline).toContain('21 s')
    expect(timeline).toContain('TimeoutError')
    expect(html).toContain('Reference verification did not complete')
    expect(html).toContain('Claim analysis completed with unresolved evidence')
  })

  it('keeps a partial reference-item average distinct from a numerical fallback in both views', () => {
    const assessment = structuredClone(paper005) as unknown as Reported
    const report = assessment.report
    const references = report.dimensions.find(item => item.dimension_id === 'reference_verification')!
    references.check_status = 'partial'
    references.score = 7.625
    references.score_rule_ids = ['P_R_MATCHED', 'P_R_UNVERIFIED']
    report.overall.calculation.fallback_dimension_ids!.push('reference_verification')
    for (const html of [renderToStaticMarkup(<VerdictBody report={report} model={buildModel(report)} />),
      renderToStaticMarkup(<ReportDocument assessment={assessment} modelName="GPT Review Model" />)]) {
      expect(html).toContain('Reference coverage is incomplete.')
      expect(html).toContain('The reference score averages the recorded reference-item scores.')
      expect(html).not.toContain('the reference score uses the rubric’s fallback rule')
    }
  })

  it('explains a reference numerical fallback only when its recorded rule applies', () => {
    const report = structuredClone(paper005.report) as unknown as CredibilityReport
    const references = report.dimensions.find(item => item.dimension_id === 'reference_verification')!
    references.check_status = 'partial'
    references.score = 3
    references.score_rule_ids = ['P_R_NO_ITEMS_FALLBACK']
    report.overall.calculation.fallback_dimension_ids!.push('reference_verification')
    const html = renderToStaticMarkup(<VerdictBody report={report} model={buildModel(report)} />)
    expect(html).toContain('No reference items were available; the reference score uses the rubric’s fallback rule.')
    expect(html).not.toContain('The reference score averages the recorded reference-item scores.')
  })
})
