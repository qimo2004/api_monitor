import { useEffect, useState, useCallback } from 'react';
import { Card, Table, Select, Tag, Button, Space, Statistic, Row, Col, message, Tooltip } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { alertApi, type AlertItem } from './api';
import { apiApi, type ApiItem } from '../apis/api';
import { useAlertStore } from './store';
import { useAuthStore } from '../auth/store';

const typeColors: Record<string, string> = {
  response_timeout: 'red', status_code_error: 'orange', consecutive_failure: 'purple',
};

export default function AlertList() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<AlertItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string | undefined>('pending');
  const [alertType, setAlertType] = useState<string | undefined>();
  const [apiId, setApiId] = useState<number | undefined>(
    searchParams.get('api_id') ? Number(searchParams.get('api_id')) : undefined
  );
  const [apis, setApis] = useState<ApiItem[]>([]);
  const setPendingCount = useAlertStore((s) => s.setPendingCount);
  const triggerRefresh = useAlertStore((s) => s.triggerRefresh);
  const user = useAuthStore((s) => s.user);
  const isViewer = user?.role === 'viewer';
  const [todayNewTotal, setTodayNewTotal] = useState(0);
  const [pendingTotal, setPendingTotal] = useState(0);

  useEffect(() => {
    apiApi.list({ page_size: 200 }).then((res) => setApis(res.items || [])).catch(() => {});
  }, []);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await alertApi.list({ status, alert_type: alertType, api_id: apiId, page, page_size: 20 });
      setData(res.items || []);
      setTotal(res.total || 0);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [status, alertType, apiId, page]);

  useEffect(() => { fetchList(); }, [fetchList]);

  // 独立获取今日新增总数（不受筛选条件影响）
  const fetchTodayCount = useCallback(async () => {
    try {
      const res = await alertApi.todayCount();
      setTodayNewTotal(res.count || 0);
    } catch { /* ignore */ }
  }, []);
  useEffect(() => { fetchTodayCount(); }, [fetchTodayCount]);

  // 独立获取待处理总数（不受筛选条件影响）
  const fetchPendingCount = useCallback(async () => {
    try {
      const res = await alertApi.pendingCount();
      setPendingTotal(res.count || 0);
      setPendingCount(res.count || 0);
    } catch { /* ignore */ }
  }, []);
  useEffect(() => { fetchPendingCount(); }, [fetchPendingCount]);

  const handleResolve = async (id: number) => {
    try {
      await alertApi.resolve(id);
      message.success('告警已解决');
      fetchList();
      fetchPendingCount();
      triggerRefresh();
    } catch { message.error('解决失败'); }
  };

  const columns = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
    { title: '接口', dataIndex: 'api_name', key: 'api_name', ellipsis: true },
    { title: '告警类型', dataIndex: 'alert_type', key: 'alert_type', width: 120,
      render: (v: string) => <Tag color={typeColors[v] || 'default'}>{v}</Tag> },
    { title: '告警消息', dataIndex: 'message', key: 'message', ellipsis: true,
      render: (v: string) => <Tooltip title={v}><span>{v}</span></Tooltip> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'pending' ? 'orange' : 'green'}>{v === 'pending' ? '待处理' : '已解决'}</Tag> },
    ...(isViewer ? [] : [{
      title: '操作', key: 'action', width: 80,
      render: (_: any, record: AlertItem) =>
        record.status === 'pending' ? (
          <Button size="small" type="primary" onClick={() => handleResolve(record.id)}>解决</Button>
        ) : (
          <Button size="small" disabled>已解决</Button>
        ),
    }]),
  ];

  return (
    <Card title="告警管理">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="当前待处理" value={pendingTotal} valueStyle={{ color: '#ff4d4f' }} /></Col>
        <Col span={6}><Statistic title="今日新增" value={todayNewTotal} valueStyle={{ color: '#faad14' }} /></Col>
        <Col span={6}><Statistic title="当前列表总数" value={data.length} /></Col>
      </Row>
      <Space style={{ marginBottom: 16, flexWrap: 'wrap' }}>
        <Select placeholder="状态" allowClear value={status} onChange={(v) => { setStatus(v); setPage(1); }} style={{ width: 120 }}>
          <Select.Option value="pending">待处理</Select.Option>
          <Select.Option value="resolved">已解决</Select.Option>
        </Select>
        <Select placeholder="告警类型" allowClear onChange={(v) => { setAlertType(v); setPage(1); }} style={{ width: 150 }}>
          <Select.Option value="response_timeout">响应超时</Select.Option>
          <Select.Option value="status_code_error">状态码异常</Select.Option>
          <Select.Option value="consecutive_failure">连续失败</Select.Option>
        </Select>
        <Select placeholder="接口筛选" allowClear value={apiId} onChange={(v) => { setApiId(v); setPage(1); }} style={{ width: 180 }} showSearch optionFilterProp="label">
          {apis.map((a) => <Select.Option key={a.id} value={a.id} label={a.name}>{a.name}</Select.Option>)}
        </Select>
        <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
      </Space>
      <Table
        dataSource={data} columns={columns} rowKey="id" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ x: 800 }}
        locale={{ emptyText: '🎉 目前没有待处理的告警' }}
      />
    </Card>
  );
}
