import type { CredibilityReport } from '../../types/credibility'

/** Explain scoring gaps separately from whether the check finished executing. */
export function scoreExplanations(report: CredibilityReport): string[] {
  const selected = new Set(report.overall.calculation.fallback_dimension_ids ?? [])
  return report.dimensions.filter(dimension => selected.has(dimension.dimension_id)).map(dimension => {
    const completed = dimension.check_status === 'completed'
    if (dimension.dimension_id === 'claim_evidence') {
      return completed
        ? 'Claim analysis completed with unresolved evidence; the claim score uses the rubric’s fallback rule.'
        : 'Claim analysis did not complete; the claim score uses the rubric’s fallback rule.'
    }
    if (dimension.dimension_id === 'reference_verification') {
      if (dimension.score_rule_ids.includes('P_R_NO_ITEMS_FALLBACK')) {
        return 'No reference items were available; the reference score uses the rubric’s fallback rule.'
      }
      const coverage = completed
        ? 'Reference verification completed with unresolved entries.'
        : dimension.check_status === 'partial'
          ? 'Reference coverage is incomplete.'
          : 'Reference verification did not complete.'
      return `${coverage} The reference score averages the recorded reference-item scores.`
    }
    if (dimension.score_rule_ids.includes('P_K_MINIMUM_WITH_CAP')) {
      return `${completed ? 'The code check completed its bounded scope.' : 'Code coverage is incomplete.'} The code score follows the availability rule and fixed cap.`
    }
    return completed
      ? 'The code check completed with unresolved evidence; the code score uses the rubric’s fallback rule.'
      : 'The code check did not complete; the code score uses the rubric’s fallback rule.'
  })
}
