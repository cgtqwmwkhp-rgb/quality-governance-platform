import { useState } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  Mail,
  Phone,
  Building,
  Search,
  MoreVertical,
  Edit,
  Trash2,
  Lock,
  Unlock,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  X,
  Save,
  AlertTriangle
} from 'lucide-react';

interface User {
  id: string;
  name: string;
  email: string;
  phone?: string;
  department: string;
  role: string;
  status: 'active' | 'inactive' | 'pending';
  lastLogin?: string;
  createdAt: string;
  permissions: string[];
}

interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  userCount: number;
  color: string;
}

export default function UserManagement() {
  const [activeTab, setActiveTab] = useState<'users' | 'roles'>('users');
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [_selectedUser] = useState<User | null>(null); void _selectedUser;

  const users: User[] = [
    {
      id: 'USR001',
      name: 'John Smith',
      email: 'john.smith@company.com',
      phone: '+44 7700 900123',
      department: 'Operations',
      role: 'Admin',
      status: 'active',
      lastLogin: '2024-01-19 09:45',
      createdAt: '2023-06-15',
      permissions: ['all']
    },
    {
      id: 'USR002',
      name: 'Sarah Johnson',
      email: 'sarah.johnson@company.com',
      department: 'Quality',
      role: 'Manager',
      status: 'active',
      lastLogin: '2024-01-19 08:30',
      createdAt: '2023-08-20',
      permissions: ['incidents.manage', 'audits.manage', 'reports.view']
    },
    {
      id: 'USR003',
      name: 'Mike Chen',
      email: 'mike.chen@company.com',
      department: 'Fleet',
      role: 'Supervisor',
      status: 'active',
      lastLogin: '2024-01-18 17:20',
      createdAt: '2023-09-10',
      permissions: ['rtas.manage', 'incidents.view', 'actions.manage']
    },
    {
      id: 'USR004',
      name: 'Emma Wilson',
      email: 'emma.wilson@company.com',
      department: 'Customer Service',
      role: 'User',
      status: 'inactive',
      lastLogin: '2024-01-10 14:00',
      createdAt: '2023-10-05',
      permissions: ['complaints.view', 'complaints.create']
    },
    {
      id: 'USR005',
      name: 'David Brown',
      email: 'david.brown@company.com',
      department: 'Safety',
      role: 'Manager',
      status: 'pending',
      createdAt: '2024-01-15',
      permissions: ['incidents.manage', 'risks.manage', 'actions.manage']
    }
  ];

  const roles: Role[] = [
    {
      id: 'ROLE001',
      name: 'Admin',
      description: 'Full system access with user management capabilities',
      permissions: ['all'],
      userCount: 2,
      color: 'from-red-500 to-rose-500'
    },
    {
      id: 'ROLE002',
      name: 'Manager',
      description: 'Department-level access with reporting capabilities',
      permissions: ['incidents.manage', 'audits.manage', 'reports.view', 'risks.manage'],
      userCount: 8,
      color: 'from-violet-500 to-purple-500'
    },
    {
      id: 'ROLE003',
      name: 'Supervisor',
      description: 'Team-level access with limited management rights',
      permissions: ['incidents.view', 'rtas.manage', 'actions.manage'],
      userCount: 15,
      color: 'from-blue-500 to-cyan-500'
    },
    {
      id: 'ROLE004',
      name: 'User',
      description: 'Basic access for viewing and creating records',
      permissions: ['*.view', '*.create'],
      userCount: 45,
      color: 'from-emerald-500 to-green-500'
    },
    {
      id: 'ROLE005',
      name: 'Auditor',
      description: 'Read-only access to all modules for audit purposes',
      permissions: ['*.view', 'reports.view', 'audit-trail.view'],
      userCount: 5,
      color: 'from-amber-500 to-orange-500'
    }
  ];

  // Permissions list available for role configuration
  const _permissions = [
    { id: 'incidents', name: 'Incidents', actions: ['view', 'create', 'edit', 'delete', 'manage'] },
    { id: 'rtas', name: 'RTAs', actions: ['view', 'create', 'edit', 'delete', 'manage'] },
    { id: 'complaints', name: 'Complaints', actions: ['view', 'create', 'edit', 'delete', 'manage'] },
    { id: 'risks', name: 'Risks', actions: ['view', 'create', 'edit', 'delete', 'manage'] },
    { id: 'audits', name: 'Audits', actions: ['view', 'create', 'edit', 'delete', 'manage'] },
    { id: 'actions', name: 'Actions', actions: ['view', 'create', 'edit', 'delete', 'manage'] },
    { id: 'documents', name: 'Documents', actions: ['view', 'upload', 'edit', 'delete', 'manage'] },
    { id: 'reports', name: 'Reports', actions: ['view', 'create', 'export'] },
    { id: 'users', name: 'Users', actions: ['view', 'create', 'edit', 'delete', 'manage'] }
  ];
  void _permissions; // Used for role configuration UI

  const statusColors: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
    active: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', icon: <CheckCircle2 className="w-4 h-4" /> },
    inactive: { bg: 'bg-slate-500/20', text: 'text-slate-400', icon: <XCircle className="w-4 h-4" /> },
    pending: { bg: 'bg-amber-500/20', text: 'text-amber-400', icon: <Clock className="w-4 h-4" /> }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          user.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRole = selectedRole === 'all' || user.role === selectedRole;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl">
              <Users className="w-8 h-8" />
            </div>
            User Management
          </h1>
          <p className="text-slate-400 mt-1">Manage users, roles, and permissions</p>
        </div>
        
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-medium rounded-xl hover:from-violet-500 hover:to-purple-500 transition-all flex items-center gap-2"
        >
          <UserPlus className="w-5 h-5" />
          Add User
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700/50">
        <button
          onClick={() => setActiveTab('users')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'users'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Users ({users.length})
          </span>
        </button>
        <button
          onClick={() => setActiveTab('roles')}
          className={`px-6 py-3 font-medium transition-all border-b-2 ${
            activeTab === 'roles'
              ? 'text-violet-400 border-violet-400'
              : 'text-slate-400 border-transparent hover:text-white'
          }`}
        >
          <span className="flex items-center gap-2">
            <Shield className="w-5 h-5" />
            Roles ({roles.length})
          </span>
        </button>
      </div>

      {/* Users Tab */}
      {activeTab === 'users' && (
        <>
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search users..."
                className="w-full pl-10 pr-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500"
              />
            </div>
            
            <div className="relative">
              <select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
                className="appearance-none pl-4 pr-10 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                <option value="all">All Roles</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.name}>{role.name}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Users Table */}
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-900/50">
                  <tr>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">User</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Department</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Role</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Status</th>
                    <th className="text-left p-4 text-sm font-medium text-slate-400">Last Login</th>
                    <th className="text-center p-4 text-sm font-medium text-slate-400">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user) => (
                    <tr
                      key={user.id}
                      className="border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors"
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-semibold">
                            {user.name.split(' ').map(n => n[0]).join('')}
                          </div>
                          <div>
                            <p className="font-medium text-white">{user.name}</p>
                            <p className="text-sm text-slate-400">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="flex items-center gap-2 text-slate-300">
                          <Building className="w-4 h-4 text-slate-500" />
                          {user.department}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className="px-3 py-1 bg-violet-500/20 text-violet-400 rounded-full text-sm font-medium">
                          {user.role}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${statusColors[user.status].bg} ${statusColors[user.status].text}`}>
                          {statusColors[user.status].icon}
                          {user.status.charAt(0).toUpperCase() + user.status.slice(1)}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 text-sm">
                        {user.lastLogin || 'Never'}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            className="p-2 text-slate-400 hover:text-violet-400 transition-colors"
                            title="Edit User"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            className="p-2 text-slate-400 hover:text-amber-400 transition-colors"
                            title={user.status === 'active' ? 'Deactivate' : 'Activate'}
                          >
                            {user.status === 'active' ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                          </button>
                          <button
                            className="p-2 text-slate-400 hover:text-red-400 transition-colors"
                            title="Delete User"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Roles Tab */}
      {activeTab === 'roles' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {roles.map((role) => (
            <div
              key={role.id}
              className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6 hover:border-violet-500/50 transition-all"
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl bg-gradient-to-br ${role.color}`}>
                  <Shield className="w-6 h-6 text-white" />
                </div>
                <button className="p-2 text-slate-400 hover:text-white transition-colors">
                  <MoreVertical className="w-5 h-5" />
                </button>
              </div>
              
              <h3 className="text-xl font-semibold text-white mb-2">{role.name}</h3>
              <p className="text-sm text-slate-400 mb-4">{role.description}</p>
              
              <div className="flex items-center justify-between pt-4 border-t border-slate-700/50">
                <span className="text-sm text-slate-400">
                  <span className="text-white font-medium">{role.userCount}</span> users
                </span>
                <span className="text-sm text-slate-400">
                  <span className="text-white font-medium">{role.permissions.length}</span> permissions
                </span>
              </div>
              
              <div className="mt-4 flex flex-wrap gap-2">
                {role.permissions.slice(0, 3).map((perm, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 bg-slate-700/50 text-slate-300 rounded text-xs"
                  >
                    {perm}
                  </span>
                ))}
                {role.permissions.length > 3 && (
                  <span className="px-2 py-1 bg-violet-500/20 text-violet-400 rounded text-xs">
                    +{role.permissions.length - 3} more
                  </span>
                )}
              </div>
            </div>
          ))}
          
          {/* Add New Role Card */}
          <button className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-dashed border-slate-700 p-6 flex flex-col items-center justify-center gap-3 hover:border-violet-500/50 hover:bg-slate-800/50 transition-all min-h-[200px]">
            <div className="p-3 rounded-xl bg-slate-700/50">
              <Shield className="w-6 h-6 text-slate-400" />
            </div>
            <span className="text-slate-400 font-medium">Create New Role</span>
          </button>
        </div>
      )}

      {/* Add User Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-2xl border border-slate-700 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-700 flex items-center justify-between sticky top-0 bg-slate-800">
              <h2 className="text-xl font-semibold text-white">Add New User</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="p-2 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">First Name</label>
                  <input
                    type="text"
                    className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="John"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Last Name</label>
                  <input
                    type="text"
                    className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="Smith"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                  <input
                    type="email"
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="john.smith@company.com"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Phone (Optional)</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                  <input
                    type="tel"
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="+44 7700 900000"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Department</label>
                  <select className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    <option>Operations</option>
                    <option>Quality</option>
                    <option>Fleet</option>
                    <option>Safety</option>
                    <option>Customer Service</option>
                    <option>HR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Role</label>
                  <select className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    {roles.map((role) => (
                      <option key={role.id}>{role.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-amber-200">
                  An email will be sent to the user with instructions to set their password and complete account setup.
                </p>
              </div>
            </div>
            
            <div className="p-6 border-t border-slate-700 flex justify-end gap-3 sticky bottom-0 bg-slate-800">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button className="px-6 py-2 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-medium rounded-xl hover:from-violet-500 hover:to-purple-500 transition-all flex items-center gap-2">
                <Save className="w-5 h-5" />
                Create User
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
