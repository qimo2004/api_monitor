import { useEffect, useState } from 'react';
import { Button, Card, Row, Col, Statistic, Table, List, Tag, Skeleton, Typography } from 'antd';
import { MinusCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ApiOutlined, AlertOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import { useNavigate } from 'react-router-dom';
import { statsApi } from '../stats/api';
import { apiApi } from '../apis/api';
import { alertApi } from '../alerts/api';

interface DashboardData {
  total_apis?: number;
  healthy_count?: number;
  warning_count?: number;
  down_count?: number;
  disabled_count?: number;
  today_checks?: number;
  pending_alerts?: number;
  recent_logs?: any[];
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData>({});
  const [topSlow, setTopSlow] = useState<any[]>([]);
  const [pendingAlerts, setPendingAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        statsApi.dashboard(),
        statsApi.topSlow(5),
        apiApi.status(),
        alertApi.list({ status: 'pending', page_size: 5 }),
      ]);
      if (results[0].status === 'fulfilled') setData((prev) => ({ ...prev, ...results[0].value }));
      if (results[1].status === 'fulfilled') setTopSlow(results[1].value || []);
      if (results[2].status === 'fulfilled') setData((prev) => ({ ...prev, ...results[2].value }));
      if (results[3].status === 'fulfilled') setPendingAlerts(results[3].value?.items || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const healthData = [
    { value: (data.healthy_count || 0) + (data.warning_count || 0), name: '健康', itemStyle: { color: '#52c41a' } },
    { value: data.down_count || 0, name: '故障', itemStyle: { color: '#ff4d4f' } },
    { value: data.disabled_count || 0, name: '禁用', itemStyle: { color: '#d9d9d9' } },
  ];

  const onChartClick = (params: any) => {
    const name = params.name;
    if (name === '故障') navigate('/apis?health=down');
    else if (name === '禁用') navigate('/apis?enabled=0');
    else if (name === '健康') navigate('/apis?health=healthy');
  };

  const donutOption = {
    tooltip: { trigger: 'item' as const },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: { scale: true },
      cursor: 'pointer',
      data: healthData,
    }],
  };

  const logColumns = [
    { title: '时间', dataIndex: 'check_time', key: 'check_time', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
    { title: '接口', dataIndex: 'api_name', key: 'api_name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v}</Tag> },
    { title: '响应时间', dataIndex: 'response_time_ms', key: 'response_time_ms', render: (v: number) => v ? `${v}ms` : '-' },
  ];

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 8 }}>
        <Button icon={<ReloadOutlined />} onClick={fetchData} size="small">刷新</Button>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}><Card><Statistic title="总接口数" value={data.total_apis || 0} prefix={<ApiOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="正常运行" value={(data.healthy_count || 0) + (data.warning_count || 0)} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="故障" value={data.down_count || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<CloseCircleOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="待处理告警" value={data.pending_alerts || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<AlertOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="今日巡检" value={data.today_checks || 0} suffix="次" /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={10}>
          <Card title="健康状态分布" size="small">
            <ReactEChartsCore option={donutOption} style={{ height: 240 }} onEvents={{ click: onChartClick }} />
          </Card>
        </Col>
        <Col xs={24} md={14}>
          <Card title="最近巡检" size="small">
            <Table
              dataSource={(data.recent_logs || []).slice(0, 5)}
              columns={logColumns}
              rowKey="id"
              size="small"
              pagination={false}
              onRow={(record: any) => ({ 
                onClick: () => navigate(`/logs?api_id=${record.api_id}`), 
                style: { cursor: 'pointer' } 
              })}
            />
          </Card>
        </Col>
      </Row>

      <Card title="待处理告警" size="small" style={{ marginTop: 16 }}>
        <List
          dataSource={pendingAlerts}
          locale={{ emptyText: '🎉 目前没有待处理的告警' }}
          renderItem={(item: any) => (
            <List.Item
              onClick={() => navigate(`/alerts?api_id=${item.api_id}`)}
              style={{ cursor: 'pointer' }}
            >
              <Typography.Text>{item.message}</Typography.Text>
              <Typography.Text type="secondary">{item.api_name}</Typography.Text>
            </List.Item>
          )}
        />
      </Card>

      <Card title="最慢接口排行" size="small" style={{ marginTop: 16 }}>
        <List
          dataSource={topSlow}
          renderItem={(item: any, idx) => (
            <List.Item>
              <Typography.Text>{idx + 1}. {item.name}</Typography.Text>
              <Typography.Text type="secondary">{item.avg_response_time}ms</Typography.Text>
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
