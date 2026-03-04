import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

vi.mock('../lib/syncService', () => ({
  startAutoSync: vi.fn(() => vi.fn()),
}));

vi.mock('../hooks/useWebVitals', () => ({
  useWebVitals: vi.fn(),
}));

vi.mock('../services/errorTracker', () => ({
  trackComponentError: vi.fn(),
}));

vi.mock('../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:3000',
}));

vi.mock('../api/client', () => ({
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ data: { unread_count: 0 } }),
  },
}));

vi.mock('../components/copilot/AICopilot', () => ({
  default: () => <div data-testid="ai-copilot" />,
}));

vi.mock('../components/OfflineIndicator', () => ({
  default: () => null,
}));

vi.mock('../components/ui/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}));

vi.mock('../pages/Login', () => ({
  default: ({ onLogin }: { onLogin: (t: string) => void }) => (
    <div data-testid="login-page">
      <h1>Sign In</h1>
      <input data-testid="email-input" type="email" />
    </div>
  ),
}));

vi.mock('../pages/Dashboard', () => ({
  default: () => <div data-testid="dashboard-page">Dashboard</div>,
}));

vi.mock('../pages/ForgotPassword', () => ({
  default: () => <div>ForgotPassword</div>,
}));

vi.mock('../pages/ResetPassword', () => ({
  default: () => <div>ResetPassword</div>,
}));

vi.mock('../pages/Portal', () => ({ default: () => <div>Portal</div> }));
vi.mock('../pages/PortalLogin', () => ({ default: () => <div>PortalLogin</div> }));
vi.mock('../pages/PortalReport', () => ({ default: () => <div>PortalReport</div> }));
vi.mock('../pages/PortalTrack', () => ({ default: () => <div>PortalTrack</div> }));
vi.mock('../pages/PortalHelp', () => ({ default: () => <div>PortalHelp</div> }));
vi.mock('../pages/PortalIncidentForm', () => ({ default: () => <div>PortalIncidentForm</div> }));
vi.mock('../pages/PortalRTAForm', () => ({ default: () => <div>PortalRTAForm</div> }));
vi.mock('../pages/PortalNearMissForm', () => ({ default: () => <div>PortalNearMissForm</div> }));
vi.mock('../pages/PortalDynamicForm', () => ({ default: () => <div>PortalDynamicForm</div> }));
vi.mock('../pages/Incidents', () => ({ default: () => <div>Incidents</div> }));
vi.mock('../pages/IncidentDetail', () => ({ default: () => <div>IncidentDetail</div> }));
vi.mock('../pages/RTAs', () => ({ default: () => <div>RTAs</div> }));
vi.mock('../pages/RTADetail', () => ({ default: () => <div>RTADetail</div> }));
vi.mock('../pages/Complaints', () => ({ default: () => <div>Complaints</div> }));
vi.mock('../pages/ComplaintDetail', () => ({ default: () => <div>ComplaintDetail</div> }));
vi.mock('../pages/Policies', () => ({ default: () => <div>Policies</div> }));
vi.mock('../pages/Risks', () => ({ default: () => <div>Risks</div> }));
vi.mock('../pages/Audits', () => ({ default: () => <div>Audits</div> }));
vi.mock('../pages/Investigations', () => ({ default: () => <div>Investigations</div> }));
vi.mock('../pages/Standards', () => ({ default: () => <div>Standards</div> }));
vi.mock('../pages/Actions', () => ({ default: () => <div>Actions</div> }));
vi.mock('../pages/Documents', () => ({ default: () => <div>Documents</div> }));
vi.mock('../pages/AuditTemplateLibrary', () => ({ default: () => <div>AuditTemplateLibrary</div> }));
vi.mock('../pages/AuditTemplateBuilder', () => ({ default: () => <div>AuditTemplateBuilder</div> }));
vi.mock('../pages/AuditExecution', () => ({ default: () => <div>AuditExecution</div> }));
vi.mock('../pages/MobileAuditExecution', () => ({ default: () => <div>MobileAuditExecution</div> }));
vi.mock('../pages/Analytics', () => ({ default: () => <div>Analytics</div> }));
vi.mock('../pages/GlobalSearch', () => ({ default: () => <div>GlobalSearch</div> }));
vi.mock('../pages/UserManagement', () => ({ default: () => <div>UserManagement</div> }));
vi.mock('../pages/AuditTrail', () => ({ default: () => <div>AuditTrail</div> }));
vi.mock('../pages/CalendarView', () => ({ default: () => <div>CalendarView</div> }));
vi.mock('../pages/Notifications', () => ({ default: () => <div>Notifications</div> }));
vi.mock('../pages/ExportCenter', () => ({ default: () => <div>ExportCenter</div> }));
vi.mock('../pages/ComplianceEvidence', () => ({ default: () => <div>ComplianceEvidence</div> }));
vi.mock('../pages/AdvancedAnalytics', () => ({ default: () => <div>AdvancedAnalytics</div> }));
vi.mock('../pages/DashboardBuilder', () => ({ default: () => <div>DashboardBuilder</div> }));
vi.mock('../pages/ReportGenerator', () => ({ default: () => <div>ReportGenerator</div> }));
vi.mock('../pages/WorkflowCenter', () => ({ default: () => <div>WorkflowCenter</div> }));
vi.mock('../pages/ComplianceAutomation', () => ({ default: () => <div>ComplianceAutomation</div> }));
vi.mock('../pages/RiskRegister', () => ({ default: () => <div>RiskRegister</div> }));
vi.mock('../pages/IMSDashboard', () => ({ default: () => <div>IMSDashboard</div> }));
vi.mock('../pages/AIIntelligence', () => ({ default: () => <div>AIIntelligence</div> }));
vi.mock('../pages/UVDBAudits', () => ({ default: () => <div>UVDBAudits</div> }));
vi.mock('../pages/PlanetMark', () => ({ default: () => <div>PlanetMark</div> }));
vi.mock('../pages/DigitalSignatures', () => ({ default: () => <div>DigitalSignatures</div> }));
vi.mock('../pages/workforce/AssessmentCreate', () => ({ default: () => <div>AssessmentCreate</div> }));
vi.mock('../pages/workforce/InductionCreate', () => ({ default: () => <div>InductionCreate</div> }));
vi.mock('../pages/workforce/Assessments', () => ({ default: () => <div>Assessments</div> }));
vi.mock('../pages/workforce/AssessmentExecution', () => ({ default: () => <div>AssessmentExecution</div> }));
vi.mock('../pages/workforce/Training', () => ({ default: () => <div>Training</div> }));
vi.mock('../pages/workforce/TrainingExecution', () => ({ default: () => <div>TrainingExecution</div> }));
vi.mock('../pages/workforce/Engineers', () => ({ default: () => <div>Engineers</div> }));
vi.mock('../pages/workforce/EngineerProfile', () => ({ default: () => <div>EngineerProfile</div> }));
vi.mock('../pages/workforce/Calendar', () => ({ default: () => <div>Calendar</div> }));
vi.mock('../pages/workforce/CompetencyDashboard', () => ({ default: () => <div>CompetencyDashboard</div> }));
vi.mock('../pages/admin/AdminDashboard', () => ({ default: () => <div>AdminDashboard</div> }));
vi.mock('../pages/admin/FormsList', () => ({ default: () => <div>FormsList</div> }));
vi.mock('../pages/admin/FormBuilder', () => ({ default: () => <div>FormBuilder</div> }));
vi.mock('../pages/admin/ContractsManagement', () => ({ default: () => <div>ContractsManagement</div> }));
vi.mock('../pages/admin/SystemSettings', () => ({ default: () => <div>SystemSettings</div> }));

describe('App', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders login page when no token in localStorage', async () => {
    const App = (await import('../App')).default;

    await act(async () => {
      render(<App />);
    });

    expect(screen.getByTestId('login-page')).toBeInTheDocument();
    expect(screen.getByTestId('email-input')).toBeInTheDocument();
  });

  it('does not show login page when token exists in localStorage', async () => {
    localStorage.setItem('access_token', 'test-jwt-token');

    const App = (await import('../App')).default;

    await act(async () => {
      render(<App />);
    });

    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
  });
});
