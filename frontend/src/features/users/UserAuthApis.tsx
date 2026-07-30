import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Table, Button, Space, Tag, message, Popconfirm, Tooltip } from 'antd';
import { ArrowLeftOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import client from '../../shared/client';

interface AuthorizedApi {
  id: number;
  api_id: number;
  name: string;
  url: string;
  method: string;
  group_name?: string;
  enabled: boolean;
  status: string;
}

const methodColors: Record<string, string> = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' };
const statusLabels: Record<string, { color: string; text: string }> = {
  healthy: { color: 'green', text: '健康' },
  down: { color: 'red', text: '故障' },
  unknown: { color: 'default', text: '未知' },
};

export default function UserAuthApis() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<AuthorizedApi[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [username, setUsername] = useState('');

  const fetchList = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const res = await client.get(`/api/users/${userId}/authorized-apis`).then(r => r.data);
      setData(res.items || []);
      // 获取用户名
      const usersRes = await client.get('/api/users', { params: { page: 1, page_size: 200 } }).then(r => r.data);
      const user = (usersRes.items || []).find((u: any) => u.id === Number(userId));
      setUsername(user?.display_name || user?.username || '');
    } catch {
      message.error('加载授权数据失败');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) { message.warning('请先选择要取消的授权'); return; }
    try {
      await client.post('/api/authorizations/batch-delete', { ids: selectedRowKeys }).then(r => r.data);
      message.success(`已取消 ${selectedRowKeys.length} 条授权`);
      setSelectedRowKeys([]);
      fetchList();
    } catch {
      message.error('取消授权失败');
    }
  };

  const handleSingleDelete = async (record: AuthorizedApi) => {
    try {
      await client.post('/api/authorizations/batch-delete', { ids: [record.id] }).then(r => r.data);
      message.success('已取消授权');
      fetchList();
    } catch {
      message.error('取消授权失败');
    }
  };

  const columns = [
    {
      title: '接口名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      width: 300,
      ellipsis: true,
      render: (v: string) => <Tooltip title={v}><span>{v}</span></Tooltip>,
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 80,
      render: (v: string) => <Tag color={methodColors[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '分组',
      dataIndex: 'group_name',
      key: 'group_name',
      width: 120,
      render: (v?: string) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => {
        const info = statusLabels[v] || { color: 'default', text: v };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: AuthorizedApi) => (
        <Popconfirm
          title={`确定取消对接口"${record.name}"的授权？`}
          onConfirm={() => handleSingleDelete(record)}
        >
          <Tooltip title="取消授权">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} size="small" onClick={() => navigate('/users')} />
          <span>{username} - 授权接口列表</span>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
        </Space>
      }
    >
      {selectedRowKeys.length > 0 && (
        <Space style={{ marginBottom: 16 }}>
          <Popconfirm
            title={`确定取消 ${selectedRowKeys.length} 条授权？`}
            description="取消后该运维人员将无法查看和管理这些接口"
            onConfirm={handleBatchDelete}
          >
            <Button type="primary" danger icon={<DeleteOutlined />}>
              取消授权 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        </Space>
      )}
      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={loading}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条授权` }}
        scroll={{ x: 900 }}
      />
    </Card>
  );
}
