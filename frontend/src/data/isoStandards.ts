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
// ISO 27001:2022 - Information Security Management System
// ============================================================================

const ISO_27001_CLAUSES: ISOClause[] = [
  // Clause 4 - Context
  { id: '27001-4', standard: 'iso27001', clauseNumber: '4', title: 'Context of the organization', description: 'Understanding the organization and its context for information security', keywords: ['context', 'information security', 'stakeholders', 'scope'], level: 1 },
  { id: '27001-4.1', standard: 'iso27001', clauseNumber: '4.1', title: 'Understanding the organization and its context', description: 'Determine external and internal issues relevant to information security', keywords: ['context', 'internal issues', 'external issues', 'information security'], parentClause: '27001-4', level: 2 },
  { id: '27001-4.2', standard: 'iso27001', clauseNumber: '4.2', title: 'Understanding the needs and expectations of interested parties', description: 'Determine interested parties and their information security requirements', keywords: ['interested parties', 'stakeholders', 'requirements', 'information security'], parentClause: '27001-4', level: 2 },
  { id: '27001-4.3', standard: 'iso27001', clauseNumber: '4.3', title: 'Determining the scope of the ISMS', description: 'Determine boundaries and applicability of the ISMS', keywords: ['scope', 'boundaries', 'ISMS', 'information security'], parentClause: '27001-4', level: 2 },
  { id: '27001-4.4', standard: 'iso27001', clauseNumber: '4.4', title: 'Information security management system', description: 'Establish, implement, maintain and continually improve the ISMS', keywords: ['ISMS', 'information security management system', 'establish', 'implement'], parentClause: '27001-4', level: 2 },

  // Clause 5 - Leadership
  { id: '27001-5', standard: 'iso27001', clauseNumber: '5', title: 'Leadership', description: 'Leadership and commitment for information security', keywords: ['leadership', 'commitment', 'policy', 'top management'], level: 1 },
  { id: '27001-5.1', standard: 'iso27001', clauseNumber: '5.1', title: 'Leadership and commitment', description: 'Top management shall demonstrate leadership and commitment to the ISMS', keywords: ['top management', 'leadership', 'commitment', 'accountability', 'resources'], parentClause: '27001-5', level: 2 },
  { id: '27001-5.2', standard: 'iso27001', clauseNumber: '5.2', title: 'Policy', description: 'Establish information security policy', keywords: ['information security policy', 'policy', 'objectives', 'commitment'], parentClause: '27001-5', level: 2 },
  { id: '27001-5.3', standard: 'iso27001', clauseNumber: '5.3', title: 'Organizational roles, responsibilities and authorities', description: 'Assign and communicate roles and responsibilities for information security', keywords: ['roles', 'responsibilities', 'authorities', 'CISO', 'information security manager'], parentClause: '27001-5', level: 2 },

  // Clause 6 - Planning
  { id: '27001-6', standard: 'iso27001', clauseNumber: '6', title: 'Planning', description: 'Planning for the ISMS', keywords: ['planning', 'risk assessment', 'risk treatment', 'objectives'], level: 1 },
  { id: '27001-6.1', standard: 'iso27001', clauseNumber: '6.1', title: 'Actions to address risks and opportunities', description: 'Determine risks and opportunities and plan actions', keywords: ['risk assessment', 'risk treatment', 'opportunities', 'information security risk'], parentClause: '27001-6', level: 2 },
  { id: '27001-6.1.1', standard: 'iso27001', clauseNumber: '6.1.1', title: 'General', description: 'Consider issues and requirements when planning the ISMS', keywords: ['planning', 'issues', 'requirements'], parentClause: '27001-6.1', level: 3 },
  { id: '27001-6.1.2', standard: 'iso27001', clauseNumber: '6.1.2', title: 'Information security risk assessment', description: 'Define and apply information security risk assessment process', keywords: ['risk assessment', 'risk criteria', 'risk analysis', 'risk evaluation', 'CIA', 'confidentiality', 'integrity', 'availability'], parentClause: '27001-6.1', level: 3 },
  { id: '27001-6.1.3', standard: 'iso27001', clauseNumber: '6.1.3', title: 'Information security risk treatment', description: 'Define and apply risk treatment process', keywords: ['risk treatment', 'risk treatment plan', 'statement of applicability', 'SoA', 'controls', 'Annex A'], parentClause: '27001-6.1', level: 3 },
  { id: '27001-6.2', standard: 'iso27001', clauseNumber: '6.2', title: 'Information security objectives and planning to achieve them', description: 'Establish information security objectives', keywords: ['information security objectives', 'objectives', 'targets', 'KPIs', 'measurable'], parentClause: '27001-6', level: 2 },
  { id: '27001-6.3', standard: 'iso27001', clauseNumber: '6.3', title: 'Planning of changes', description: 'Changes to ISMS shall be carried out in a planned manner', keywords: ['change management', 'planning changes', 'ISMS changes'], parentClause: '27001-6', level: 2 },

  // Clause 7 - Support
  { id: '27001-7', standard: 'iso27001', clauseNumber: '7', title: 'Support', description: 'Resources, competence, awareness, communication, documented information', keywords: ['support', 'resources', 'competence', 'awareness', 'training'], level: 1 },
  { id: '27001-7.1', standard: 'iso27001', clauseNumber: '7.1', title: 'Resources', description: 'Determine and provide resources for ISMS', keywords: ['resources', 'budget', 'personnel', 'infrastructure'], parentClause: '27001-7', level: 2 },
  { id: '27001-7.2', standard: 'iso27001', clauseNumber: '7.2', title: 'Competence', description: 'Determine competence of persons affecting information security', keywords: ['competence', 'training', 'security training', 'qualifications', 'skills'], parentClause: '27001-7', level: 2 },
  { id: '27001-7.3', standard: 'iso27001', clauseNumber: '7.3', title: 'Awareness', description: 'Persons shall be aware of information security policy', keywords: ['awareness', 'security awareness', 'policy awareness', 'phishing awareness'], parentClause: '27001-7', level: 2 },
  { id: '27001-7.4', standard: 'iso27001', clauseNumber: '7.4', title: 'Communication', description: 'Determine internal and external communications for ISMS', keywords: ['communication', 'internal communication', 'external communication', 'security communication'], parentClause: '27001-7', level: 2 },
  { id: '27001-7.5', standard: 'iso27001', clauseNumber: '7.5', title: 'Documented information', description: 'ISMS shall include required documented information', keywords: ['documented information', 'documents', 'records', 'document control', 'information classification'], parentClause: '27001-7', level: 2 },

  // Clause 8 - Operation
  { id: '27001-8', standard: 'iso27001', clauseNumber: '8', title: 'Operation', description: 'Operational planning and control', keywords: ['operation', 'operational', 'risk assessment', 'risk treatment'], level: 1 },
  { id: '27001-8.1', standard: 'iso27001', clauseNumber: '8.1', title: 'Operational planning and control', description: 'Plan, implement and control processes for ISMS', keywords: ['operational planning', 'process control', 'outsourced processes'], parentClause: '27001-8', level: 2 },
  { id: '27001-8.2', standard: 'iso27001', clauseNumber: '8.2', title: 'Information security risk assessment', description: 'Perform risk assessments at planned intervals', keywords: ['risk assessment', 'periodic assessment', 'risk reassessment'], parentClause: '27001-8', level: 2 },
  { id: '27001-8.3', standard: 'iso27001', clauseNumber: '8.3', title: 'Information security risk treatment', description: 'Implement risk treatment plan', keywords: ['risk treatment', 'risk treatment implementation', 'controls implementation'], parentClause: '27001-8', level: 2 },

  // Clause 9 - Performance evaluation
  { id: '27001-9', standard: 'iso27001', clauseNumber: '9', title: 'Performance evaluation', description: 'Monitoring, measurement, analysis and evaluation', keywords: ['performance', 'monitoring', 'measurement', 'audit', 'review'], level: 1 },
  { id: '27001-9.1', standard: 'iso27001', clauseNumber: '9.1', title: 'Monitoring, measurement, analysis and evaluation', description: 'Determine what needs to be monitored and measured', keywords: ['monitoring', 'measurement', 'security metrics', 'KPIs', 'effectiveness'], parentClause: '27001-9', level: 2 },
  { id: '27001-9.2', standard: 'iso27001', clauseNumber: '9.2', title: 'Internal audit', description: 'Conduct internal audits at planned intervals', keywords: ['internal audit', 'ISMS audit', 'audit program', 'audit findings', 'security audit'], parentClause: '27001-9', level: 2 },
  { id: '27001-9.3', standard: 'iso27001', clauseNumber: '9.3', title: 'Management review', description: 'Top management shall review the ISMS', keywords: ['management review', 'review', 'top management', 'ISMS review'], parentClause: '27001-9', level: 2 },

  // Clause 10 - Improvement
  { id: '27001-10', standard: 'iso27001', clauseNumber: '10', title: 'Improvement', description: 'Nonconformity, corrective action, continual improvement', keywords: ['improvement', 'corrective action', 'continual improvement', 'nonconformity'], level: 1 },
  { id: '27001-10.1', standard: 'iso27001', clauseNumber: '10.1', title: 'Continual improvement', description: 'Continually improve the ISMS', keywords: ['continual improvement', 'improvement', 'ISMS effectiveness'], parentClause: '27001-10', level: 2 },
  { id: '27001-10.2', standard: 'iso27001', clauseNumber: '10.2', title: 'Nonconformity and corrective action', description: 'React to nonconformities and take corrective action', keywords: ['nonconformity', 'corrective action', 'root cause', 'security incident', 'breach'], parentClause: '27001-10', level: 2 },

  // Annex A Controls (2022 version - 4 themes, 93 controls)
  // A.5 Organizational controls
  { id: '27001-A.5', standard: 'iso27001', clauseNumber: 'A.5', title: 'Organizational controls', description: 'Annex A - Organizational controls (37 controls)', keywords: ['organizational controls', 'Annex A', 'policies', 'roles', 'responsibilities'], level: 1 },
  { id: '27001-A.5.1', standard: 'iso27001', clauseNumber: 'A.5.1', title: 'Policies for information security', description: 'Information security policy and topic-specific policies', keywords: ['information security policy', 'policies', 'policy framework'], parentClause: '27001-A.5', level: 2 },
  { id: '27001-A.5.2', standard: 'iso27001', clauseNumber: 'A.5.2', title: 'Information security roles and responsibilities', description: 'Define and allocate information security responsibilities', keywords: ['roles', 'responsibilities', 'CISO', 'security roles'], parentClause: '27001-A.5', level: 2 },
  { id: '27001-A.5.7', standard: 'iso27001', clauseNumber: 'A.5.7', title: 'Threat intelligence', description: 'Information about threats shall be collected and analyzed', keywords: ['threat intelligence', 'threat analysis', 'cyber threats', 'vulnerability intelligence'], parentClause: '27001-A.5', level: 2 },
  { id: '27001-A.5.23', standard: 'iso27001', clauseNumber: 'A.5.23', title: 'Information security for use of cloud services', description: 'Processes for cloud service acquisition, use and management', keywords: ['cloud security', 'cloud services', 'SaaS', 'IaaS', 'PaaS'], parentClause: '27001-A.5', level: 2 },
  { id: '27001-A.5.24', standard: 'iso27001', clauseNumber: 'A.5.24', title: 'Information security incident management planning', description: 'Plan and prepare for information security incidents', keywords: ['incident management', 'incident response', 'incident planning', 'security incident'], parentClause: '27001-A.5', level: 2 },

  // A.6 People controls
  { id: '27001-A.6', standard: 'iso27001', clauseNumber: 'A.6', title: 'People controls', description: 'Annex A - People controls (8 controls)', keywords: ['people controls', 'Annex A', 'HR security', 'screening', 'awareness'], level: 1 },
  { id: '27001-A.6.1', standard: 'iso27001', clauseNumber: 'A.6.1', title: 'Screening', description: 'Background verification checks on candidates', keywords: ['screening', 'background check', 'vetting', 'pre-employment'], parentClause: '27001-A.6', level: 2 },
  { id: '27001-A.6.3', standard: 'iso27001', clauseNumber: 'A.6.3', title: 'Information security awareness, education and training', description: 'Awareness program and relevant training', keywords: ['awareness training', 'security training', 'education', 'phishing training'], parentClause: '27001-A.6', level: 2 },

  // A.7 Physical controls
  { id: '27001-A.7', standard: 'iso27001', clauseNumber: 'A.7', title: 'Physical controls', description: 'Annex A - Physical controls (14 controls)', keywords: ['physical controls', 'Annex A', 'physical security', 'access control', 'environmental'], level: 1 },
  { id: '27001-A.7.1', standard: 'iso27001', clauseNumber: 'A.7.1', title: 'Physical security perimeters', description: 'Security perimeters to protect areas with information', keywords: ['physical perimeter', 'secure areas', 'data center', 'server room'], parentClause: '27001-A.7', level: 2 },
  { id: '27001-A.7.4', standard: 'iso27001', clauseNumber: 'A.7.4', title: 'Physical security monitoring', description: 'Premises shall be continuously monitored for unauthorized access', keywords: ['CCTV', 'monitoring', 'surveillance', 'intrusion detection'], parentClause: '27001-A.7', level: 2 },

  // A.8 Technological controls
  { id: '27001-A.8', standard: 'iso27001', clauseNumber: 'A.8', title: 'Technological controls', description: 'Annex A - Technological controls (34 controls)', keywords: ['technological controls', 'Annex A', 'technical controls', 'encryption', 'access control'], level: 1 },
  { id: '27001-A.8.1', standard: 'iso27001', clauseNumber: 'A.8.1', title: 'User endpoint devices', description: 'Information on endpoint devices shall be protected', keywords: ['endpoint security', 'laptops', 'mobile devices', 'BYOD', 'MDM'], parentClause: '27001-A.8', level: 2 },
  { id: '27001-A.8.5', standard: 'iso27001', clauseNumber: 'A.8.5', title: 'Secure authentication', description: 'Secure authentication technologies and procedures', keywords: ['authentication', 'MFA', 'multi-factor', 'passwords', 'SSO'], parentClause: '27001-A.8', level: 2 },
  { id: '27001-A.8.7', standard: 'iso27001', clauseNumber: 'A.8.7', title: 'Protection against malware', description: 'Protection against malware shall be implemented', keywords: ['malware', 'antivirus', 'anti-malware', 'ransomware', 'virus'], parentClause: '27001-A.8', level: 2 },
  { id: '27001-A.8.12', standard: 'iso27001', clauseNumber: 'A.8.12', title: 'Data leakage prevention', description: 'Data leakage prevention measures shall be applied', keywords: ['DLP', 'data leakage', 'data loss prevention', 'exfiltration'], parentClause: '27001-A.8', level: 2 },
  { id: '27001-A.8.15', standard: 'iso27001', clauseNumber: 'A.8.15', title: 'Logging', description: 'Logs recording activities, exceptions, faults shall be produced', keywords: ['logging', 'audit logs', 'security logs', 'SIEM'], parentClause: '27001-A.8', level: 2 },
  { id: '27001-A.8.24', standard: 'iso27001', clauseNumber: 'A.8.24', title: 'Use of cryptography', description: 'Rules for effective use of cryptography shall be defined', keywords: ['cryptography', 'encryption', 'key management', 'TLS', 'PKI'], parentClause: '27001-A.8', level: 2 },
  { id: '27001-A.8.28', standard: 'iso27001', clauseNumber: 'A.8.28', title: 'Secure coding', description: 'Secure coding principles shall be applied', keywords: ['secure coding', 'OWASP', 'code review', 'SAST', 'DAST', 'secure development'], parentClause: '27001-A.8', level: 2 },
];

// ============================================================================
// Planet Mark Carbon Certification - Sustainability Standard
// ============================================================================

const PLANET_MARK_REQUIREMENTS: ISOClause[] = [
  { id: 'pm-1', standard: 'planetmark', clauseNumber: 'PM.1', title: 'Carbon Footprint Measurement', description: 'Measure organizational carbon footprint using GHG Protocol', keywords: ['carbon footprint', 'emissions', 'GHG protocol', 'scope 1', 'scope 2', 'scope 3', 'tCO2e'], level: 1 },
  { id: 'pm-1.1', standard: 'planetmark', clauseNumber: 'PM.1.1', title: 'Scope 1 Emissions', description: 'Direct emissions from owned or controlled sources', keywords: ['scope 1', 'direct emissions', 'fleet', 'natural gas', 'combustion'], parentClause: 'pm-1', level: 2 },
  { id: 'pm-1.2', standard: 'planetmark', clauseNumber: 'PM.1.2', title: 'Scope 2 Emissions', description: 'Indirect emissions from purchased electricity, heat, steam', keywords: ['scope 2', 'electricity', 'purchased energy', 'location-based', 'market-based'], parentClause: 'pm-1', level: 2 },
  { id: 'pm-1.3', standard: 'planetmark', clauseNumber: 'PM.1.3', title: 'Scope 3 Emissions', description: 'Value chain emissions (15 categories)', keywords: ['scope 3', 'value chain', 'supply chain', 'business travel', 'commuting', 'waste'], parentClause: 'pm-1', level: 2 },
  { id: 'pm-2', standard: 'planetmark', clauseNumber: 'PM.2', title: 'Data Quality', description: 'Ensure data quality score meets certification requirements', keywords: ['data quality', 'metered data', 'verified data', 'estimates', 'accuracy'], level: 1 },
  { id: 'pm-2.1', standard: 'planetmark', clauseNumber: 'PM.2.1', title: 'Scope 1 & 2 Data Quality', description: 'Achieve data quality score ≥12/16 for Scope 1 & 2', keywords: ['data quality', 'actual readings', 'calibration', 'completeness'], parentClause: 'pm-2', level: 2 },
  { id: 'pm-2.2', standard: 'planetmark', clauseNumber: 'PM.2.2', title: 'Scope 3 Data Quality', description: 'Achieve data quality score ≥11/16 for Scope 3', keywords: ['data quality', 'supplier data', 'spend-based', 'activity-based'], parentClause: 'pm-2', level: 2 },
  { id: 'pm-3', standard: 'planetmark', clauseNumber: 'PM.3', title: 'Improvement Plan', description: 'Implement SMART improvement actions for carbon reduction', keywords: ['improvement plan', 'SMART', 'targets', 'reduction', 'actions'], level: 1 },
  { id: 'pm-3.1', standard: 'planetmark', clauseNumber: 'PM.3.1', title: 'Annual Reduction Target', description: 'Achieve minimum 5% reduction in emissions per employee', keywords: ['reduction target', '5%', 'per FTE', 'year-on-year'], parentClause: 'pm-3', level: 2 },
  { id: 'pm-3.2', standard: 'planetmark', clauseNumber: 'PM.3.2', title: 'SMART Actions', description: 'Document Specific, Measurable, Achievable, Relevant, Time-bound actions', keywords: ['SMART', 'actions', 'owners', 'deadlines', 'measurable'], parentClause: 'pm-3', level: 2 },
  { id: 'pm-4', standard: 'planetmark', clauseNumber: 'PM.4', title: 'Continual Improvement', description: 'Demonstrate year-on-year environmental improvement', keywords: ['continual improvement', 'annual certification', 'trajectory', 'net-zero'], level: 1 },
];

// ============================================================================
// UVDB Achilles Verify B2 Audit Protocol
// ============================================================================

const UVDB_SECTIONS: ISOClause[] = [
  { id: 'uvdb-1', standard: 'uvdb', clauseNumber: 'UVDB.1', title: 'System Assurance and Compliance', description: 'Management system certification and compliance arrangements', keywords: ['management system', 'ISO certification', 'compliance', 'governance'], level: 1 },
  { id: 'uvdb-2', standard: 'uvdb', clauseNumber: 'UVDB.2', title: 'Quality Control and Assurance', description: 'Quality management and assurance processes', keywords: ['quality control', 'quality assurance', 'QC', 'QA', 'inspection'], level: 1 },
  { id: 'uvdb-3', standard: 'uvdb', clauseNumber: 'UVDB.3', title: 'Health and Safety Leadership', description: 'Leadership commitment to health and safety', keywords: ['H&S leadership', 'safety leadership', 'visible commitment', 'accountability'], level: 1 },
  { id: 'uvdb-4', standard: 'uvdb', clauseNumber: 'UVDB.4', title: 'Health and Safety Management', description: 'H&S management system and arrangements', keywords: ['H&S management', 'OHSMS', 'risk assessment', 'safe systems of work'], level: 1 },
  { id: 'uvdb-5', standard: 'uvdb', clauseNumber: 'UVDB.5', title: 'Health and Safety Arrangements', description: 'Operational H&S arrangements and controls', keywords: ['H&S arrangements', 'permits', 'isolations', 'working at height', 'confined space'], level: 1 },
  { id: 'uvdb-6', standard: 'uvdb', clauseNumber: 'UVDB.6', title: 'Occupational Health', description: 'Occupational health management', keywords: ['occupational health', 'health surveillance', 'fitness for work', 'HAVS', 'noise'], level: 1 },
  { id: 'uvdb-7', standard: 'uvdb', clauseNumber: 'UVDB.7', title: 'Safety Critical Personnel', description: 'Competence of safety critical workers', keywords: ['competence', 'training', 'certification', 'CSCS', 'ECS'], level: 1 },
  { id: 'uvdb-8', standard: 'uvdb', clauseNumber: 'UVDB.8', title: 'Environmental Leadership', description: 'Leadership commitment to environmental management', keywords: ['environmental leadership', 'environmental commitment', 'sustainability'], level: 1 },
  { id: 'uvdb-9', standard: 'uvdb', clauseNumber: 'UVDB.9', title: 'Environmental Management', description: 'Environmental management system and arrangements', keywords: ['EMS', 'environmental aspects', 'impacts', 'legal compliance'], level: 1 },
  { id: 'uvdb-10', standard: 'uvdb', clauseNumber: 'UVDB.10', title: 'Environmental Arrangements', description: 'Operational environmental controls', keywords: ['environmental controls', 'pollution prevention', 'spill response'], level: 1 },
  { id: 'uvdb-11', standard: 'uvdb', clauseNumber: 'UVDB.11', title: 'Waste Management', description: 'Waste management arrangements', keywords: ['waste management', 'duty of care', 'waste hierarchy', 'recycling'], level: 1 },
  { id: 'uvdb-12', standard: 'uvdb', clauseNumber: 'UVDB.12', title: 'Sub-contractor Management', description: 'Selection and management of sub-contractors', keywords: ['subcontractor', 'supply chain', 'contractor management', 'approval'], level: 1 },
  { id: 'uvdb-13', standard: 'uvdb', clauseNumber: 'UVDB.13', title: 'Sourcing of Goods', description: 'Sourcing and procurement of goods', keywords: ['sourcing', 'procurement', 'supply chain', 'ethical sourcing'], level: 1 },
  { id: 'uvdb-14', standard: 'uvdb', clauseNumber: 'UVDB.14', title: 'Work Equipment', description: 'Use of work equipment, vehicles and machines', keywords: ['work equipment', 'PUWER', 'LOLER', 'vehicles', 'plant'], level: 1 },
  { id: 'uvdb-15', standard: 'uvdb', clauseNumber: 'UVDB.15', title: 'Key Performance Indicators', description: 'KPI tracking and performance monitoring', keywords: ['KPIs', 'TRIR', 'LTIR', 'RIDDOR', 'performance'], level: 1 },
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
  {
    id: 'iso27001',
    code: 'ISO 27001:2022',
    name: 'Information Security Management System',
    version: '2022',
    description: 'Requirements for establishing, implementing, maintaining and continually improving an information security management system.',
    icon: 'Lock',
    color: 'purple',
    clauses: ISO_27001_CLAUSES,
  },
  {
    id: 'planetmark',
    code: 'Planet Mark',
    name: 'Carbon Certification',
    version: '2024',
    description: 'Business certification for carbon footprint measurement and year-on-year reduction aligned with GHG Protocol and Net-Zero pathway.',
    icon: 'Leaf',
    color: 'green',
    clauses: PLANET_MARK_REQUIREMENTS,
  },
  {
    id: 'uvdb',
    code: 'UVDB Achilles',
    name: 'Verify B2 Audit Protocol',
    version: 'V11.2',
    description: 'UK utilities sector supplier qualification audit covering quality, health & safety, and environmental management.',
    icon: 'Award',
    color: 'yellow',
    clauses: UVDB_SECTIONS,
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
