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
  Save,
  AlertTriangle
} from 'lucide-react';
import { cn } from "../helpers/utils";
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/Dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/Select';

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
      color: 'from-destructive to-destructive/80'
    },
    {
      id: 'ROLE002',
      name: 'Manager',
      description: 'Department-level access with reporting capabilities',
      permissions: ['incidents.manage', 'audits.manage', 'reports.view', 'risks.manage'],
      userCount: 8,
      color: 'from-primary to-primary-hover'
    },
    {
      id: 'ROLE003',
      name: 'Supervisor',
      description: 'Team-level access with limited management rights',
      permissions: ['incidents.view', 'rtas.manage', 'actions.manage'],
      userCount: 15,
      color: 'from-info to-info/80'
    },
    {
      id: 'ROLE004',
      name: 'User',
      description: 'Basic access for viewing and creating records',
      permissions: ['*.view', '*.create'],
      userCount: 45,
      color: 'from-success to-success/80'
    },
    {
      id: 'ROLE005',
      name: 'Auditor',
      description: 'Read-only access to all modules for audit purposes',
      permissions: ['*.view', 'reports.view', 'audit-trail.view'],
      userCount: 5,
      color: 'from-warning to-warning/80'
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

  const statusConfig: Record<string, { variant: 'resolved' | 'submitted' | 'destructive'; icon: React.ReactNode }> = {
    active: { variant: 'resolved', icon: <CheckCircle2 className="w-4 h-4" /> },
    inactive: { variant: 'destructive', icon: <XCircle className="w-4 h-4" /> },
    pending: { variant: 'submitted', icon: <Clock className="w-4 h-4" /> }
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
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-primary to-primary-hover rounded-xl">
              <Users className="w-8 h-8 text-primary-foreground" />
            </div>
            User Management
          </h1>
          <p className="text-muted-foreground mt-1">Manage users, roles, and permissions</p>
        </div>
        
        <Button onClick={() => setShowAddModal(true)}>
          <UserPlus className="w-5 h-5" />
          Add User
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('users')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'users'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Users ({users.length})
          </span>
        </button>
        <button
          onClick={() => setActiveTab('roles')}
          className={cn(
            "px-6 py-3 font-medium transition-all border-b-2",
            activeTab === 'roles'
              ? 'text-primary border-primary'
              : 'text-muted-foreground border-transparent hover:text-foreground'
          )}
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
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search users..."
                className="pl-10"
              />
            </div>
            
            <Select value={selectedRole} onValueChange={setSelectedRole}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="All Roles" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                {roles.map((role) => (
                  <SelectItem key={role.id} value={role.name}>{role.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Users Table */}
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">User</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Department</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Role</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Last Login</th>
                    <th className="text-center p-4 text-sm font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user) => (
                    <tr
                      key={user.id}
                      className="border-b border-border hover:bg-muted/30 transition-colors"
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-hover flex items-center justify-center text-primary-foreground font-semibold">
                            {user.name.split(' ').map(n => n[0]).join('')}
                          </div>
                          <div>
                            <p className="font-medium text-foreground">{user.name}</p>
                            <p className="text-sm text-muted-foreground">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="flex items-center gap-2 text-foreground">
                          <Building className="w-4 h-4 text-muted-foreground" />
                          {user.department}
                        </span>
                      </td>
                      <td className="p-4">
                        <Badge variant="default">
                          {user.role}
                        </Badge>
                      </td>
                      <td className="p-4">
                        <Badge variant={statusConfig[user.status].variant} className="flex items-center gap-1 w-fit">
                          {statusConfig[user.status].icon}
                          {user.status.charAt(0).toUpperCase() + user.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="p-4 text-muted-foreground text-sm">
                        {user.lastLogin || 'Never'}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-center gap-2">
                          <Button variant="ghost" size="sm" title="Edit User">
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            title={user.status === 'active' ? 'Deactivate' : 'Activate'}
                          >
                            {user.status === 'active' ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                          </Button>
                          <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" title="Delete User">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {/* Roles Tab */}
      {activeTab === 'roles' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {roles.map((role) => (
            <Card
              key={role.id}
              className="hover:border-primary/50 transition-all"
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className={cn("p-3 rounded-xl bg-gradient-to-br", role.color)}>
                    <Shield className="w-6 h-6 text-white" />
                  </div>
                  <Button variant="ghost" size="sm">
                    <MoreVertical className="w-5 h-5" />
                  </Button>
                </div>
                
                <h3 className="text-xl font-semibold text-foreground mb-2">{role.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">{role.description}</p>
                
                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <span className="text-sm text-muted-foreground">
                    <span className="text-foreground font-medium">{role.userCount}</span> users
                  </span>
                  <span className="text-sm text-muted-foreground">
                    <span className="text-foreground font-medium">{role.permissions.length}</span> permissions
                  </span>
                </div>
                
                <div className="mt-4 flex flex-wrap gap-2">
                  {role.permissions.slice(0, 3).map((perm, i) => (
                    <span
                      key={i}
                      className="px-2 py-1 bg-muted text-muted-foreground rounded text-xs"
                    >
                      {perm}
                    </span>
                  ))}
                  {role.permissions.length > 3 && (
                    <Badge variant="default" className="text-xs">
                      +{role.permissions.length - 3} more
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
          
          {/* Add New Role Card */}
          <button className="bg-card/30 rounded-xl border border-dashed border-border p-6 flex flex-col items-center justify-center gap-3 hover:border-primary/50 hover:bg-card/50 transition-all min-h-[200px]">
            <div className="p-3 rounded-xl bg-muted">
              <Shield className="w-6 h-6 text-muted-foreground" />
            </div>
            <span className="text-muted-foreground font-medium">Create New Role</span>
          </button>
        </div>
      )}

      {/* Add User Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add New User</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">First Name</label>
                <Input type="text" placeholder="John" />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Last Name</label>
                <Input type="text" placeholder="Smith" />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-2">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  type="email"
                  className="pl-10"
                  placeholder="john.smith@company.com"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-2">Phone (Optional)</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  type="tel"
                  className="pl-10"
                  placeholder="+44 7700 900000"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Department</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="operations">Operations</SelectItem>
                    <SelectItem value="quality">Quality</SelectItem>
                    <SelectItem value="fleet">Fleet</SelectItem>
                    <SelectItem value="safety">Safety</SelectItem>
                    <SelectItem value="customer-service">Customer Service</SelectItem>
                    <SelectItem value="hr">HR</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Role</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map((role) => (
                      <SelectItem key={role.id} value={role.name.toLowerCase()}>{role.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div className="p-4 bg-warning/10 border border-warning/30 rounded-xl flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
              <p className="text-sm text-warning">
                An email will be sent to the user with instructions to set their password and complete account setup.
              </p>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button>
              <Save className="w-5 h-5" />
              Create User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
