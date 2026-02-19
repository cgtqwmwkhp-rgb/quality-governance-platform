/**
 * Digital Signatures Page
 * 
 * DocuSign-level e-signature management with:
 * - Signature request creation
 * - Template management
 * - Signing interface
 * - Audit trail viewer
 */

import React, { useState, useEffect, useCallback } from 'react';
import { signaturesApi } from '../api/client';
import type { SignatureRequestEntry } from '../api/client';
import {
  FileSignature,
  Plus,
  Send,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Users,
  FileText,
  Mail,
  Calendar,
  ChevronRight,
  Eye,
  Download,
  MoreVertical,
  Search,
  RefreshCw,
  History,
  PenTool,
  User,
  Shield,
  MapPin,
  Smartphone,
} from 'lucide-react';
import { cn } from "../helpers/utils";
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardHeader, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/Dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/Select';

interface SignatureRequest {
  id: number;
  referenceNumber: string;
  title: string;
  description?: string;
  documentType: string;
  status: 'draft' | 'pending' | 'in_progress' | 'completed' | 'declined' | 'expired';
  workflowType: 'sequential' | 'parallel';
  createdAt: Date;
  expiresAt: Date;
  completedAt?: Date;
  signers: Signer[];
}

interface Signer {
  id: number;
  name: string;
  email: string;
  role: string;
  order: number;
  status: 'pending' | 'viewed' | 'signed' | 'declined';
  signedAt?: Date;
  declinedAt?: Date;
}

interface SignatureTemplate {
  id: number;
  name: string;
  description?: string;
  signerRoles: { role: string; order: number }[];
  workflowType: string;
  expiryDays: number;
}

const DigitalSignatures: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'requests' | 'pending' | 'templates' | 'audit'>('requests');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showSigningModal, setShowSigningModal] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<SignatureRequest | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [signatureRequests, setSignatureRequests] = useState<SignatureRequest[]>([]);
  const [templates, setTemplates] = useState<SignatureTemplate[]>([]);
  const [loading, setLoading] = useState(true);  // eslint-disable-line @typescript-eslint/no-unused-vars

  const mapApiRequest = (r: SignatureRequestEntry): SignatureRequest => ({
    id: r.id,
    referenceNumber: r.reference_number,
    title: r.title,
    description: r.description,
    documentType: r.document_type,
    status: r.status as SignatureRequest['status'],
    workflowType: r.workflow_type as 'sequential' | 'parallel',
    createdAt: new Date(r.created_at),
    expiresAt: r.expires_at ? new Date(r.expires_at) : new Date(Date.now() + 30 * 86400000),
    completedAt: r.completed_at ? new Date(r.completed_at) : undefined,
    signers: (r.signers || []).map(s => ({
      id: s.id,
      name: s.name,
      email: s.email,
      role: s.role,
      order: s.order,
      status: s.status as Signer['status'],
      signedAt: s.signed_at ? new Date(s.signed_at) : undefined,
      declinedAt: s.declined_at ? new Date(s.declined_at) : undefined,
    })),
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [reqRes, tplRes] = await Promise.all([
        signaturesApi.list(filterStatus !== 'all' ? filterStatus : undefined),
        signaturesApi.listTemplates(),
      ]);
      setSignatureRequests((reqRes.data || []).map(mapApiRequest));
      setTemplates((tplRes.data || []).map((t: any) => ({
        id: Number(t.id),
        name: String(t.name || ''),
        description: t.description ? String(t.description) : undefined,
        signerRoles: (t.signer_roles as { role: string; order: number }[]) || [],
        workflowType: String(t.workflow_type || 'sequential'),
        expiryDays: Number(t.expiry_days || 30),
      })));
    } catch {
      console.error('Failed to load signatures');
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => { loadData(); }, [loadData]);

  const auditLog: { id: number; action: string; actor: string; time: Date; details: string; ip?: string }[] = [];

  const statusVariants: Record<string, 'default' | 'submitted' | 'in-progress' | 'resolved' | 'destructive'> = {
    draft: 'default',
    pending: 'submitted',
    in_progress: 'in-progress',
    completed: 'resolved',
    declined: 'destructive',
    expired: 'default',
    viewed: 'in-progress',
    signed: 'resolved',
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
      case 'signed':
        return <CheckCircle className="w-4 h-4 text-success" />;
      case 'declined':
        return <XCircle className="w-4 h-4 text-destructive" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-warning" />;
      case 'in_progress':
      case 'viewed':
        return <AlertCircle className="w-4 h-4 text-info" />;
      default:
        return <Clock className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const filteredRequests = signatureRequests.filter(req => {
    if (filterStatus !== 'all' && req.status !== filterStatus) return false;
    if (searchQuery && !req.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-primary to-primary-hover rounded-xl">
              <FileSignature className="w-8 h-8 text-primary-foreground" />
            </div>
            Digital Signatures
          </h1>
          <p className="text-muted-foreground mt-1">
            Secure electronic signatures with legal compliance
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-5 h-5" />
          New Request
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-warning/20 rounded-lg">
                <Clock className="w-6 h-6 text-warning" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="text-2xl font-bold text-foreground">5</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-info/20 rounded-lg">
                <Send className="w-6 h-6 text-info" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">In Progress</p>
                <p className="text-2xl font-bold text-foreground">3</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-success/20 rounded-lg">
                <CheckCircle className="w-6 h-6 text-success" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Completed</p>
                <p className="text-2xl font-bold text-foreground">47</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-primary/20 rounded-lg">
                <FileText className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Signatures</p>
                <p className="text-2xl font-bold text-foreground">156</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border pb-2">
        {[
          { id: 'requests', label: 'Requests', icon: FileText },
          { id: 'pending', label: 'Awaiting My Signature', icon: PenTool },
          { id: 'templates', label: 'Templates', icon: FileSignature },
          { id: 'audit', label: 'Audit Trail', icon: History },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg transition-colors",
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Requests Tab */}
      {activeTab === 'requests' && (
        <div>
          {/* Filters */}
          <div className="flex items-center gap-4 mb-6">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search requests..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="declined">Declined</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="secondary" size="sm">
              <RefreshCw className="w-5 h-5" />
            </Button>
          </div>

          {/* Requests List */}
          <div className="space-y-4">
            {filteredRequests.map(request => (
              <Card key={request.id} className="hover:border-primary/50 transition-colors">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <Badge variant={statusVariants[request.status]}>
                          {request.status.replace('_', ' ').toUpperCase()}
                        </Badge>
                        <span className="text-sm text-muted-foreground">{request.referenceNumber}</span>
                        <span className="text-sm text-muted-foreground">•</span>
                        <span className="text-sm text-muted-foreground">
                          {request.workflowType === 'sequential' ? 'Sequential' : 'Parallel'} signing
                        </span>
                      </div>
                      <h3 className="text-lg font-medium text-foreground mb-1">{request.title}</h3>
                      {request.description && (
                        <p className="text-sm text-muted-foreground mb-3">{request.description}</p>
                      )}
                      
                      {/* Signers */}
                      <div className="flex items-center gap-4 mt-4">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Users className="w-4 h-4" />
                          <span>{request.signers.length} signers</span>
                        </div>
                        <div className="flex -space-x-2">
                          {request.signers.map(signer => (
                            <div
                              key={signer.id}
                              className={cn(
                                "w-8 h-8 rounded-full border-2 border-card flex items-center justify-center text-xs font-medium text-white",
                                signer.status === 'signed' ? 'bg-success' :
                                signer.status === 'declined' ? 'bg-destructive' :
                                signer.status === 'viewed' ? 'bg-info' : 'bg-muted-foreground'
                              )}
                              title={`${signer.name} - ${signer.status}`}
                            >
                              {signer.name.charAt(0)}
                            </div>
                          ))}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Calendar className="w-4 h-4" />
                          <span>Expires {request.expiresAt.toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedRequest(request)}>
                        <Eye className="w-5 h-5" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Download className="w-5 h-5" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <MoreVertical className="w-5 h-5" />
                      </Button>
                    </div>
                  </div>

                  {/* Signer Progress */}
                  <div className="mt-4 pt-4 border-t border-border">
                    <div className="space-y-2">
                      {request.signers.map((signer, index) => (
                        <div key={signer.id} className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs text-muted-foreground">
                            {request.workflowType === 'sequential' ? index + 1 : '•'}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-foreground">{signer.name}</span>
                              <span className="text-xs text-muted-foreground">({signer.role})</span>
                            </div>
                            <span className="text-xs text-muted-foreground">{signer.email}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(signer.status)}
                            <span className="text-sm text-muted-foreground capitalize">{signer.status}</span>
                            {signer.signedAt && (
                              <span className="text-xs text-muted-foreground">
                                {signer.signedAt.toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Pending Signatures Tab */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-primary/10 to-primary/5 rounded-xl border border-primary/30 p-6">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-primary/20 rounded-xl">
                <PenTool className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-foreground">2 Documents Awaiting Your Signature</h2>
                <p className="text-muted-foreground">Review and sign these documents to complete the approval process.</p>
              </div>
            </div>
          </div>

          {signatureRequests
            .filter(r => r.status === 'pending' || r.status === 'in_progress')
            .map(request => (
              <Card key={request.id}>
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-medium text-foreground mb-1">{request.title}</h3>
                      <p className="text-sm text-muted-foreground">{request.description}</p>
                    </div>
                    <span className="text-sm text-muted-foreground">{request.referenceNumber}</span>
                  </div>

                  <div className="flex items-center gap-4 mb-6">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <User className="w-4 h-4" />
                      <span>From: Admin User</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Calendar className="w-4 h-4" />
                      <span>Due: {request.expiresAt.toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button
                      onClick={() => {
                        setSelectedRequest(request);
                        setShowSigningModal(true);
                      }}
                    >
                      <PenTool className="w-4 h-4" />
                      Review & Sign
                    </Button>
                    <Button variant="secondary">
                      <Eye className="w-4 h-4" />
                      View Document
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map(template => (
            <Card key={template.id} className="hover:border-primary/50 transition-colors">
              <CardContent className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-3 bg-primary/20 rounded-lg">
                    <FileSignature className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-medium text-foreground">{template.name}</h3>
                    <p className="text-sm text-muted-foreground">{template.workflowType} workflow</p>
                  </div>
                </div>

                {template.description && (
                  <p className="text-sm text-muted-foreground mb-4">{template.description}</p>
                )}

                <div className="space-y-2 mb-4">
                  <p className="text-xs text-muted-foreground uppercase">Signing Order</p>
                  {template.signerRoles.map((role, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs text-muted-foreground">
                        {template.workflowType === 'sequential' ? i + 1 : '•'}
                      </span>
                      <span className="text-sm text-foreground">{role.role}</span>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <span className="text-sm text-muted-foreground">
                    Expires in {template.expiryDays} days
                  </span>
                  <button className="flex items-center gap-1 text-primary hover:text-primary-hover text-sm transition-colors">
                    Use Template
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Add Template Card */}
          <button className="bg-card/30 rounded-xl border border-dashed border-border p-6 flex flex-col items-center justify-center hover:border-primary/50 transition-colors min-h-[200px]">
            <div className="p-4 bg-muted rounded-full mb-4">
              <Plus className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">Create New Template</p>
          </button>
        </div>
      )}

      {/* Audit Trail Tab */}
      {activeTab === 'audit' && (
        <Card>
          <CardHeader>
            <h3 className="text-lg font-medium text-foreground">Recent Activity</h3>
          </CardHeader>
          <div className="divide-y divide-border">
            {auditLog.map(log => (
              <div key={log.id} className="p-4 hover:bg-muted/30 transition-colors">
                <div className="flex items-start gap-4">
                  <div className={cn(
                    "p-2 rounded-lg",
                    log.action === 'signed' ? 'bg-success/20' :
                    log.action === 'viewed' ? 'bg-info/20' :
                    log.action === 'created' ? 'bg-primary/20' : 'bg-muted'
                  )}>
                    {log.action === 'signed' && <CheckCircle className="w-5 h-5 text-success" />}
                    {log.action === 'viewed' && <Eye className="w-5 h-5 text-info" />}
                    {log.action === 'created' && <Plus className="w-5 h-5 text-primary" />}
                    {log.action === 'sent' && <Send className="w-5 h-5 text-muted-foreground" />}
                    {log.action === 'reminded' && <Mail className="w-5 h-5 text-warning" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-foreground">{log.actor}</span>
                      <span className="text-muted-foreground">{log.action}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{log.details}</p>
                    {log.ip && (
                      <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                        <MapPin className="w-3 h-3" />
                        <span>IP: {log.ip}</span>
                      </div>
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {log.time.toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Create Request Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Signature Request</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground mb-4">Create a new document for signature collection.</p>
          <div className="text-center py-8">
            <FileSignature className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
            <p className="text-muted-foreground">Coming soon: Full document upload and signer configuration</p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button onClick={() => setShowCreateModal(false)}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Signing Modal */}
      {showSigningModal && selectedRequest && (
        <SigningModal
          request={selectedRequest}
          onClose={() => {
            setShowSigningModal(false);
            setSelectedRequest(null);
          }}
        />
      )}
    </div>
  );
};

// Signing Modal Component
const SigningModal: React.FC<{
  request: SignatureRequest;
  onClose: () => void;
}> = ({ request, onClose }) => {
  const [signatureType, setSignatureType] = useState<'draw' | 'type' | 'upload'>('draw');
  const [typedName, setTypedName] = useState('');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    setIsDrawing(true);
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const rect = canvas.getBoundingClientRect();
      ctx.beginPath();
      ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
    }
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const rect = canvas.getBoundingClientRect();
      ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
      ctx.strokeStyle = 'hsl(var(--primary))';
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.stroke();
    }
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  const handleSign = () => {
    console.log('Signing document...');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-border">
        {/* Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Sign Document</h2>
              <p className="text-sm text-muted-foreground">{request.title}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <XCircle className="w-6 h-6" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Document Preview */}
          <div className="bg-muted rounded-lg p-4 mb-6 border border-border">
            <div className="flex items-center gap-3 mb-3">
              <FileText className="w-5 h-5 text-muted-foreground" />
              <span className="text-foreground font-medium">Document Preview</span>
            </div>
            <div className="bg-white dark:bg-background rounded-lg p-6 min-h-[200px]">
              <h3 className="font-bold text-foreground mb-4">{request.title}</h3>
              <p className="text-sm text-muted-foreground mb-4">{request.description}</p>
              <p className="text-sm text-muted-foreground">
                This document requires your electronic signature to indicate your acknowledgment and agreement 
                to the terms outlined above. By signing, you confirm that you have read and understood the contents.
              </p>
            </div>
          </div>

          {/* Signature Type Selection */}
          <div className="mb-6">
            <p className="text-sm text-muted-foreground mb-3">Choose how to sign:</p>
            <div className="flex gap-3">
              {[
                { id: 'draw', label: 'Draw', icon: PenTool },
                { id: 'type', label: 'Type', icon: FileText },
                { id: 'upload', label: 'Upload', icon: FileSignature },
              ].map(option => (
                <button
                  key={option.id}
                  onClick={() => setSignatureType(option.id as typeof signatureType)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors",
                    signatureType === option.id
                      ? 'border-primary bg-primary/20 text-primary'
                      : 'border-border text-muted-foreground hover:border-primary/50'
                  )}
                >
                  <option.icon className="w-4 h-4" />
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Signature Input */}
          <div className="mb-6">
            {signatureType === 'draw' && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-muted-foreground">Draw your signature below:</p>
                  <button onClick={clearCanvas} className="text-sm text-primary hover:text-primary-hover">
                    Clear
                  </button>
                </div>
                <canvas
                  ref={canvasRef}
                  width={540}
                  height={150}
                  className="w-full bg-white dark:bg-background rounded-lg cursor-crosshair border-2 border-dashed border-border"
                  onMouseDown={startDrawing}
                  onMouseMove={draw}
                  onMouseUp={stopDrawing}
                  onMouseLeave={stopDrawing}
                />
              </div>
            )}
            
            {signatureType === 'type' && (
              <div>
                <p className="text-sm text-muted-foreground mb-2">Type your name:</p>
                <Input
                  type="text"
                  value={typedName}
                  onChange={(e) => setTypedName(e.target.value)}
                  placeholder="Enter your full name"
                />
                {typedName && (
                  <div className="mt-4 p-4 bg-white dark:bg-background rounded-lg">
                    <p className="text-2xl text-primary font-script">{typedName}</p>
                  </div>
                )}
              </div>
            )}

            {signatureType === 'upload' && (
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center">
                <FileSignature className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground mb-2">Drag and drop your signature image</p>
                <p className="text-sm text-muted-foreground">or</p>
                <Button variant="secondary" className="mt-2">
                  Browse Files
                </Button>
              </div>
            )}
          </div>

          {/* Legal Agreement */}
          <div className="bg-muted rounded-lg p-4 mb-6 border border-border">
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                id="agree"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="mt-1"
              />
              <label htmlFor="agree" className="text-sm text-foreground">
                By signing this document electronically, I agree that my electronic signature is the legal 
                equivalent of my manual signature. I consent to the use of electronic signatures, and I 
                understand that I am legally bound by this agreement.
              </label>
            </div>
          </div>

          {/* Verification Info */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground mb-6">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-success" />
              <span>256-bit encryption</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4" />
              <span>Location recorded</span>
            </div>
            <div className="flex items-center gap-2">
              <Smartphone className="w-4 h-4" />
              <span>Device verified</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button variant="secondary" onClick={onClose} className="flex-1">
              Cancel
            </Button>
            <Button onClick={handleSign} disabled={!agreedToTerms} className="flex-1">
              <CheckCircle className="w-5 h-5" />
              Sign Document
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DigitalSignatures;
