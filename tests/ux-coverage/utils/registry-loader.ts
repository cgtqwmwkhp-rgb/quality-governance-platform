/**
 * Registry Loader for UX Functional Coverage Gate
 * 
 * Loads and parses PAGE_REGISTRY.yml, BUTTON_REGISTRY.yml, and WORKFLOW_REGISTRY.yml
 * to drive Playwright tests.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

// Types for registries
export interface PageEntry {
  pageId: string;
  route: string;
  auth: 'anon' | 'portal_sso' | 'jwt_admin';
  criticality: 'P0' | 'P1' | 'P2';
  component: string;
  expected_empty_state: string | null;
  expected_degraded_state: string | null;
  description: string;
}

export interface ButtonEntry {
  pageId: string;
  actionId: string;
  selector: string;
  fallback_selector?: string;
  criticality: 'P0' | 'P1' | 'P2';
  expected_outcome: 'navigation' | 'network_call' | 'ui_state' | 'disabled';
  expected_route?: string;
  expected_api?: string;
  expected_state?: string;
  disabled_reason?: string | null;
  description: string;
}

export interface WorkflowStep {
  stepId: number;
  action: string;
  route?: string;
  selector?: string;
  fallback_selector?: string;
  form_fields?: Array<{ selector: string; value: string }>;
  exit_criteria: string;
  expected_api?: string;
}

export interface WorkflowEntry {
  workflowId: string;
  name: string;
  description: string;
  criticality: 'P0' | 'P1' | 'P2';
  auth_type: 'none' | 'portal_sso' | 'jwt_admin';
  steps: WorkflowStep[];
  success_terminal_state: string;
  recovery_path: string;
  expected_apis: string[];
  max_duration_seconds: number;
}

export interface PageRegistry {
  version: string;
  public_routes: PageEntry[];
  portal_routes: PageEntry[];
  admin_routes: PageEntry[];
}

export interface ButtonRegistry {
  version: string;
  portal_actions: ButtonEntry[];
  admin_actions: ButtonEntry[];
  admin_config_actions: ButtonEntry[];
}

export interface WorkflowRegistry {
  version: string;
  p0_workflows: WorkflowEntry[];
  p1_workflows: WorkflowEntry[];
  p2_workflows: WorkflowEntry[];
}

const REGISTRY_PATH = path.join(__dirname, '../../../docs/ops');

export function loadPageRegistry(): PageRegistry {
  const filePath = path.join(REGISTRY_PATH, 'PAGE_REGISTRY.yml');
  const content = fs.readFileSync(filePath, 'utf-8');
  return yaml.load(content) as PageRegistry;
}

export function loadButtonRegistry(): ButtonRegistry {
  const filePath = path.join(REGISTRY_PATH, 'BUTTON_REGISTRY.yml');
  const content = fs.readFileSync(filePath, 'utf-8');
  return yaml.load(content) as ButtonRegistry;
}

export function loadWorkflowRegistry(): WorkflowRegistry {
  const filePath = path.join(REGISTRY_PATH, 'WORKFLOW_REGISTRY.yml');
  const content = fs.readFileSync(filePath, 'utf-8');
  return yaml.load(content) as WorkflowRegistry;
}

export function getAllPages(criticality?: 'P0' | 'P1' | 'P2'): PageEntry[] {
  const registry = loadPageRegistry();
  const allPages = [
    ...registry.public_routes,
    ...registry.portal_routes,
    ...registry.admin_routes,
  ];
  
  if (criticality) {
    return allPages.filter(p => p.criticality === criticality);
  }
  return allPages;
}

export function getP0P1Pages(): PageEntry[] {
  return getAllPages().filter(p => p.criticality === 'P0' || p.criticality === 'P1');
}

export function getAllButtons(criticality?: 'P0' | 'P1' | 'P2'): ButtonEntry[] {
  const registry = loadButtonRegistry();
  const allButtons = [
    ...registry.portal_actions,
    ...registry.admin_actions,
    ...registry.admin_config_actions,
  ];
  
  if (criticality) {
    return allButtons.filter(b => b.criticality === criticality);
  }
  return allButtons;
}

export function getP0P1Buttons(): ButtonEntry[] {
  return getAllButtons().filter(b => b.criticality === 'P0' || b.criticality === 'P1');
}

export function getAllWorkflows(criticality?: 'P0' | 'P1' | 'P2'): WorkflowEntry[] {
  const registry = loadWorkflowRegistry();
  const allWorkflows = [
    ...registry.p0_workflows,
    ...registry.p1_workflows,
    ...registry.p2_workflows,
  ];
  
  if (criticality) {
    return allWorkflows.filter(w => w.criticality === criticality);
  }
  return allWorkflows;
}

export function getP0Workflows(): WorkflowEntry[] {
  return getAllWorkflows('P0');
}

// PII detection helper
const PII_PATTERNS = [
  /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/, // Email
  /\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/, // Phone
  /\b\d{2}\/\d{2}\/\d{4}\b/, // Date of birth pattern
  /\bNI[A-Z]{2}\d{6}[A-Z]\b/i, // NI number
];

export function containsPII(text: string): boolean {
  return PII_PATTERNS.some(pattern => pattern.test(text));
}

export function sanitizeForArtifact(text: string): string {
  let sanitized = text;
  
  // Replace emails
  sanitized = sanitized.replace(
    /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
    '[EMAIL_REDACTED]'
  );
  
  // Replace phone numbers
  sanitized = sanitized.replace(
    /\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
    '[PHONE_REDACTED]'
  );
  
  return sanitized;
}
