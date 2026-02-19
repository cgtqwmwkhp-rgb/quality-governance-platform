import { useState, useEffect, useCallback } from 'react';
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
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { cn } from "../helpers/utils";
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/Dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/Select';
import { usersApi } from '../api/client';
import type { UserDetail, RoleDetail } from '../api/client';

/* eslint-disable @typescript-eslint/no-empty-interface */

export default function UserManagement() {
  const [activeTab, setActiveTab] = useState<'users' | 'roles'>('users');
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [users, setUsers] = useState<UserDetail[]>([]);
  const [roles, setRoles] = useState<RoleDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newUser, setNewUser] = useState({ firstName: '', lastName: '', email: '', phone: '', department: '', role: '' });

  const ROLE_COLORS: Record<string, string> = {
    Admin: 'from-destructive to-destructive/80',
    Manager: 'from-primary to-primary-hover',
    Supervisor: 'from-info to-info/80',
    User: 'from-success to-success/80',
    Auditor: 'from-warning to-warning/80',
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [usersRes, rolesRes] = await Promise.all([
        usersApi.list(1, 100),
        usersApi.listRoles(),
      ]);
      setUsers(usersRes.data?.items || []);
      setRoles(rolesRes.data || []);
    } catch {
      console.error('Failed to load users/roles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCreateUser = async () => {
    if (!newUser.email || !newUser.firstName || !newUser.lastName) return;
    setSaving(true);
    try {
      const roleObj = roles.find(r => r.name.toLowerCase() === newUser.role);
      await usersApi.create({
        email: newUser.email,
        password: 'TempPass123!',
        first_name: newUser.firstName,
        last_name: newUser.lastName,
        phone: newUser.phone || undefined,
        department: newUser.department || undefined,
        role_ids: roleObj ? [roleObj.id] : [],
      });
      setShowAddModal(false);
      setNewUser({ firstName: '', lastName: '', email: '', phone: '', department: '', role: '' });
      await loadData();
    } catch {
      console.error('Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (user: UserDetail) => {
    try {
      await usersApi.update(user.id, { is_active: !user.is_active });
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
    } catch {
      console.error('Failed to toggle user');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('Are you sure you want to deactivate this user?')) return;
    try {
      await usersApi.delete(userId);
      setUsers(prev => prev.filter(u => u.id !== userId));
    } catch {
      console.error('Failed to delete user');
    }
  };

  const statusConfig: Record<string, { variant: 'resolved' | 'submitted' | 'destructive'; icon: React.ReactNode }> = {
    active: { variant: 'resolved', icon: <CheckCircle2 className="w-4 h-4" /> },
    inactive: { variant: 'destructive', icon: <XCircle className="w-4 h-4" /> },
    pending: { variant: 'submitted', icon: <Clock className="w-4 h-4" /> }
  };

  const getUserStatus = (user: UserDetail): 'active' | 'inactive' | 'pending' => {
    if (!user.is_active) return 'inactive';
    return 'active';
  };

  const getUserRoleName = (user: UserDetail) => user.roles?.[0]?.name || 'User';

  const filteredUsers = users.filter(user => {
    const fullName = user.full_name || `${user.first_name} ${user.last_name}`;
    const matchesSearch = fullName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          user.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRole = selectedRole === 'all' || getUserRoleName(user) === selectedRole;
    return matchesSearch && matchesRole;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

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
            Users ({filteredUsers.length})
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
                  {filteredUsers.map((user) => {
                    const displayName = user.full_name || `${user.first_name} ${user.last_name}`;
                    const initials = displayName.split(' ').map(n => n[0]).join('').toUpperCase();
                    const status = getUserStatus(user);
                    const roleName = getUserRoleName(user);
                    return (
                    <tr
                      key={user.id}
                      className="border-b border-border hover:bg-muted/30 transition-colors"
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-hover flex items-center justify-center text-primary-foreground font-semibold">
                            {initials}
                          </div>
                          <div>
                            <p className="font-medium text-foreground">{displayName}</p>
                            <p className="text-sm text-muted-foreground">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="flex items-center gap-2 text-foreground">
                          <Building className="w-4 h-4 text-muted-foreground" />
                          {user.department || '—'}
                        </span>
                      </td>
                      <td className="p-4">
                        <Badge variant="default">
                          {roleName}
                        </Badge>
                      </td>
                      <td className="p-4">
                        <Badge variant={statusConfig[status].variant} className="flex items-center gap-1 w-fit">
                          {statusConfig[status].icon}
                          {status.charAt(0).toUpperCase() + status.slice(1)}
                        </Badge>
                      </td>
                      <td className="p-4 text-muted-foreground text-sm">
                        {user.last_login || 'Never'}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-center gap-2">
                          <Button variant="ghost" size="sm" title="Edit User">
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            title={user.is_active ? 'Deactivate' : 'Activate'}
                            onClick={() => handleToggleActive(user)}
                          >
                            {user.is_active ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                          </Button>
                          <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" title="Delete User" onClick={() => handleDeleteUser(user.id)}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {/* Roles Tab */}
      {activeTab === 'roles' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {roles.map((role) => {
            const color = ROLE_COLORS[role.name] || 'from-muted to-muted/80';
            const roleUserCount = users.filter(u => u.roles?.some(r => r.id === role.id)).length;
            return (
            <Card
              key={role.id}
              className="hover:border-primary/50 transition-all"
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className={cn("p-3 rounded-xl bg-gradient-to-br", color)}>
                    <Shield className="w-6 h-6 text-white" />
                  </div>
                  <Button variant="ghost" size="sm">
                    <MoreVertical className="w-5 h-5" />
                  </Button>
                </div>
                
                <h3 className="text-xl font-semibold text-foreground mb-2">{role.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">{role.description || 'No description'}</p>
                
                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <span className="text-sm text-muted-foreground">
                    <span className="text-foreground font-medium">{roleUserCount}</span> users
                  </span>
                  <span className="text-sm text-muted-foreground">
                    <span className="text-foreground font-medium">{role.permissions?.length || 0}</span> permissions
                  </span>
                </div>
                
                <div className="mt-4 flex flex-wrap gap-2">
                  {(role.permissions || []).slice(0, 3).map((perm, i) => (
                    <span
                      key={i}
                      className="px-2 py-1 bg-muted text-muted-foreground rounded text-xs"
                    >
                      {perm}
                    </span>
                  ))}
                  {(role.permissions?.length || 0) > 3 && (
                    <Badge variant="default" className="text-xs">
                      +{role.permissions.length - 3} more
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
            );
          })}
          
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
                <Input type="text" placeholder="John" value={newUser.firstName} onChange={(e) => setNewUser(p => ({ ...p, firstName: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Last Name</label>
                <Input type="text" placeholder="Smith" value={newUser.lastName} onChange={(e) => setNewUser(p => ({ ...p, lastName: e.target.value }))} />
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
                  value={newUser.email}
                  onChange={(e) => setNewUser(p => ({ ...p, email: e.target.value }))}
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
                  value={newUser.phone}
                  onChange={(e) => setNewUser(p => ({ ...p, phone: e.target.value }))}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Department</label>
                <Select value={newUser.department} onValueChange={(v) => setNewUser(p => ({ ...p, department: v }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Operations">Operations</SelectItem>
                    <SelectItem value="Quality">Quality</SelectItem>
                    <SelectItem value="Fleet">Fleet</SelectItem>
                    <SelectItem value="Safety">Safety</SelectItem>
                    <SelectItem value="Customer Service">Customer Service</SelectItem>
                    <SelectItem value="HR">HR</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Role</label>
                <Select value={newUser.role} onValueChange={(v) => setNewUser(p => ({ ...p, role: v }))}>
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
            <Button onClick={handleCreateUser} disabled={saving}>
              {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
              Create User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
