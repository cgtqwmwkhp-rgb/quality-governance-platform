import { lazy } from "react";
import {
  LayoutDashboard,
  AlertTriangle,
  FileText,
  Shield,
  Car,
  MessageSquare,
  ClipboardCheck,
  FlaskConical,
  BookOpen,
  ListTodo,
  FolderOpen,
  BarChart3,
  Search,
  Users,
  History,
  Calendar,
  Download,
  GitBranch,
  Brain,
  GitMerge,
  Target,
  Award,
  Leaf,
  FileSignature,
} from "lucide-react";

export interface RouteConfig {
  path: string;
  component: React.LazyExoticComponent<any>;
  label: string;
  icon?: typeof LayoutDashboard;
  requiresAuth?: boolean;
  isPortal?: boolean;
  isPublic?: boolean;
}

// Code-split all page components for faster initial load
const Login = lazy(() => import("../pages/Login"));
const Dashboard = lazy(() => import("../pages/Dashboard"));
const Incidents = lazy(() => import("../pages/Incidents"));
const IncidentDetail = lazy(() => import("../pages/IncidentDetail"));
const RTAs = lazy(() => import("../pages/RTAs"));
const RTADetail = lazy(() => import("../pages/RTADetail"));
const Complaints = lazy(() => import("../pages/Complaints"));
const ComplaintDetail = lazy(() => import("../pages/ComplaintDetail"));
const Policies = lazy(() => import("../pages/Policies"));
const Audits = lazy(() => import("../pages/Audits"));
const Investigations = lazy(() => import("../pages/Investigations"));
const InvestigationDetail = lazy(() => import("../pages/InvestigationDetail"));
const Standards = lazy(() => import("../pages/Standards"));
const Actions = lazy(() => import("../pages/Actions"));
const Documents = lazy(() => import("../pages/Documents"));
const AuditTemplateLibrary = lazy(() => import("../pages/AuditTemplateLibrary"));
const AuditTemplateBuilder = lazy(() => import("../pages/AuditTemplateBuilder"));
const AuditExecution = lazy(() => import("../pages/AuditExecution"));
const MobileAuditExecution = lazy(() => import("../pages/MobileAuditExecution"));
const Portal = lazy(() => import("../pages/Portal"));
const PortalLogin = lazy(() => import("../pages/PortalLogin"));
const ForgotPassword = lazy(() => import("../pages/ForgotPassword"));
const ResetPassword = lazy(() => import("../pages/ResetPassword"));
const PortalReport = lazy(() => import("../pages/PortalReport"));
const PortalTrack = lazy(() => import("../pages/PortalTrack"));
const PortalHelp = lazy(() => import("../pages/PortalHelp"));
const PortalRTAForm = lazy(() => import("../pages/PortalRTAForm"));
const PortalDynamicForm = lazy(() => import("../pages/PortalDynamicForm"));
const Analytics = lazy(() => import("../pages/Analytics"));
const GlobalSearch = lazy(() => import("../pages/GlobalSearch"));
const UserManagement = lazy(() => import("../pages/UserManagement"));
const AuditTrail = lazy(() => import("../pages/AuditTrail"));
const CalendarView = lazy(() => import("../pages/CalendarView"));
const Notifications = lazy(() => import("../pages/Notifications"));
const ExportCenter = lazy(() => import("../pages/ExportCenter"));
const ComplianceEvidence = lazy(() => import("../pages/ComplianceEvidence"));
const AdvancedAnalytics = lazy(() => import("../pages/AdvancedAnalytics"));
const DashboardBuilder = lazy(() => import("../pages/DashboardBuilder"));
const ReportGenerator = lazy(() => import("../pages/ReportGenerator"));
const WorkflowCenter = lazy(() => import("../pages/WorkflowCenter"));
const ComplianceAutomation = lazy(() => import("../pages/ComplianceAutomation"));
const RiskRegister = lazy(() => import("../pages/RiskRegister"));
const IMSDashboard = lazy(() => import("../pages/IMSDashboard"));
const AIIntelligence = lazy(() => import("../pages/AIIntelligence"));
const UVDBAudits = lazy(() => import("../pages/UVDBAudits"));
const PlanetMark = lazy(() => import("../pages/PlanetMark"));
const DigitalSignatures = lazy(() => import("../pages/DigitalSignatures"));
const AdminDashboard = lazy(() => import("../pages/admin/AdminDashboard"));
const FormsList = lazy(() => import("../pages/admin/FormsList"));
const FormBuilder = lazy(() => import("../pages/admin/FormBuilder"));
const ContractsManagement = lazy(
  () => import("../pages/admin/ContractsManagement"),
);
const SystemSettings = lazy(() => import("../pages/admin/SystemSettings"));

export const routes: RouteConfig[] = [
  // Public Routes
  {
    path: "/login",
    component: Login,
    label: "Login",
    isPublic: true,
  },
  {
    path: "/portal/login",
    component: PortalLogin,
    label: "Portal Login",
    isPublic: true,
    isPortal: true,
  },
  {
    path: "/forgot-password",
    component: ForgotPassword,
    label: "Forgot Password",
    isPublic: true,
  },
  {
    path: "/reset-password",
    component: ResetPassword,
    label: "Reset Password",
    isPublic: true,
  },

  // Portal Routes
  {
    path: "/portal",
    component: Portal,
    label: "Employee Portal",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/report",
    component: PortalReport,
    label: "Report",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/report/incident",
    component: PortalDynamicForm,
    label: "Report Incident",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/report/near-miss",
    component: PortalDynamicForm,
    label: "Report Near Miss",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/report/complaint",
    component: PortalDynamicForm,
    label: "Report Complaint",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/report/rta",
    component: PortalRTAForm,
    label: "Report RTA",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/track",
    component: PortalTrack,
    label: "Track",
    isPortal: true,
    requiresAuth: true,
  },
  {
    path: "/portal/help",
    component: PortalHelp,
    label: "Help",
    isPortal: true,
    requiresAuth: true,
  },

  // Protected Admin Routes
  {
    path: "/dashboard",
    component: Dashboard,
    label: "Dashboard",
    icon: LayoutDashboard,
    requiresAuth: true,
  },
  {
    path: "/incidents",
    component: Incidents,
    label: "Incidents",
    icon: AlertTriangle,
    requiresAuth: true,
  },
  {
    path: "/incidents/:id",
    component: IncidentDetail,
    label: "Incident Detail",
    requiresAuth: true,
  },
  {
    path: "/rtas",
    component: RTAs,
    label: "RTAs",
    icon: Car,
    requiresAuth: true,
  },
  {
    path: "/rtas/:id",
    component: RTADetail,
    label: "RTA Detail",
    requiresAuth: true,
  },
  {
    path: "/complaints",
    component: Complaints,
    label: "Complaints",
    icon: MessageSquare,
    requiresAuth: true,
  },
  {
    path: "/complaints/:id",
    component: ComplaintDetail,
    label: "Complaint Detail",
    requiresAuth: true,
  },
  {
    path: "/policies",
    component: Policies,
    label: "Policies",
    icon: FileText,
    requiresAuth: true,
  },
  {
    path: "/audits",
    component: Audits,
    label: "Audits",
    icon: ClipboardCheck,
    requiresAuth: true,
  },
  {
    path: "/audit-templates",
    component: AuditTemplateLibrary,
    label: "Audit Templates",
    requiresAuth: true,
  },
  {
    path: "/audit-templates/new",
    component: AuditTemplateBuilder,
    label: "New Audit Template",
    requiresAuth: true,
  },
  {
    path: "/audit-templates/:templateId/edit",
    component: AuditTemplateBuilder,
    label: "Edit Audit Template",
    requiresAuth: true,
  },
  {
    path: "/audits/:auditId/execute",
    component: AuditExecution,
    label: "Audit Execution",
    requiresAuth: true,
  },
  {
    path: "/audits/:auditId/mobile",
    component: MobileAuditExecution,
    label: "Mobile Audit Execution",
    requiresAuth: true,
  },
  {
    path: "/investigations",
    component: Investigations,
    label: "Investigations",
    icon: FlaskConical,
    requiresAuth: true,
  },
  {
    path: "/investigations/:id",
    component: InvestigationDetail,
    label: "Investigation Detail",
    requiresAuth: true,
  },
  {
    path: "/standards",
    component: Standards,
    label: "Standards",
    icon: BookOpen,
    requiresAuth: true,
  },
  {
    path: "/actions",
    component: Actions,
    label: "Actions",
    icon: ListTodo,
    requiresAuth: true,
  },
  {
    path: "/documents",
    component: Documents,
    label: "Documents",
    icon: FolderOpen,
    requiresAuth: true,
  },
  {
    path: "/analytics",
    component: Analytics,
    label: "Analytics",
    icon: BarChart3,
    requiresAuth: true,
  },
  {
    path: "/analytics/advanced",
    component: AdvancedAnalytics,
    label: "Advanced Analytics",
    requiresAuth: true,
  },
  {
    path: "/analytics/dashboards",
    component: DashboardBuilder,
    label: "Dashboard Builder",
    requiresAuth: true,
  },
  {
    path: "/analytics/reports",
    component: ReportGenerator,
    label: "Report Generator",
    requiresAuth: true,
  },
  {
    path: "/search",
    component: GlobalSearch,
    label: "Search",
    icon: Search,
    requiresAuth: true,
  },
  {
    path: "/users",
    component: UserManagement,
    label: "User Management",
    icon: Users,
    requiresAuth: true,
  },
  {
    path: "/audit-trail",
    component: AuditTrail,
    label: "Audit Trail",
    icon: History,
    requiresAuth: true,
  },
  {
    path: "/calendar",
    component: CalendarView,
    label: "Calendar",
    icon: Calendar,
    requiresAuth: true,
  },
  {
    path: "/notifications",
    component: Notifications,
    label: "Notifications",
    requiresAuth: true,
  },
  {
    path: "/exports",
    component: ExportCenter,
    label: "Export Center",
    icon: Download,
    requiresAuth: true,
  },
  {
    path: "/compliance",
    component: ComplianceEvidence,
    label: "Compliance Evidence",
    icon: Shield,
    requiresAuth: true,
  },
  {
    path: "/workflows",
    component: WorkflowCenter,
    label: "Workflow Center",
    icon: GitBranch,
    requiresAuth: true,
  },
  {
    path: "/compliance-automation",
    component: ComplianceAutomation,
    label: "Compliance Automation",
    requiresAuth: true,
  },
  {
    path: "/risk-register",
    component: RiskRegister,
    label: "Risk Register",
    icon: Target,
    requiresAuth: true,
  },
  {
    path: "/ims",
    component: IMSDashboard,
    label: "IMS Dashboard",
    icon: GitMerge,
    requiresAuth: true,
  },
  {
    path: "/ai-intelligence",
    component: AIIntelligence,
    label: "AI Intelligence",
    icon: Brain,
    requiresAuth: true,
  },
  {
    path: "/uvdb",
    component: UVDBAudits,
    label: "UVDB Audits",
    icon: Award,
    requiresAuth: true,
  },
  {
    path: "/planet-mark",
    component: PlanetMark,
    label: "Planet Mark",
    icon: Leaf,
    requiresAuth: true,
  },
  {
    path: "/signatures",
    component: DigitalSignatures,
    label: "Digital Signatures",
    icon: FileSignature,
    requiresAuth: true,
  },
  {
    path: "/admin",
    component: AdminDashboard,
    label: "Admin Dashboard",
    requiresAuth: true,
  },
  {
    path: "/admin/forms",
    component: FormsList,
    label: "Forms",
    requiresAuth: true,
  },
  {
    path: "/admin/forms/new",
    component: FormBuilder,
    label: "New Form",
    requiresAuth: true,
  },
  {
    path: "/admin/forms/:templateId",
    component: FormBuilder,
    label: "Edit Form",
    requiresAuth: true,
  },
  {
    path: "/admin/contracts",
    component: ContractsManagement,
    label: "Contracts Management",
    requiresAuth: true,
  },
  {
    path: "/admin/settings",
    component: SystemSettings,
    label: "System Settings",
    requiresAuth: true,
  },
];
