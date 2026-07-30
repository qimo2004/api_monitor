import { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Select, Statistic, Button, message, Space, Table, Tag, Radio, Empty } from 'antd';
import { DownloadOutlined, BarChartOutlined, LineChartOutlined, RadarChartOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import { statsApi } from './api';
import { apiApi, type ApiItem } from '../apis/api';
import { useAuthStore } from '../auth/store';

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#2b821d'];
const CHART_TYPES = [
  { key: 'line', label: '折线图', icon: <LineChartOutlined /> },
  { key: 'bar', label: '柱状图', icon: <BarChartOutlined /> },
  { key: 'radar', label: '雷达图', icon: <RadarChartOutlined /> },
];

export default function Reports() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === 'admin';
  const [apis, setApis] = useState<ApiItem[]>([]);
  const [apiId, setApiId] = useState<number | undefined>();
  const [stats, setStats] = useState<any>({});
  const [topSlow, setTopSlow] = useState<any[]>([]);
  const [topUnstable, setTopUnstable] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // ── 接口对比 ──
  const [compareApiIds, setCompareApiIds] = useState<number[]>([]);
  const [compareChartType, setCompareChartType] = useState<string>('line');
  const [compareData, setCompareData] = useState<any[]>([]);

  useEffect(() => {
    apiApi.list({ page_size: 100 }).then((res) => {
      setApis(res.items || []);
      if (res.items?.length) setApiId(res.items[0].id);
    }).catch(() => {});
  }, []);

  const fetchStats = useCallback(async () => {
    if (!apiId) return;
    setLoading(true);
    try {
      const [s, slow, unstable] = await Promise.all([
        statsApi.apiStats(apiId, 30),
        statsApi.topSlow(10),
        statsApi.topUnstable(10),
      ]);
      setStats(s);
      setTopSlow(slow || []);
      setTopUnstable(unstable || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [apiId]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const fetchCompareStats = useCallback(async () => {
    if (compareApiIds.length < 1) { setCompareData([]); return; }
    try {
      const res = await statsApi.compareStats(compareApiIds, 30);
      setCompareData(res.items || []);
    } catch { /* ignore */ }
  }, [compareApiIds]);

  useEffect(() => { fetchCompareStats(); }, [fetchCompareStats]);

  const dailyStats = stats.daily_stats || [];

  // ── 图表配置 ──
  const trendOption = {
    tooltip: { trigger: 'axis' as const },
    xAxis: { type: 'category' as const, data: dailyStats.map((d: any) => d.date) },
    yAxis: { type: 'value' as const, name: 'ms' },
    series: [{ data: dailyStats.map((d: any) => d.avg_response_time), type: 'line', smooth: true, name: '平均响应时间' }],
  };

  const successOption = {
    tooltip: { trigger: 'axis' as const },
    xAxis: { type: 'category' as const, data: dailyStats.map((d: any) => d.date) },
    yAxis: { type: 'value' as const, name: '%', max: 100 },
    series: [{ data: dailyStats.map((d: any) => d.success_rate), type: 'bar', name: '成功率', itemStyle: { color: '#52c41a' } }],
  };

  // ── 接口对比图表 ──
  const allDates = [...new Set(compareData.flatMap((d: any) => (d.daily_stats || []).map((ds: any) => ds.date)))].sort();

  const compareTrendOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        const title = params[0]?.axisValue || '';
        const lines = params.map((p: any) => `${p.marker} ${p.seriesName}: ${p.value}ms`);
        return `${title}<br/>${lines.join('<br/>')}`;
      },
    },
    legend: { type: 'scroll' as const, bottom: 0 },
    grid: { left: 60, right: 30, top: 10, bottom: 40 },
    xAxis: { type: 'category' as const, data: allDates },
    yAxis: { type: 'value' as const, name: '响应时间(ms)' },
    series: compareData.map((d: any, i: number) => {
      const dateMap = Object.fromEntries((d.daily_stats || []).map((ds: any) => [ds.date, ds.avg_response_time]));
      return {
        name: d.name,
        type: compareChartType === 'line' ? 'line' as const : 'bar' as const,
        data: allDates.map((dt) => dateMap[dt] ?? 0),
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: COLORS[i % COLORS.length] },
      };
    }),
  };

  const compareSuccessOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        const title = params[0]?.axisValue || '';
        const lines = params.map((p: any) => `${p.marker} ${p.seriesName}: ${p.value}%`);
        return `${title}<br/>${lines.join('<br/>')}`;
      },
    },
    legend: { type: 'scroll' as const, bottom: 0 },
    grid: { left: 60, right: 30, top: 10, bottom: 40 },
    xAxis: { type: 'category' as const, data: allDates },
    yAxis: { type: 'value' as const, name: '成功率(%)', max: 100 },
    series: compareData.map((d: any, i: number) => {
      const dateMap = Object.fromEntries((d.daily_stats || []).map((ds: any) => [ds.date, ds.success_rate]));
      return {
        name: d.name,
        type: compareChartType === 'line' ? 'line' as const : 'bar' as const,
        data: allDates.map((dt) => dateMap[dt] ?? 0),
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: COLORS[i % COLORS.length] },
      };
    }),
  };

  const compareRadarOption = {
    tooltip: { trigger: 'item' as const },
    legend: { type: 'scroll' as const, bottom: 0 },
    radar: {
      indicator: [
        { name: '成功率(%)', max: 100 },
        { name: 'SLA达标率(%)', max: 100 },
        { name: '平均响应(ms)', max: Math.max(...compareData.map((d: any) => d.avg_response_time || 0)) * 1.5 || 100 },
      ],
      center: ['50%', '50%'],
      radius: '65%',
    },
    series: [{
      type: 'radar' as const,
      data: compareData.map((d: any, i: number) => ({
        value: [d.success_rate, d.sla_compliance, d.avg_response_time],
        name: d.name,
        areaStyle: { color: COLORS[i % COLORS.length], opacity: 0.1 },
        lineStyle: { color: COLORS[i % COLORS.length] },
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  };

  const slowOption = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any) => {
        const p = params[0];
        const fullName = p.data?.fullName || p.name;
        return `${fullName}<br/>平均响应: ${p.value}ms`;
      },
    },
    grid: { left: 120, right: 20, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const, name: '响应时间(ms)' },
    yAxis: {
      type: 'category' as const,
      data: topSlow.map((d: any) => (d.name && d.name.length > 10 ? d.name.slice(0, 10) + '...' : d.name)),
      inverse: true,
      axisLabel: { fontSize: 12 },
    },
    series: [{
      data: topSlow.map((d: any) => ({
        value: d.avg_response_time,
        fullName: d.name,
        itemStyle: {
          color: d.avg_response_time >= 1000 ? '#ff4d4f' : d.avg_response_time >= 500 ? '#faad14' : '#52c41a',
        },
      })),
      type: 'bar',
      barMaxWidth: 24,
    }],
  };

  const unstableOption = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any) => {
        const p = params[0];
        const fullName = p.data?.fullName || p.name;
        return `${fullName}<br/>成功率: ${p.value}%`;
      },
    },
    grid: { left: 120, right: 20, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const, name: '成功率(%)', max: 100 },
    yAxis: {
      type: 'category' as const,
      data: topUnstable.map((d: any) => (d.name && d.name.length > 10 ? d.name.slice(0, 10) + '...' : d.name)),
      inverse: true,
      axisLabel: { fontSize: 12 },
    },
    series: [{
      data: topUnstable.map((d: any) => ({
        value: d.success_rate,
        fullName: d.name,
        itemStyle: {
          color: d.success_rate >= 90 ? '#52c41a' : d.success_rate >= 70 ? '#faad14' : '#ff4d4f',
        },
      })),
      type: 'bar',
      barMaxWidth: 24,
    }],
  };

  const handleExport = async (format: 'csv' | 'pdf') => {
    try {
      const blob = await statsApi.exportReport({ api_id: apiId, days: 30, export_format: format });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch { message.error('导出失败'); }
  };

  return (
    <div>
      {/* ── 接口对比分析 ── */}
      <Card title="接口对比分析" size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle" style={{ marginBottom: 16 }}>
          <Col xs={24} md={10}>
            <Select
              mode="multiple" value={compareApiIds} onChange={setCompareApiIds}
              style={{ width: '100%' }} placeholder="选择要对比的接口（可多选）"
              showSearch optionFilterProp="label"
              maxTagCount={0}
              maxTagPlaceholder={(omittedValues) => `已选 ${omittedValues.length} 个接口`}
            >
              {apis.map((a) => (
                <Select.Option key={a.id} value={a.id} label={a.name}>{a.name} - {a.method} {a.url}</Select.Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} md={14}>
            <Radio.Group
              value={compareChartType} onChange={(e) => setCompareChartType(e.target.value)}
              optionType="button" buttonStyle="solid"
            >
              {CHART_TYPES.map((ct) => (
                <Radio.Button key={ct.key} value={ct.key}>{ct.icon} {ct.label}</Radio.Button>
              ))}
            </Radio.Group>
          </Col>
        </Row>

        {compareData.length < 1 ? (
          <Empty description="请选择至少一个接口进行对比" />
        ) : compareChartType === 'radar' ? (
          <Row gutter={[16, 16]}>
            <Col xs={24}>
              <Card title="综合指标对比（雷达图）" size="small" type="inner">
                <ReactEChartsCore key="radar" option={compareRadarOption} style={{ height: 400 }} />
              </Card>
            </Col>
          </Row>
        ) : (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title={`响应时间趋势对比（${compareChartType === 'line' ? '折线图' : '柱状图'}）`} size="small" type="inner">
                <ReactEChartsCore key={`trend-${compareChartType}`} option={compareTrendOption} style={{ height: 350 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title={`成功率趋势对比（${compareChartType === 'line' ? '折线图' : '柱状图'}）`} size="small" type="inner">
                <ReactEChartsCore key={`success-${compareChartType}`} option={compareSuccessOption} style={{ height: 350 }} />
              </Card>
            </Col>
          </Row>
        )}

        {compareData.length > 0 && (
          <Table
            dataSource={compareData} rowKey="api_id" size="small"
            pagination={false} style={{ marginTop: 12 }}
            columns={[
              { title: '接口名称', dataIndex: 'name', key: 'name', ellipsis: true },
              { title: '方法', dataIndex: 'method', key: 'method', width: 70,
                render: (v: string) => <Tag color={v === 'GET' ? 'blue' : v === 'POST' ? 'green' : v === 'PUT' ? 'orange' : 'red'}>{v}</Tag> },
              { title: '成功率', dataIndex: 'success_rate', key: 'success_rate', width: 100,
                render: (v: number) => <span style={{ color: v >= 90 ? '#52c41a' : v >= 70 ? '#faad14' : '#ff4d4f', fontWeight: 600 }}>{v}%</span> },
              { title: '平均响应', dataIndex: 'avg_response_time', key: 'avg_response_time', width: 100,
                render: (v: number) => `${v}ms` },
              { title: 'SLA达标率', dataIndex: 'sla_compliance', key: 'sla_compliance', width: 110,
                render: (v: number) => <span style={{ color: v >= 90 ? '#52c41a' : v >= 70 ? '#faad14' : '#ff4d4f', fontWeight: 600 }}>{v}%</span> },
            ]}
          />
        )}
      </Card>

      {/* ── 单接口选择 ── */}
      <Card title="单接口统计">
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Select
              value={apiId} onChange={setApiId} style={{ width: '100%' }}
              showSearch optionFilterProp="label"
              placeholder="选择接口"
            >
              {apis.map((a) => <Select.Option key={a.id} value={a.id} label={a.name}>{a.name}</Select.Option>)}
            </Select>
          </Col>
          {isAdmin && (
            <Col xs={24} md={18}>
              <Space>
                <Button icon={<DownloadOutlined />} onClick={() => handleExport('csv')}>导出CSV</Button>
                <Button icon={<DownloadOutlined />} onClick={() => handleExport('pdf')}>导出PDF</Button>
              </Space>
            </Col>
          )}
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={8}><Card><Statistic title="成功率" value={stats.success_rate || 0} suffix="%" valueStyle={{ color: (stats.success_rate || 0) >= 90 ? '#52c41a' : '#ff4d4f' }} /></Card></Col>
        <Col xs={8}><Card><Statistic title="平均响应时间" value={stats.avg_response_time || 0} suffix="ms" /></Card></Col>
        <Col xs={8}><Card><Statistic title="SLA达标率" value={stats.sla_compliance || 0} suffix="%" /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="响应时间趋势" size="small">
            <ReactEChartsCore option={trendOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="成功率趋势" size="small">
            <ReactEChartsCore option={successOption} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="最慢接口 TOP10" size="small">
            <ReactEChartsCore option={slowOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="最不稳定接口 TOP10" size="small">
            <ReactEChartsCore option={unstableOption} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
