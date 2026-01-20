/**
 * Digital Signatures Page
 * 
 * DocuSign-level e-signature management with:
 * - Signature request creation
 * - Template management
 * - Signing interface
 * - Audit trail viewer
 */

import React, { useState } from 'react';
import {
  FileSignature,
  Plus,
  Send,
  Clock,
  CheckCircle,
  XCircle,
  X,
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

  // Mock data
  const signatureRequests: SignatureRequest[] = [
    {
      id: 1,
      referenceNumber: 'SIG-20260120-A1B2',
      title: 'Safety Policy Acknowledgment',
      description: 'Annual safety policy review and acknowledgment',
      documentType: 'policy',
      status: 'pending',
      workflowType: 'sequential',
      createdAt: new Date('2026-01-20'),
      expiresAt: new Date('2026-02-19'),
      signers: [
        { id: 1, name: 'John Smith', email: 'john@example.com', role: 'Employee', order: 1, status: 'signed', signedAt: new Date() },
        { id: 2, name: 'Sarah Johnson', email: 'sarah@example.com', role: 'Manager', order: 2, status: 'pending' },
        { id: 3, name: 'Mike Wilson', email: 'mike@example.com', role: 'Director', order: 3, status: 'pending' },
      ],
    },
    {
      id: 2,
      referenceNumber: 'SIG-20260119-C3D4',
      title: 'Incident Investigation Report',
      description: 'Final sign-off for incident INC-2026-045',
      documentType: 'report',
      status: 'completed',
      workflowType: 'parallel',
      createdAt: new Date('2026-01-19'),
      expiresAt: new Date('2026-02-18'),
      completedAt: new Date('2026-01-20'),
      signers: [
        { id: 4, name: 'Emily Brown', email: 'emily@example.com', role: 'Investigator', order: 1, status: 'signed', signedAt: new Date() },
        { id: 5, name: 'David Lee', email: 'david@example.com', role: 'Safety Manager', order: 1, status: 'signed', signedAt: new Date() },
      ],
    },
    {
      id: 3,
      referenceNumber: 'SIG-20260118-E5F6',
      title: 'CAPA Closure Approval',
      description: 'Approval to close corrective action CAPA-2025-122',
      documentType: 'capa',
      status: 'declined',
      workflowType: 'sequential',
      createdAt: new Date('2026-01-18'),
      expiresAt: new Date('2026-02-17'),
      signers: [
        { id: 6, name: 'Alex Turner', email: 'alex@example.com', role: 'Quality Manager', order: 1, status: 'declined', declinedAt: new Date() },
      ],
    },
  ];

  const templates: SignatureTemplate[] = [
    {
      id: 1,
      name: 'Policy Acknowledgment',
      description: 'Standard template for policy sign-off',
      signerRoles: [
        { role: 'Employee', order: 1 },
        { role: 'Manager', order: 2 },
      ],
      workflowType: 'sequential',
      expiryDays: 30,
    },
    {
      id: 2,
      name: 'Audit Report Sign-off',
      description: 'Audit report approval workflow',
      signerRoles: [
        { role: 'Auditor', order: 1 },
        { role: 'Audit Manager', order: 2 },
        { role: 'Director', order: 3 },
      ],
      workflowType: 'sequential',
      expiryDays: 14,
    },
    {
      id: 3,
      name: 'Incident Closure',
      description: 'Incident investigation closure approval',
      signerRoles: [
        { role: 'Investigator', order: 1 },
        { role: 'Safety Manager', order: 1 },
      ],
      workflowType: 'parallel',
      expiryDays: 7,
    },
  ];

  const auditLog = [
    { id: 1, action: 'created', actor: 'Admin User', time: new Date('2026-01-20T10:00:00'), details: 'Request created' },
    { id: 2, action: 'sent', actor: 'System', time: new Date('2026-01-20T10:01:00'), details: 'Sent to signers' },
    { id: 3, action: 'viewed', actor: 'John Smith', time: new Date('2026-01-20T10:15:00'), details: 'Document viewed', ip: '192.168.1.100' },
    { id: 4, action: 'signed', actor: 'John Smith', time: new Date('2026-01-20T10:20:00'), details: 'Document signed', ip: '192.168.1.100' },
    { id: 5, action: 'reminded', actor: 'System', time: new Date('2026-01-20T11:00:00'), details: 'Reminder sent to Sarah Johnson' },
  ];

  const getStatusColor = (status: string) => {
    const colors = {
      draft: 'bg-gray-500',
      pending: 'bg-yellow-500',
      in_progress: 'bg-blue-500',
      completed: 'bg-green-500',
      declined: 'bg-red-500',
      expired: 'bg-gray-400',
      viewed: 'bg-blue-400',
      signed: 'bg-green-500',
    };
    return colors[status as keyof typeof colors] || 'bg-gray-500';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
      case 'signed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'declined':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'in_progress':
      case 'viewed':
        return <AlertCircle className="w-4 h-4 text-blue-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const filteredRequests = signatureRequests.filter(req => {
    if (filterStatus !== 'all' && req.status !== filterStatus) return false;
    if (searchQuery && !req.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <FileSignature className="w-8 h-8 text-indigo-400" />
            Digital Signatures
          </h1>
          <p className="text-gray-400 mt-1">
            Secure electronic signatures with legal compliance
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
        >
          <Plus className="w-5 h-5" />
          New Request
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-yellow-500/20 rounded-lg">
              <Clock className="w-6 h-6 text-yellow-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Pending</p>
              <p className="text-2xl font-bold text-white">5</p>
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-500/20 rounded-lg">
              <Send className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">In Progress</p>
              <p className="text-2xl font-bold text-white">3</p>
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-500/20 rounded-lg">
              <CheckCircle className="w-6 h-6 text-green-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Completed</p>
              <p className="text-2xl font-bold text-white">47</p>
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-indigo-500/20 rounded-lg">
              <FileText className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Total Signatures</p>
              <p className="text-2xl font-bold text-white">156</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-700 pb-2">
        {[
          { id: 'requests', label: 'Requests', icon: FileText },
          { id: 'pending', label: 'Awaiting My Signature', icon: PenTool },
          { id: 'templates', label: 'Templates', icon: FileSignature },
          { id: 'audit', label: 'Audit Trail', icon: History },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === tab.id
                ? 'bg-indigo-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
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
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search requests..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-800 text-white pl-10 pr-4 py-2.5 rounded-lg border border-gray-700 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-gray-800 text-white px-4 py-2.5 rounded-lg border border-gray-700 focus:border-indigo-500 focus:outline-none"
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="declined">Declined</option>
              <option value="expired">Expired</option>
            </select>
            <button className="p-2.5 bg-gray-800 text-gray-400 hover:text-white rounded-lg border border-gray-700 transition-colors">
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>

          {/* Requests List */}
          <div className="space-y-4">
            {filteredRequests.map(request => (
              <div
                key={request.id}
                className="bg-gray-800 rounded-xl border border-gray-700 p-5 hover:border-indigo-500/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-medium text-white ${getStatusColor(request.status)}`}>
                        {request.status.replace('_', ' ').toUpperCase()}
                      </span>
                      <span className="text-sm text-gray-400">{request.referenceNumber}</span>
                      <span className="text-sm text-gray-500">•</span>
                      <span className="text-sm text-gray-400">
                        {request.workflowType === 'sequential' ? 'Sequential' : 'Parallel'} signing
                      </span>
                    </div>
                    <h3 className="text-lg font-medium text-white mb-1">{request.title}</h3>
                    {request.description && (
                      <p className="text-sm text-gray-400 mb-3">{request.description}</p>
                    )}
                    
                    {/* Signers */}
                    <div className="flex items-center gap-4 mt-4">
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <Users className="w-4 h-4" />
                        <span>{request.signers.length} signers</span>
                      </div>
                      <div className="flex -space-x-2">
                        {request.signers.map(signer => (
                          <div
                            key={signer.id}
                            className={`w-8 h-8 rounded-full border-2 border-gray-800 flex items-center justify-center text-xs font-medium ${
                              signer.status === 'signed' 
                                ? 'bg-green-600 text-white' 
                                : signer.status === 'declined'
                                ? 'bg-red-600 text-white'
                                : signer.status === 'viewed'
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-600 text-white'
                            }`}
                            title={`${signer.name} - ${signer.status}`}
                          >
                            {signer.name.charAt(0)}
                          </div>
                        ))}
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <Calendar className="w-4 h-4" />
                        <span>Expires {request.expiresAt.toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedRequest(request)}
                      className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
                    >
                      <Eye className="w-5 h-5" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors">
                      <Download className="w-5 h-5" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors">
                      <MoreVertical className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* Signer Progress */}
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <div className="space-y-2">
                    {request.signers.map((signer, index) => (
                      <div key={signer.id} className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-6 h-6 rounded-full bg-gray-700 text-xs text-gray-300">
                          {request.workflowType === 'sequential' ? index + 1 : '•'}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-white">{signer.name}</span>
                            <span className="text-xs text-gray-500">({signer.role})</span>
                          </div>
                          <span className="text-xs text-gray-400">{signer.email}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(signer.status)}
                          <span className="text-sm text-gray-400 capitalize">{signer.status}</span>
                          {signer.signedAt && (
                            <span className="text-xs text-gray-500">
                              {signer.signedAt.toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pending Signatures Tab */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-indigo-900/50 to-purple-900/50 rounded-xl border border-indigo-500/30 p-6">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-indigo-500/20 rounded-xl">
                <PenTool className="w-8 h-8 text-indigo-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-white">2 Documents Awaiting Your Signature</h2>
                <p className="text-gray-400">Review and sign these documents to complete the approval process.</p>
              </div>
            </div>
          </div>

          {signatureRequests
            .filter(r => r.status === 'pending' || r.status === 'in_progress')
            .map(request => (
              <div
                key={request.id}
                className="bg-gray-800 rounded-xl border border-gray-700 p-6"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-white mb-1">{request.title}</h3>
                    <p className="text-sm text-gray-400">{request.description}</p>
                  </div>
                  <span className="text-sm text-gray-400">{request.referenceNumber}</span>
                </div>

                <div className="flex items-center gap-4 mb-6">
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <User className="w-4 h-4" />
                    <span>From: Admin User</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Calendar className="w-4 h-4" />
                    <span>Due: {request.expiresAt.toLocaleDateString()}</span>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setSelectedRequest(request);
                      setShowSigningModal(true);
                    }}
                    className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
                  >
                    <PenTool className="w-4 h-4" />
                    Review & Sign
                  </button>
                  <button className="flex items-center gap-2 px-4 py-2.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                    <Eye className="w-4 h-4" />
                    View Document
                  </button>
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map(template => (
            <div
              key={template.id}
              className="bg-gray-800 rounded-xl border border-gray-700 p-6 hover:border-indigo-500/50 transition-colors"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-indigo-500/20 rounded-lg">
                  <FileSignature className="w-6 h-6 text-indigo-400" />
                </div>
                <div>
                  <h3 className="font-medium text-white">{template.name}</h3>
                  <p className="text-sm text-gray-400">{template.workflowType} workflow</p>
                </div>
              </div>

              {template.description && (
                <p className="text-sm text-gray-400 mb-4">{template.description}</p>
              )}

              <div className="space-y-2 mb-4">
                <p className="text-xs text-gray-500 uppercase">Signing Order</p>
                {template.signerRoles.map((role, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-gray-700 flex items-center justify-center text-xs text-gray-300">
                      {template.workflowType === 'sequential' ? i + 1 : '•'}
                    </span>
                    <span className="text-sm text-gray-300">{role.role}</span>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-gray-700">
                <span className="text-sm text-gray-400">
                  Expires in {template.expiryDays} days
                </span>
                <button className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 text-sm transition-colors">
                  Use Template
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}

          {/* Add Template Card */}
          <div
            className="bg-gray-800/50 rounded-xl border border-dashed border-gray-600 p-6 flex flex-col items-center justify-center cursor-pointer hover:border-indigo-500/50 transition-colors"
          >
            <div className="p-4 bg-gray-700/50 rounded-full mb-4">
              <Plus className="w-8 h-8 text-gray-400" />
            </div>
            <p className="text-gray-400">Create New Template</p>
          </div>
        </div>
      )}

      {/* Audit Trail Tab */}
      {activeTab === 'audit' && (
        <div className="bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-4 border-b border-gray-700">
            <h3 className="text-lg font-medium text-white">Recent Activity</h3>
          </div>
          <div className="divide-y divide-gray-700">
            {auditLog.map(log => (
              <div key={log.id} className="p-4 hover:bg-gray-750 transition-colors">
                <div className="flex items-start gap-4">
                  <div className={`p-2 rounded-lg ${
                    log.action === 'signed' ? 'bg-green-500/20' :
                    log.action === 'viewed' ? 'bg-blue-500/20' :
                    log.action === 'created' ? 'bg-indigo-500/20' :
                    'bg-gray-700'
                  }`}>
                    {log.action === 'signed' && <CheckCircle className="w-5 h-5 text-green-400" />}
                    {log.action === 'viewed' && <Eye className="w-5 h-5 text-blue-400" />}
                    {log.action === 'created' && <Plus className="w-5 h-5 text-indigo-400" />}
                    {log.action === 'sent' && <Send className="w-5 h-5 text-gray-400" />}
                    {log.action === 'reminded' && <Mail className="w-5 h-5 text-yellow-400" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-white">{log.actor}</span>
                      <span className="text-gray-400">{log.action}</span>
                    </div>
                    <p className="text-sm text-gray-400">{log.details}</p>
                    {log.ip && (
                      <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                        <MapPin className="w-3 h-3" />
                        <span>IP: {log.ip}</span>
                      </div>
                    )}
                  </div>
                  <div className="text-sm text-gray-500">
                    {log.time.toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Request Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 w-full max-w-lg mx-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-white">Create Signature Request</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-gray-400 mb-4">Create a new document for signature collection.</p>
            <div className="text-center py-8 text-gray-500">
              <FileSignature className="w-12 h-12 mx-auto mb-3 text-gray-600" />
              <p>Coming soon: Full document upload and signer configuration</p>
            </div>
            <div className="flex justify-end gap-3 mt-4">
              <button 
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

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
      ctx.strokeStyle = '#4f46e5';
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
    // Submit signature
    console.log('Signing document...');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Sign Document</h2>
              <p className="text-sm text-gray-400">{request.title}</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
            >
              <XCircle className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Document Preview */}
          <div className="bg-gray-900 rounded-lg p-4 mb-6 border border-gray-700">
            <div className="flex items-center gap-3 mb-3">
              <FileText className="w-5 h-5 text-gray-400" />
              <span className="text-white font-medium">Document Preview</span>
            </div>
            <div className="bg-white rounded-lg p-6 min-h-[200px] text-gray-800">
              <h3 className="font-bold mb-4">{request.title}</h3>
              <p className="text-sm text-gray-600 mb-4">{request.description}</p>
              <p className="text-sm text-gray-600">
                This document requires your electronic signature to indicate your acknowledgment and agreement 
                to the terms outlined above. By signing, you confirm that you have read and understood the contents.
              </p>
            </div>
          </div>

          {/* Signature Type Selection */}
          <div className="mb-6">
            <p className="text-sm text-gray-400 mb-3">Choose how to sign:</p>
            <div className="flex gap-3">
              {[
                { id: 'draw', label: 'Draw', icon: PenTool },
                { id: 'type', label: 'Type', icon: FileText },
                { id: 'upload', label: 'Upload', icon: FileSignature },
              ].map(option => (
                <button
                  key={option.id}
                  onClick={() => setSignatureType(option.id as any)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
                    signatureType === option.id
                      ? 'border-indigo-500 bg-indigo-500/20 text-indigo-400'
                      : 'border-gray-600 text-gray-400 hover:border-gray-500'
                  }`}
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
                  <p className="text-sm text-gray-400">Draw your signature below:</p>
                  <button
                    onClick={clearCanvas}
                    className="text-sm text-indigo-400 hover:text-indigo-300"
                  >
                    Clear
                  </button>
                </div>
                <canvas
                  ref={canvasRef}
                  width={540}
                  height={150}
                  className="w-full bg-white rounded-lg cursor-crosshair border-2 border-dashed border-gray-300"
                  onMouseDown={startDrawing}
                  onMouseMove={draw}
                  onMouseUp={stopDrawing}
                  onMouseLeave={stopDrawing}
                />
              </div>
            )}
            
            {signatureType === 'type' && (
              <div>
                <p className="text-sm text-gray-400 mb-2">Type your name:</p>
                <input
                  type="text"
                  value={typedName}
                  onChange={(e) => setTypedName(e.target.value)}
                  placeholder="Enter your full name"
                  className="w-full bg-gray-900 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-indigo-500 focus:outline-none"
                />
                {typedName && (
                  <div className="mt-4 p-4 bg-white rounded-lg">
                    <p className="text-2xl text-indigo-600 font-script">{typedName}</p>
                  </div>
                )}
              </div>
            )}

            {signatureType === 'upload' && (
              <div className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center">
                <FileSignature className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400 mb-2">Drag and drop your signature image</p>
                <p className="text-sm text-gray-500">or</p>
                <button className="mt-2 px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors">
                  Browse Files
                </button>
              </div>
            )}
          </div>

          {/* Legal Agreement */}
          <div className="bg-gray-900 rounded-lg p-4 mb-6 border border-gray-700">
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                id="agree"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="mt-1"
              />
              <label htmlFor="agree" className="text-sm text-gray-300">
                By signing this document electronically, I agree that my electronic signature is the legal 
                equivalent of my manual signature. I consent to the use of electronic signatures, and I 
                understand that I am legally bound by this agreement.
              </label>
            </div>
          </div>

          {/* Verification Info */}
          <div className="flex items-center gap-4 text-sm text-gray-400 mb-6">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-green-400" />
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
            <button
              onClick={onClose}
              className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSign}
              disabled={!agreedToTerms}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              <CheckCircle className="w-5 h-5" />
              Sign Document
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DigitalSignatures;
