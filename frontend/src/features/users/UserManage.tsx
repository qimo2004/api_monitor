import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Table, Button, Space, Tag, Drawer, Form, Input, Select, Switch,
  message, Popconfirm, Tooltip,
} from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { authApi, type UserInfo, type UserCreate, type UserUpdate } from '../auth/api';
import { useAuthStore } from '../auth/store';

const roleColors: Record<string, string> = { admin: 'red', operator: 'blue', viewer: 'green' };
const roleLabels: Record<string, string> = { admin: '管理员', operator: '操作员', viewer: '观察者' };

export default function UserManage() {
  const currentUser = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const isAdmin = currentUser?.role === 'admin';

  const [data, setData] = useState<UserInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<UserInfo | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authApi.listUsers(page, 20);
      setData(res.items || []);
      setTotal(res.total || 0);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openCreate = () => {
    setEditItem(null);
    form.resetFields();
    form.setFieldsValue({ role: 'operator', enabled: true });
    setDrawerOpen(true);
  };

  const openEdit = (item: UserInfo) => {
    setEditItem(item);
    form.setFieldsValue({
      username: item.username,
      display_name: item.display_name,
      role: item.role,
      email: item.email,
      enabled: item.enabled,
    });
    form.resetFields(['password']);
    setDrawerOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await authApi.deleteUser(id);
      message.success('删除成功');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggleEnabled = async (record: UserInfo, checked: boolean) => {
    try {
      await authApi.updateUser(record.id, { enabled: checked });
      message.success(checked ? '已启用' : '已停用');
      fetchList();
    } catch {
      message.error('操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      if (editItem) {
        const payload: UserUpdate = {
          display_name: values.display_name,
          role: values.role,
          email: values.email,
          enabled: values.enabled,
          password: values.password || undefined,
        };
        await authApi.updateUser(editItem.id, payload);
        message.success('更新成功');
      } else {
        await authApi.createUser(values as UserCreate);
        message.success('创建成功');
      }
      setDrawerOpen(false);
      fetchList();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isAdmin) {
    navigate('/dashboard', { replace: true });
    return null;
  }

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 120,
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 140,
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (role: string) => (
        <Tag color={roleColors[role] || 'default'}>{roleLabels[role] || role}</Tag>
      ),
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      width: 200,
      render: (email?: string) => email || '-',
    },
    {
      title: '启用状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (_: boolean, record: UserInfo) => (
        <Switch
          checked={record.enabled}
          onChange={(checked) => handleToggleEnabled(record, checked)}
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) => val ? new Date(val).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: UserInfo) => (
        <Space>
          <Tooltip title="编辑">
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title={`确定删除用户 ${record.username}？此操作不可恢复`}
            onConfirm={() => handleDelete(record.id)}
          >
            <Tooltip title="删除">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="用户管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增用户
        </Button>
      }
    >
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
      </Space>

      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={loading}
        onRow={(record) => ({
          onClick: (e) => {
            // 点击按钮/链接等交互元素时不触发跳转
            if ((e.target as HTMLElement).closest('button, a, input, .ant-select, .ant-switch, .ant-popconfirm, .ant-dropdown-trigger')) return;
            if (record.role === 'operator') {
              navigate(`/users/${record.id}/auth-apis`);
            }
          },
          style: record.role === 'operator' ? { cursor: 'pointer' } : undefined,
        })}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 条`,
        }}
        scroll={{ x: 800 }}
      />

      <Drawer
        title={editItem ? '编辑用户' : '新增用户'}
        size="middle"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Button type="primary" onClick={handleSubmit} loading={submitting}>
            {editItem ? '更新' : '创建'}
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: !editItem, message: '请输入用户名' }]}
          >
            <Input disabled={!!editItem} placeholder="请输入用户名" />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={editItem ? [] : [{ required: true, message: '请输入密码' }, { min: 6, message: '密码长度至少6位' }]}
          >
            <Input.Password
              key={editItem ? 'edit-pwd' : 'create-pwd'}
              placeholder={editItem ? '留空则不修改密码' : '请输入密码'}
              autoComplete="off"
            />
          </Form.Item>

          <Form.Item
            name="display_name"
            label="显示名称"
            rules={[{ required: true, message: '请输入显示名称' }]}
          >
            <Input placeholder="请输入显示名称" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="请选择角色">
              <Select.Option value="admin">管理员</Select.Option>
              <Select.Option value="operator">操作员</Select.Option>
              <Select.Option value="viewer">观察者</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="email" label="邮箱">
            <Input placeholder="请输入邮箱（可选）" />
          </Form.Item>

          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </Card>
  );
}
