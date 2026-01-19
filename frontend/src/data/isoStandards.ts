/**
 * ISO Standards Database
 * Comprehensive clause library for ISO 9001, 14001, 45001 and other standards
 * Used for auto-tagging and compliance evidence mapping
 */

export interface ISOClause {
  id: string;
  standard: string;
  clauseNumber: string;
  title: string;
  description: string;
  keywords: string[];
  parentClause?: string;
  level: number; // 1 = main clause, 2 = sub-clause, 3 = sub-sub-clause
}

export interface ISOStandard {
  id: string;
  code: string;
  name: string;
  version: string;
  description: string;
  icon: string;
  color: string;
  clauses: ISOClause[];
}

// ============================================================================
// ISO 9001:2015 - Quality Management System
// ============================================================================

const ISO_9001_CLAUSES: ISOClause[] = [
  // Clause 4 - Context of the Organization
  { id: '9001-4', standard: 'iso9001', clauseNumber: '4', title: 'Context of the organization', description: 'Understanding the organization and its context', keywords: ['context', 'organization', 'stakeholder', 'scope'], level: 1 },
  { id: '9001-4.1', standard: 'iso9001', clauseNumber: '4.1', title: 'Understanding the organization and its context', description: 'Determine external and internal issues relevant to purpose and strategic direction', keywords: ['internal issues', 'external issues', 'strategic direction', 'context'], parentClause: '9001-4', level: 2 },
  { id: '9001-4.2', standard: 'iso9001', clauseNumber: '4.2', title: 'Understanding the needs and expectations of interested parties', description: 'Determine interested parties and their requirements', keywords: ['interested parties', 'stakeholders', 'requirements', 'needs', 'expectations'], parentClause: '9001-4', level: 2 },
  { id: '9001-4.3', standard: 'iso9001', clauseNumber: '4.3', title: 'Determining the scope of the QMS', description: 'Determine boundaries and applicability of the QMS', keywords: ['scope', 'boundaries', 'applicability', 'QMS'], parentClause: '9001-4', level: 2 },
  { id: '9001-4.4', standard: 'iso9001', clauseNumber: '4.4', title: 'Quality management system and its processes', description: 'Establish, implement, maintain and improve the QMS', keywords: ['processes', 'QMS', 'process approach', 'inputs', 'outputs'], parentClause: '9001-4', level: 2 },

  // Clause 5 - Leadership
  { id: '9001-5', standard: 'iso9001', clauseNumber: '5', title: 'Leadership', description: 'Leadership and commitment', keywords: ['leadership', 'commitment', 'management', 'policy'], level: 1 },
  { id: '9001-5.1', standard: 'iso9001', clauseNumber: '5.1', title: 'Leadership and commitment', description: 'Top management shall demonstrate leadership and commitment', keywords: ['top management', 'leadership', 'commitment', 'accountability'], parentClause: '9001-5', level: 2 },
  { id: '9001-5.1.1', standard: 'iso9001', clauseNumber: '5.1.1', title: 'General', description: 'Leadership commitment to QMS', keywords: ['accountability', 'policy', 'objectives', 'resources'], parentClause: '9001-5.1', level: 3 },
  { id: '9001-5.1.2', standard: 'iso9001', clauseNumber: '5.1.2', title: 'Customer focus', description: 'Customer requirements and satisfaction', keywords: ['customer focus', 'customer satisfaction', 'customer requirements'], parentClause: '9001-5.1', level: 3 },
  { id: '9001-5.2', standard: 'iso9001', clauseNumber: '5.2', title: 'Policy', description: 'Establishing the quality policy', keywords: ['quality policy', 'policy', 'commitment'], parentClause: '9001-5', level: 2 },
  { id: '9001-5.3', standard: 'iso9001', clauseNumber: '5.3', title: 'Organizational roles, responsibilities and authorities', description: 'Assign and communicate roles and responsibilities', keywords: ['roles', 'responsibilities', 'authorities', 'organization chart'], parentClause: '9001-5', level: 2 },

  // Clause 6 - Planning
  { id: '9001-6', standard: 'iso9001', clauseNumber: '6', title: 'Planning', description: 'Planning for the QMS', keywords: ['planning', 'risks', 'opportunities', 'objectives'], level: 1 },
  { id: '9001-6.1', standard: 'iso9001', clauseNumber: '6.1', title: 'Actions to address risks and opportunities', description: 'Determine risks and opportunities and plan actions', keywords: ['risk', 'opportunity', 'risk assessment', 'risk treatment'], parentClause: '9001-6', level: 2 },
  { id: '9001-6.2', standard: 'iso9001', clauseNumber: '6.2', title: 'Quality objectives and planning to achieve them', description: 'Establish quality objectives at relevant functions', keywords: ['quality objectives', 'objectives', 'targets', 'KPIs'], parentClause: '9001-6', level: 2 },
  { id: '9001-6.3', standard: 'iso9001', clauseNumber: '6.3', title: 'Planning of changes', description: 'Changes to QMS shall be carried out in a planned manner', keywords: ['change management', 'change control', 'planning changes'], parentClause: '9001-6', level: 2 },

  // Clause 7 - Support
  { id: '9001-7', standard: 'iso9001', clauseNumber: '7', title: 'Support', description: 'Resources, competence, awareness, communication, documented information', keywords: ['support', 'resources', 'competence', 'training'], level: 1 },
  { id: '9001-7.1', standard: 'iso9001', clauseNumber: '7.1', title: 'Resources', description: 'Determine and provide resources needed', keywords: ['resources', 'infrastructure', 'environment', 'monitoring', 'measuring'], parentClause: '9001-7', level: 2 },
  { id: '9001-7.1.1', standard: 'iso9001', clauseNumber: '7.1.1', title: 'General', description: 'Determine and provide resources', keywords: ['resources', 'capability', 'constraints'], parentClause: '9001-7.1', level: 3 },
  { id: '9001-7.1.2', standard: 'iso9001', clauseNumber: '7.1.2', title: 'People', description: 'Personnel needed for QMS', keywords: ['personnel', 'people', 'staffing', 'human resources'], parentClause: '9001-7.1', level: 3 },
  { id: '9001-7.1.3', standard: 'iso9001', clauseNumber: '7.1.3', title: 'Infrastructure', description: 'Infrastructure needed for operations', keywords: ['infrastructure', 'equipment', 'facilities', 'IT systems'], parentClause: '9001-7.1', level: 3 },
  { id: '9001-7.1.4', standard: 'iso9001', clauseNumber: '7.1.4', title: 'Environment for the operation of processes', description: 'Work environment needed', keywords: ['environment', 'work environment', 'conditions'], parentClause: '9001-7.1', level: 3 },
  { id: '9001-7.1.5', standard: 'iso9001', clauseNumber: '7.1.5', title: 'Monitoring and measuring resources', description: 'Monitoring and measuring equipment', keywords: ['calibration', 'monitoring', 'measuring', 'equipment'], parentClause: '9001-7.1', level: 3 },
  { id: '9001-7.1.6', standard: 'iso9001', clauseNumber: '7.1.6', title: 'Organizational knowledge', description: 'Knowledge needed for processes', keywords: ['knowledge', 'organizational knowledge', 'lessons learned'], parentClause: '9001-7.1', level: 3 },
  { id: '9001-7.2', standard: 'iso9001', clauseNumber: '7.2', title: 'Competence', description: 'Determine competence of persons', keywords: ['competence', 'training', 'skills', 'qualifications', 'education'], parentClause: '9001-7', level: 2 },
  { id: '9001-7.3', standard: 'iso9001', clauseNumber: '7.3', title: 'Awareness', description: 'Persons shall be aware of quality policy and objectives', keywords: ['awareness', 'quality policy', 'contribution'], parentClause: '9001-7', level: 2 },
  { id: '9001-7.4', standard: 'iso9001', clauseNumber: '7.4', title: 'Communication', description: 'Internal and external communications', keywords: ['communication', 'internal communication', 'external communication'], parentClause: '9001-7', level: 2 },
  { id: '9001-7.5', standard: 'iso9001', clauseNumber: '7.5', title: 'Documented information', description: 'Control of documented information', keywords: ['documented information', 'documents', 'records', 'document control'], parentClause: '9001-7', level: 2 },

  // Clause 8 - Operation
  { id: '9001-8', standard: 'iso9001', clauseNumber: '8', title: 'Operation', description: 'Operational planning and control', keywords: ['operation', 'operational', 'process control'], level: 1 },
  { id: '9001-8.1', standard: 'iso9001', clauseNumber: '8.1', title: 'Operational planning and control', description: 'Plan, implement and control processes', keywords: ['operational planning', 'process control', 'criteria'], parentClause: '9001-8', level: 2 },
  { id: '9001-8.2', standard: 'iso9001', clauseNumber: '8.2', title: 'Requirements for products and services', description: 'Determine requirements for products and services', keywords: ['customer requirements', 'product requirements', 'service requirements'], parentClause: '9001-8', level: 2 },
  { id: '9001-8.3', standard: 'iso9001', clauseNumber: '8.3', title: 'Design and development', description: 'Design and development of products and services', keywords: ['design', 'development', 'design review', 'design validation'], parentClause: '9001-8', level: 2 },
  { id: '9001-8.4', standard: 'iso9001', clauseNumber: '8.4', title: 'Control of externally provided processes, products and services', description: 'Control of external providers', keywords: ['suppliers', 'outsourcing', 'external providers', 'purchasing'], parentClause: '9001-8', level: 2 },
  { id: '9001-8.5', standard: 'iso9001', clauseNumber: '8.5', title: 'Production and service provision', description: 'Control of production and service provision', keywords: ['production', 'service provision', 'traceability', 'preservation'], parentClause: '9001-8', level: 2 },
  { id: '9001-8.6', standard: 'iso9001', clauseNumber: '8.6', title: 'Release of products and services', description: 'Verify requirements have been met', keywords: ['release', 'verification', 'inspection', 'testing'], parentClause: '9001-8', level: 2 },
  { id: '9001-8.7', standard: 'iso9001', clauseNumber: '8.7', title: 'Control of nonconforming outputs', description: 'Identify and control nonconforming outputs', keywords: ['nonconformance', 'nonconforming', 'defect', 'reject'], parentClause: '9001-8', level: 2 },

  // Clause 9 - Performance evaluation
  { id: '9001-9', standard: 'iso9001', clauseNumber: '9', title: 'Performance evaluation', description: 'Monitoring, measurement, analysis and evaluation', keywords: ['performance', 'monitoring', 'measurement', 'analysis'], level: 1 },
  { id: '9001-9.1', standard: 'iso9001', clauseNumber: '9.1', title: 'Monitoring, measurement, analysis and evaluation', description: 'Determine what needs to be monitored and measured', keywords: ['monitoring', 'measurement', 'KPIs', 'performance indicators'], parentClause: '9001-9', level: 2 },
  { id: '9001-9.1.2', standard: 'iso9001', clauseNumber: '9.1.2', title: 'Customer satisfaction', description: 'Monitor customer perception', keywords: ['customer satisfaction', 'customer feedback', 'surveys'], parentClause: '9001-9.1', level: 3 },
  { id: '9001-9.2', standard: 'iso9001', clauseNumber: '9.2', title: 'Internal audit', description: 'Conduct internal audits at planned intervals', keywords: ['internal audit', 'audit', 'audit program', 'audit findings'], parentClause: '9001-9', level: 2 },
  { id: '9001-9.3', standard: 'iso9001', clauseNumber: '9.3', title: 'Management review', description: 'Top management shall review the QMS', keywords: ['management review', 'review', 'top management'], parentClause: '9001-9', level: 2 },

  // Clause 10 - Improvement
  { id: '9001-10', standard: 'iso9001', clauseNumber: '10', title: 'Improvement', description: 'Continual improvement', keywords: ['improvement', 'continual improvement', 'corrective action'], level: 1 },
  { id: '9001-10.1', standard: 'iso9001', clauseNumber: '10.1', title: 'General', description: 'Determine opportunities for improvement', keywords: ['improvement opportunities', 'enhancement'], parentClause: '9001-10', level: 2 },
  { id: '9001-10.2', standard: 'iso9001', clauseNumber: '10.2', title: 'Nonconformity and corrective action', description: 'React to nonconformities and take corrective action', keywords: ['nonconformity', 'corrective action', 'root cause', 'CAPA'], parentClause: '9001-10', level: 2 },
  { id: '9001-10.3', standard: 'iso9001', clauseNumber: '10.3', title: 'Continual improvement', description: 'Continually improve the QMS', keywords: ['continual improvement', 'improvement', 'effectiveness'], parentClause: '9001-10', level: 2 },
];

// ============================================================================
// ISO 14001:2015 - Environmental Management System
// ============================================================================

const ISO_14001_CLAUSES: ISOClause[] = [
  // Clause 4 - Context
  { id: '14001-4', standard: 'iso14001', clauseNumber: '4', title: 'Context of the organization', description: 'Understanding the organization and its context', keywords: ['context', 'environmental', 'stakeholders'], level: 1 },
  { id: '14001-4.1', standard: 'iso14001', clauseNumber: '4.1', title: 'Understanding the organization and its context', description: 'Determine environmental conditions affecting the organization', keywords: ['environmental conditions', 'context', 'climate'], parentClause: '14001-4', level: 2 },
  { id: '14001-4.2', standard: 'iso14001', clauseNumber: '4.2', title: 'Understanding needs and expectations of interested parties', description: 'Determine interested parties and their environmental requirements', keywords: ['interested parties', 'environmental requirements', 'compliance obligations'], parentClause: '14001-4', level: 2 },
  { id: '14001-4.3', standard: 'iso14001', clauseNumber: '4.3', title: 'Determining the scope of the EMS', description: 'Determine boundaries of the EMS', keywords: ['scope', 'boundaries', 'EMS'], parentClause: '14001-4', level: 2 },
  { id: '14001-4.4', standard: 'iso14001', clauseNumber: '4.4', title: 'Environmental management system', description: 'Establish, implement, maintain and improve the EMS', keywords: ['EMS', 'environmental management system'], parentClause: '14001-4', level: 2 },

  // Clause 5 - Leadership
  { id: '14001-5', standard: 'iso14001', clauseNumber: '5', title: 'Leadership', description: 'Leadership and commitment', keywords: ['leadership', 'environmental policy', 'commitment'], level: 1 },
  { id: '14001-5.1', standard: 'iso14001', clauseNumber: '5.1', title: 'Leadership and commitment', description: 'Top management commitment to EMS', keywords: ['top management', 'commitment', 'accountability'], parentClause: '14001-5', level: 2 },
  { id: '14001-5.2', standard: 'iso14001', clauseNumber: '5.2', title: 'Environmental policy', description: 'Establish environmental policy', keywords: ['environmental policy', 'pollution prevention', 'compliance'], parentClause: '14001-5', level: 2 },
  { id: '14001-5.3', standard: 'iso14001', clauseNumber: '5.3', title: 'Organizational roles, responsibilities and authorities', description: 'Assign roles and responsibilities for EMS', keywords: ['roles', 'responsibilities', 'authorities'], parentClause: '14001-5', level: 2 },

  // Clause 6 - Planning
  { id: '14001-6', standard: 'iso14001', clauseNumber: '6', title: 'Planning', description: 'Planning for the EMS', keywords: ['planning', 'environmental aspects', 'risks'], level: 1 },
  { id: '14001-6.1', standard: 'iso14001', clauseNumber: '6.1', title: 'Actions to address risks and opportunities', description: 'Determine environmental aspects and compliance obligations', keywords: ['environmental aspects', 'impacts', 'compliance obligations', 'risks'], parentClause: '14001-6', level: 2 },
  { id: '14001-6.1.2', standard: 'iso14001', clauseNumber: '6.1.2', title: 'Environmental aspects', description: 'Identify environmental aspects and significant impacts', keywords: ['aspects', 'impacts', 'significant aspects', 'lifecycle'], parentClause: '14001-6.1', level: 3 },
  { id: '14001-6.1.3', standard: 'iso14001', clauseNumber: '6.1.3', title: 'Compliance obligations', description: 'Identify and access compliance obligations', keywords: ['legal requirements', 'compliance', 'regulations', 'permits'], parentClause: '14001-6.1', level: 3 },
  { id: '14001-6.2', standard: 'iso14001', clauseNumber: '6.2', title: 'Environmental objectives and planning', description: 'Establish environmental objectives', keywords: ['environmental objectives', 'targets', 'programs'], parentClause: '14001-6', level: 2 },

  // Clause 7 - Support
  { id: '14001-7', standard: 'iso14001', clauseNumber: '7', title: 'Support', description: 'Resources, competence, awareness, communication', keywords: ['support', 'resources', 'competence', 'awareness'], level: 1 },
  { id: '14001-7.1', standard: 'iso14001', clauseNumber: '7.1', title: 'Resources', description: 'Provide resources for EMS', keywords: ['resources', 'budget', 'equipment'], parentClause: '14001-7', level: 2 },
  { id: '14001-7.2', standard: 'iso14001', clauseNumber: '7.2', title: 'Competence', description: 'Ensure competence of persons', keywords: ['competence', 'training', 'environmental training'], parentClause: '14001-7', level: 2 },
  { id: '14001-7.3', standard: 'iso14001', clauseNumber: '7.3', title: 'Awareness', description: 'Environmental awareness of persons', keywords: ['awareness', 'environmental policy', 'significant aspects'], parentClause: '14001-7', level: 2 },
  { id: '14001-7.4', standard: 'iso14001', clauseNumber: '7.4', title: 'Communication', description: 'Internal and external environmental communication', keywords: ['communication', 'external communication', 'environmental reporting'], parentClause: '14001-7', level: 2 },
  { id: '14001-7.5', standard: 'iso14001', clauseNumber: '7.5', title: 'Documented information', description: 'Control documented information', keywords: ['documented information', 'records', 'documents'], parentClause: '14001-7', level: 2 },

  // Clause 8 - Operation
  { id: '14001-8', standard: 'iso14001', clauseNumber: '8', title: 'Operation', description: 'Operational planning and control', keywords: ['operation', 'operational control', 'emergency'], level: 1 },
  { id: '14001-8.1', standard: 'iso14001', clauseNumber: '8.1', title: 'Operational planning and control', description: 'Plan and control operations', keywords: ['operational control', 'process control', 'lifecycle'], parentClause: '14001-8', level: 2 },
  { id: '14001-8.2', standard: 'iso14001', clauseNumber: '8.2', title: 'Emergency preparedness and response', description: 'Prepare for and respond to emergencies', keywords: ['emergency', 'emergency response', 'spill', 'incident'], parentClause: '14001-8', level: 2 },

  // Clause 9 - Performance evaluation
  { id: '14001-9', standard: 'iso14001', clauseNumber: '9', title: 'Performance evaluation', description: 'Monitoring, measurement, analysis', keywords: ['performance', 'monitoring', 'compliance evaluation'], level: 1 },
  { id: '14001-9.1', standard: 'iso14001', clauseNumber: '9.1', title: 'Monitoring, measurement, analysis and evaluation', description: 'Monitor environmental performance', keywords: ['monitoring', 'measurement', 'environmental performance'], parentClause: '14001-9', level: 2 },
  { id: '14001-9.1.2', standard: 'iso14001', clauseNumber: '9.1.2', title: 'Evaluation of compliance', description: 'Evaluate compliance with obligations', keywords: ['compliance evaluation', 'legal compliance', 'audit'], parentClause: '14001-9.1', level: 3 },
  { id: '14001-9.2', standard: 'iso14001', clauseNumber: '9.2', title: 'Internal audit', description: 'Conduct internal audits', keywords: ['internal audit', 'EMS audit', 'audit program'], parentClause: '14001-9', level: 2 },
  { id: '14001-9.3', standard: 'iso14001', clauseNumber: '9.3', title: 'Management review', description: 'Top management review of EMS', keywords: ['management review', 'review'], parentClause: '14001-9', level: 2 },

  // Clause 10 - Improvement
  { id: '14001-10', standard: 'iso14001', clauseNumber: '10', title: 'Improvement', description: 'Continual improvement', keywords: ['improvement', 'corrective action', 'continual improvement'], level: 1 },
  { id: '14001-10.2', standard: 'iso14001', clauseNumber: '10.2', title: 'Nonconformity and corrective action', description: 'Address nonconformities', keywords: ['nonconformity', 'corrective action', 'root cause'], parentClause: '14001-10', level: 2 },
  { id: '14001-10.3', standard: 'iso14001', clauseNumber: '10.3', title: 'Continual improvement', description: 'Continually improve environmental performance', keywords: ['continual improvement', 'environmental performance'], parentClause: '14001-10', level: 2 },
];

// ============================================================================
// ISO 45001:2018 - Occupational Health and Safety Management System
// ============================================================================

const ISO_45001_CLAUSES: ISOClause[] = [
  // Clause 4 - Context
  { id: '45001-4', standard: 'iso45001', clauseNumber: '4', title: 'Context of the organization', description: 'Understanding the organization and its context', keywords: ['context', 'OH&S', 'workers'], level: 1 },
  { id: '45001-4.1', standard: 'iso45001', clauseNumber: '4.1', title: 'Understanding the organization and its context', description: 'Determine issues affecting OH&S performance', keywords: ['context', 'issues', 'OH&S'], parentClause: '45001-4', level: 2 },
  { id: '45001-4.2', standard: 'iso45001', clauseNumber: '4.2', title: 'Understanding needs and expectations of workers and interested parties', description: 'Determine interested parties including workers', keywords: ['workers', 'interested parties', 'consultation'], parentClause: '45001-4', level: 2 },
  { id: '45001-4.3', standard: 'iso45001', clauseNumber: '4.3', title: 'Determining the scope of the OH&S management system', description: 'Determine scope of the OHSMS', keywords: ['scope', 'boundaries', 'OHSMS'], parentClause: '45001-4', level: 2 },
  { id: '45001-4.4', standard: 'iso45001', clauseNumber: '4.4', title: 'OH&S management system', description: 'Establish, implement, maintain the OHSMS', keywords: ['OHSMS', 'OH&S management system'], parentClause: '45001-4', level: 2 },

  // Clause 5 - Leadership
  { id: '45001-5', standard: 'iso45001', clauseNumber: '5', title: 'Leadership and worker participation', description: 'Leadership, worker participation', keywords: ['leadership', 'worker participation', 'consultation'], level: 1 },
  { id: '45001-5.1', standard: 'iso45001', clauseNumber: '5.1', title: 'Leadership and commitment', description: 'Top management leadership and commitment', keywords: ['top management', 'leadership', 'commitment', 'accountability'], parentClause: '45001-5', level: 2 },
  { id: '45001-5.2', standard: 'iso45001', clauseNumber: '5.2', title: 'OH&S policy', description: 'Establish OH&S policy', keywords: ['OH&S policy', 'health and safety policy', 'policy'], parentClause: '45001-5', level: 2 },
  { id: '45001-5.3', standard: 'iso45001', clauseNumber: '5.3', title: 'Organizational roles, responsibilities and authorities', description: 'Assign roles and responsibilities', keywords: ['roles', 'responsibilities', 'authorities'], parentClause: '45001-5', level: 2 },
  { id: '45001-5.4', standard: 'iso45001', clauseNumber: '5.4', title: 'Consultation and participation of workers', description: 'Consult and enable worker participation', keywords: ['consultation', 'participation', 'workers', 'safety committee'], parentClause: '45001-5', level: 2 },

  // Clause 6 - Planning
  { id: '45001-6', standard: 'iso45001', clauseNumber: '6', title: 'Planning', description: 'Planning for the OHSMS', keywords: ['planning', 'hazards', 'risks'], level: 1 },
  { id: '45001-6.1', standard: 'iso45001', clauseNumber: '6.1', title: 'Actions to address risks and opportunities', description: 'Determine hazards, risks, opportunities', keywords: ['hazard identification', 'risk assessment', 'opportunities'], parentClause: '45001-6', level: 2 },
  { id: '45001-6.1.2', standard: 'iso45001', clauseNumber: '6.1.2', title: 'Hazard identification and assessment of risks and opportunities', description: 'Identify hazards and assess OH&S risks', keywords: ['hazard identification', 'risk assessment', 'hazards', 'risks'], parentClause: '45001-6.1', level: 3 },
  { id: '45001-6.1.3', standard: 'iso45001', clauseNumber: '6.1.3', title: 'Determination of legal requirements and other requirements', description: 'Determine legal and other requirements', keywords: ['legal requirements', 'compliance', 'regulations', 'legislation'], parentClause: '45001-6.1', level: 3 },
  { id: '45001-6.1.4', standard: 'iso45001', clauseNumber: '6.1.4', title: 'Planning action', description: 'Plan actions to address risks and opportunities', keywords: ['action planning', 'controls', 'hierarchy of controls'], parentClause: '45001-6.1', level: 3 },
  { id: '45001-6.2', standard: 'iso45001', clauseNumber: '6.2', title: 'OH&S objectives and planning to achieve them', description: 'Establish OH&S objectives', keywords: ['OH&S objectives', 'objectives', 'targets', 'safety objectives'], parentClause: '45001-6', level: 2 },

  // Clause 7 - Support
  { id: '45001-7', standard: 'iso45001', clauseNumber: '7', title: 'Support', description: 'Resources, competence, awareness, communication', keywords: ['support', 'resources', 'competence', 'training'], level: 1 },
  { id: '45001-7.1', standard: 'iso45001', clauseNumber: '7.1', title: 'Resources', description: 'Provide resources for OHSMS', keywords: ['resources', 'budget', 'PPE'], parentClause: '45001-7', level: 2 },
  { id: '45001-7.2', standard: 'iso45001', clauseNumber: '7.2', title: 'Competence', description: 'Ensure competence of persons', keywords: ['competence', 'training', 'safety training', 'qualifications'], parentClause: '45001-7', level: 2 },
  { id: '45001-7.3', standard: 'iso45001', clauseNumber: '7.3', title: 'Awareness', description: 'Worker awareness of OH&S', keywords: ['awareness', 'OH&S policy', 'hazards', 'reporting'], parentClause: '45001-7', level: 2 },
  { id: '45001-7.4', standard: 'iso45001', clauseNumber: '7.4', title: 'Communication', description: 'Internal and external OH&S communication', keywords: ['communication', 'safety communication', 'toolbox talks'], parentClause: '45001-7', level: 2 },
  { id: '45001-7.5', standard: 'iso45001', clauseNumber: '7.5', title: 'Documented information', description: 'Control documented information', keywords: ['documented information', 'records', 'safety records'], parentClause: '45001-7', level: 2 },

  // Clause 8 - Operation
  { id: '45001-8', standard: 'iso45001', clauseNumber: '8', title: 'Operation', description: 'Operational planning and control', keywords: ['operation', 'operational control', 'emergency'], level: 1 },
  { id: '45001-8.1', standard: 'iso45001', clauseNumber: '8.1', title: 'Operational planning and control', description: 'Plan and control operations', keywords: ['operational control', 'hierarchy of controls', 'elimination', 'substitution', 'engineering controls', 'PPE'], parentClause: '45001-8', level: 2 },
  { id: '45001-8.1.2', standard: 'iso45001', clauseNumber: '8.1.2', title: 'Eliminating hazards and reducing OH&S risks', description: 'Apply hierarchy of controls', keywords: ['hierarchy of controls', 'elimination', 'substitution', 'engineering', 'administrative', 'PPE'], parentClause: '45001-8.1', level: 3 },
  { id: '45001-8.1.3', standard: 'iso45001', clauseNumber: '8.1.3', title: 'Management of change', description: 'Manage changes affecting OH&S', keywords: ['change management', 'MOC', 'change control'], parentClause: '45001-8.1', level: 3 },
  { id: '45001-8.1.4', standard: 'iso45001', clauseNumber: '8.1.4', title: 'Procurement', description: 'Control procurement of products and services', keywords: ['procurement', 'contractors', 'outsourcing'], parentClause: '45001-8.1', level: 3 },
  { id: '45001-8.2', standard: 'iso45001', clauseNumber: '8.2', title: 'Emergency preparedness and response', description: 'Prepare for and respond to emergencies', keywords: ['emergency', 'emergency response', 'first aid', 'evacuation', 'fire'], parentClause: '45001-8', level: 2 },

  // Clause 9 - Performance evaluation
  { id: '45001-9', standard: 'iso45001', clauseNumber: '9', title: 'Performance evaluation', description: 'Monitoring, measurement, analysis', keywords: ['performance', 'monitoring', 'evaluation'], level: 1 },
  { id: '45001-9.1', standard: 'iso45001', clauseNumber: '9.1', title: 'Monitoring, measurement, analysis and performance evaluation', description: 'Monitor OH&S performance', keywords: ['monitoring', 'measurement', 'OH&S performance', 'lagging indicators', 'leading indicators'], parentClause: '45001-9', level: 2 },
  { id: '45001-9.1.2', standard: 'iso45001', clauseNumber: '9.1.2', title: 'Evaluation of compliance', description: 'Evaluate compliance with legal requirements', keywords: ['compliance evaluation', 'legal compliance'], parentClause: '45001-9.1', level: 3 },
  { id: '45001-9.2', standard: 'iso45001', clauseNumber: '9.2', title: 'Internal audit', description: 'Conduct internal audits', keywords: ['internal audit', 'safety audit', 'audit program'], parentClause: '45001-9', level: 2 },
  { id: '45001-9.3', standard: 'iso45001', clauseNumber: '9.3', title: 'Management review', description: 'Top management review', keywords: ['management review', 'review'], parentClause: '45001-9', level: 2 },

  // Clause 10 - Improvement
  { id: '45001-10', standard: 'iso45001', clauseNumber: '10', title: 'Improvement', description: 'Incident investigation, nonconformity, continual improvement', keywords: ['improvement', 'incident', 'corrective action'], level: 1 },
  { id: '45001-10.2', standard: 'iso45001', clauseNumber: '10.2', title: 'Incident, nonconformity and corrective action', description: 'Investigate incidents and take corrective action', keywords: ['incident investigation', 'accident investigation', 'nonconformity', 'corrective action', 'root cause'], parentClause: '45001-10', level: 2 },
  { id: '45001-10.3', standard: 'iso45001', clauseNumber: '10.3', title: 'Continual improvement', description: 'Continually improve OH&S performance', keywords: ['continual improvement', 'OH&S performance'], parentClause: '45001-10', level: 2 },
];

// ============================================================================
// STANDARDS EXPORT
// ============================================================================

export const ISO_STANDARDS: ISOStandard[] = [
  {
    id: 'iso9001',
    code: 'ISO 9001:2015',
    name: 'Quality Management System',
    version: '2015',
    description: 'Requirements for a quality management system to demonstrate ability to consistently provide products and services that meet customer and regulatory requirements.',
    icon: 'Award',
    color: 'blue',
    clauses: ISO_9001_CLAUSES,
  },
  {
    id: 'iso14001',
    code: 'ISO 14001:2015',
    name: 'Environmental Management System',
    version: '2015',
    description: 'Requirements for an environmental management system to enhance environmental performance, fulfill compliance obligations, and achieve environmental objectives.',
    icon: 'Leaf',
    color: 'green',
    clauses: ISO_14001_CLAUSES,
  },
  {
    id: 'iso45001',
    code: 'ISO 45001:2018',
    name: 'Occupational Health and Safety Management System',
    version: '2018',
    description: 'Requirements for an OH&S management system to prevent work-related injury and ill health to workers and to provide safe and healthy workplaces.',
    icon: 'HardHat',
    color: 'orange',
    clauses: ISO_45001_CLAUSES,
  },
];

// Get all clauses across all standards
export const getAllClauses = (): ISOClause[] => {
  return ISO_STANDARDS.flatMap(s => s.clauses);
};

// Get clauses by standard
export const getClausesByStandard = (standardId: string): ISOClause[] => {
  return ISO_STANDARDS.find(s => s.id === standardId)?.clauses || [];
};

// Search clauses by keyword
export const searchClauses = (query: string): ISOClause[] => {
  const lowerQuery = query.toLowerCase();
  return getAllClauses().filter(clause => 
    clause.title.toLowerCase().includes(lowerQuery) ||
    clause.description.toLowerCase().includes(lowerQuery) ||
    clause.keywords.some(k => k.toLowerCase().includes(lowerQuery)) ||
    clause.clauseNumber.includes(query)
  );
};

// Auto-tag content based on keywords
export const autoTagContent = (content: string): ISOClause[] => {
  const lowerContent = content.toLowerCase();
  const matchedClauses: Map<string, { clause: ISOClause; score: number }> = new Map();

  getAllClauses().forEach(clause => {
    let score = 0;
    
    // Check title match
    if (lowerContent.includes(clause.title.toLowerCase())) {
      score += 10;
    }
    
    // Check keyword matches
    clause.keywords.forEach(keyword => {
      if (lowerContent.includes(keyword.toLowerCase())) {
        score += 5;
      }
    });

    // Check clause number mention
    if (lowerContent.includes(clause.clauseNumber)) {
      score += 15;
    }

    if (score > 0) {
      matchedClauses.set(clause.id, { clause, score });
    }
  });

  // Return clauses sorted by score
  return Array.from(matchedClauses.values())
    .sort((a, b) => b.score - a.score)
    .slice(0, 10)
    .map(m => m.clause);
};
