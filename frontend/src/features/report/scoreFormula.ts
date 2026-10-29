import { skills, type ReportModel } from './model'

/** Display rounded operands and the recorded overall score without implying exact equality. */
export const formatScoreFormula = (model: ReportModel, score: number | null) =>
  `(${skills.map(skill => model.dimensions[skill.dimension].score?.toFixed(2) ?? '—').join(' + ')}) ÷ 3 ≈ ${score?.toFixed(2) ?? '—'}`
