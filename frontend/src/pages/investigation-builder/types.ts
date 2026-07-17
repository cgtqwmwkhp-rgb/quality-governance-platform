import type { QuestionType } from '../audit-builder/types'
import { createInc043ScaffoldSections } from './contractSections'

export type ApplicableEntityType =
  | 'road_traffic_collision'
  | 'reporting_incident'
  | 'complaint'
  | 'near_miss'

export interface InvestigationField {
  id: string
  label: string
  type: QuestionType
  required: boolean
}

export interface InvestigationSection {
  id: string
  name: string
  fields: InvestigationField[]
}

export interface InvestigationTemplateDraft {
  name: string
  description: string
  version: string
  is_active: boolean
  applicable_entity_types: ApplicableEntityType[]
  sections: InvestigationSection[]
}

export const APPLICABLE_ENTITY_TYPES: { value: ApplicableEntityType; label: string }[] = [
  { value: 'near_miss', label: 'Near Miss' },
  { value: 'road_traffic_collision', label: 'Road Traffic Collision' },
  { value: 'complaint', label: 'Complaint' },
  { value: 'reporting_incident', label: 'Incident' },
]

export const generateId = () => Math.random().toString(36).substring(2, 11)

export const createNewField = (): InvestigationField => ({
  id: generateId(),
  label: '',
  type: 'yes_no',
  required: true,
})

export const createNewSection = (order: number): InvestigationSection => ({
  id: generateId(),
  name: `Section ${order}`,
  fields: [],
})

export const createEmptyDraft = (): InvestigationTemplateDraft => ({
  name: '',
  description: '',
  version: '1.0',
  is_active: true,
  applicable_entity_types: ['reporting_incident'],
  sections: createInc043ScaffoldSections(),
})
