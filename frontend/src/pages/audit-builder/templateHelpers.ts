import type { AuditTemplate, Section, Question, QuestionType, ScoringMethod } from './types';
import type { AuditQuestionCreate, AuditQuestionUpdate } from '../../api/client';
import { generateId, createNewSection, SECTION_COLORS } from './types';

function mapApiQuestion(q: any, questionIdMap: Record<string, number>): Question {
  const id = String(q.id);
  questionIdMap[id] = q.id;
  return {
    id,
    text: q.question_text,
    description: q.description,
    type: (q.question_type || 'yes_no') as QuestionType,
    required: q.is_required,
    weight: q.weight,
    options: q.options?.map((o: any) => ({
      id: generateId(), label: o.label, value: o.value, score: o.score, isCorrect: o.is_correct,
    })),
    evidenceRequired: false,
    failureTriggersAction: false,
    riskLevel: q.risk_category as Question['riskLevel'],
    guidance: q.help_text,
  };
}

export function mapApiToTemplate(
  data: any,
  sectionIdMap: Record<string, number>,
  questionIdMap: Record<string, number>,
): AuditTemplate {
  const mappedSections: Section[] = data.sections.map((s: any, idx: number) => {
    const id = String(s.id);
    sectionIdMap[id] = s.id;
    return {
      id,
      title: s.title,
      description: s.description,
      questions: s.questions.map((q: any) => mapApiQuestion(q, questionIdMap)),
      isExpanded: true,
      weight: s.weight,
      order: s.sort_order,
      color: SECTION_COLORS[idx % SECTION_COLORS.length],
    };
  });

  return {
    id: String(data.id),
    name: data.name,
    description: data.description || '',
    version: String(data.version),
    status: data.is_published ? 'published' : 'draft',
    category: data.category || 'quality',
    isoStandards: [],
    sections: mappedSections.length > 0 ? mappedSections : [createNewSection(1)],
    scoringMethod: (data.scoring_method || 'weighted') as ScoringMethod,
    passThreshold: data.passing_score || 80,
    createdAt: data.created_at,
    updatedAt: data.updated_at || data.created_at,
    createdBy: 'Current User',
    tags: [],
    estimatedDuration: 60,
    isLocked: false,
  };
}

export function mapAISectionsToLocal(generatedSections: any[], existingSectionCount: number): Section[] {
  return generatedSections.map((gs, idx) => ({
    id: gs.id,
    title: gs.title,
    description: gs.description,
    questions: gs.questions.map((q: any) => ({
      id: q.id,
      text: q.text,
      type: q.type as QuestionType,
      required: q.required,
      weight: q.weight,
      riskLevel: q.riskLevel as Question['riskLevel'],
      evidenceRequired: q.evidenceRequired,
      isoClause: q.isoClause,
      guidance: q.guidance,
      failureTriggersAction: false,
    })),
    isExpanded: true,
    weight: 1,
    order: existingSectionCount + idx,
    color: SECTION_COLORS[(existingSectionCount + idx) % SECTION_COLORS.length],
  }));
}

export function buildQuestionPayload(q: Question, sortOrder: number): AuditQuestionUpdate;
export function buildQuestionPayload(q: Question, sortOrder: number, sectionId: number): AuditQuestionCreate;
export function buildQuestionPayload(q: Question, sortOrder: number, sectionId?: number): AuditQuestionCreate | AuditQuestionUpdate {
  const base = {
    question_text: q.text,
    question_type: q.type,
    description: q.description,
    help_text: q.guidance,
    is_required: q.required,
    weight: q.weight,
    sort_order: sortOrder,
    options: q.options?.length
      ? q.options.map(o => ({ value: o.value, label: o.label, score: o.score, is_correct: o.isCorrect }))
      : undefined,
    risk_category: q.riskLevel,
  };
  if (sectionId !== undefined) return { ...base, section_id: sectionId };
  return base;
}
