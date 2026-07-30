import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card, Table, Button, Input, Select, Space, Tag, Drawer, Form, Descriptions,
  InputNumber, Switch, message, Popconfirm, Tooltip, notification, Modal, Radio,
  Checkbox, Row, Col,
} from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined, PlayCircleOutlined, DownloadOutlined, HistoryOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import * as XLSX from 'xlsx';
import { apiApi, type ApiItem, type ApiCreate, type ApiUpdate } from './api';
import { authApi, type UserInfo } from '../auth/api';
import { useAuthStore } from '../auth/store';

const methodColors: Record<string, string> = { GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' };

export default function ApiList() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === 'admin';
  const canCheck = user?.role !== 'viewer';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<ApiItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [group, setGroup] = useState<string | undefined>();
  const [enableFilter, setEnableFilter] = useState<number | undefined>(
    searchParams.get('enabled') !== null ? Number(searchParams.get('enabled')) : undefined
  );
  const [tagFilter, setTagFilter] = useState<string | undefined>();
  const [healthFilter, setHealthFilter] = useState<string | undefined>(
    searchParams.get('health') || undefined
  );
  const [detailItem, setDetailItem] = useState<ApiItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editItem, setEditItem] = useState<ApiItem | null>(null);
  const [form] = Form.useForm();
  // 批量选择
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchIntervalModalOpen, setBatchIntervalModalOpen] = useState(false);
  const [batchIntervalValue, setBatchIntervalValue] = useState(300);
  // 授权管理
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [operators, setOperators] = useState<UserInfo[]>([]);
  const [authorizations, setAuthorizations] = useState<Record<number, number[]>>({});
  const [selectedAuthOpIds, setSelectedAuthOpIds] = useState<number[]>([]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiApi.list({ search, group_name: group, enabled: enableFilter, tag: tagFilter, health: healthFilter, page, page_size: 10 });
      // 当前页没有数据但总条数 > 0，说明翻页越界（管理员变更授权后可见接口变少），回退到第1页
      if ((res.items || []).length === 0 && (res.total || 0) > 0 && page > 1) {
        setPage(1);
        return; // setPage 会触发 useEffect 重新 fetchList
      }
      setData(res.items || []);
      setTotal(res.total || 0);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [search, group, enableFilter, tagFilter, healthFilter, page]);

  useEffect(() => { fetchList(); }, [fetchList]);

  // 同步 URL 参数到筛选状态（组件不重新挂载时也生效）
  useEffect(() => {
    const health = searchParams.get('health') || undefined;
    const enabled = searchParams.get('enabled') !== null ? Number(searchParams.get('enabled')) : undefined;
    if (health !== healthFilter) setHealthFilter(health);
    if (enabled !== enableFilter) setEnableFilter(enabled);
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCheck = async (id: number) => {
    // 默认快速巡检（使用接口默认配置）
    try {
      const result = await apiApi.check(id);
      const log = result.check_log;
      fetchList(); // 先更新列表，后续弹出通知
      notification.open({
        message: log.status === 'success' ? '巡检成功' : '巡检失败',
        description: `响应时间: ${log.response_time_ms}ms | HTTP: ${log.http_status} | ${log.error_message || ''}`,
        type: log.status === 'success' ? 'success' : 'error',
        placement: 'topRight',
        duration: 3,
      });
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '巡检失败');
    }
  };

  // 启用/禁用切换
  const handleToggleEnabled = async (id: number, current: boolean) => {
    try {
      await apiApi.update(id, { enabled: !current });
      message.success(`接口已${current ? '禁用' : '启用'}`);
      fetchList();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  // 自定义测试状态
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testApi, setTestApi] = useState<ApiItem | null>(null);
  const [testForm] = Form.useForm();
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  // Excel 导入（直接选择文件后自动导入）
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);

  const downloadTemplate = () => {
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([['名称', 'URL', '方法', '分组'], ['示例接口名称', 'https://api.example.com/endpoint', 'GET', '默认分组']]);
    XLSX.utils.book_append_sheet(wb, ws, '模版');
    XLSX.writeFile(wb, '接口导入模版.xlsx');
  };

  const handleFileImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const data = new Uint8Array(ev.target?.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: 'array' });
        const sheet = workbook.Sheets[workbook.SheetNames[0]];
        const json = XLSX.utils.sheet_to_json<Record<string, any>>(sheet);
        const items = json.map((row: any) => {
          const keys = Object.keys(row);
          const nameKey = keys.find(k => /名称|名字|name|接口名|接口名称/i.test(k));
          const urlKey = keys.find(k => /url|地址|链接|link/i.test(k));
          const methodKey = keys.find(k => /方法|method|请求方式|请求方法/i.test(k));
          const groupKey = keys.find(k => /分组|group|组|分类/i.test(k));
          return {
            name: nameKey ? String(row[nameKey] || '').trim() : '',
            url: urlKey ? String(row[urlKey] || '').trim() : '',
            method: methodKey ? String(row[methodKey] || '').trim().toUpperCase() : 'GET',
            group_name: groupKey ? String(row[groupKey] || '').trim() : undefined,
          };
        }).filter(item => item.name && item.url);
        if (items.length === 0) {
          message.warning('未从文件中识别到有效数据，请检查列名是否包含"名称"和"URL"');
          return;
        }
        setImporting(true);
        try {
          const result = await apiApi.batchImport(items);
          message.success(`成功导入 ${result.imported} 个接口`);
          fetchList();
        } catch (err: any) {
          message.error(err?.response?.data?.detail || '导入失败');
        } finally {
          setImporting(false);
        }
      } catch {
        message.error('Excel 解析失败，请检查文件格式');
      }
    };
    reader.readAsArrayBuffer(file);
    // 重置 input 以便再次选择同一文件
    e.target.value = '';
  };

  const handleBatchInterval = async () => {
    if (selectedRowKeys.length === 0) return;
    if (batchIntervalValue < 10) {
      message.warning('巡检间隔不能小于10秒');
      return;
    }
    try {
      await apiApi.batchCheckInterval(selectedRowKeys as number[], batchIntervalValue);
      message.success(`已批量设置 ${selectedRowKeys.length} 个接口的巡检间隔为 ${batchIntervalValue}s`);
      setBatchIntervalModalOpen(false);
      setSelectedRowKeys([]);
      fetchList();
    } catch {
      message.error('批量设置失败');
    }
  };

  const handleBatchEnabled = async (enabled: boolean) => {
    try {
      const label = enabled ? '启用' : '禁用';
      await apiApi.batchEnabled(selectedRowKeys as number[], enabled);
      message.success(`已${label} ${selectedRowKeys.length} 个接口`);
      setSelectedRowKeys([]);
      fetchList();
    } catch {
      message.error('批量操作失败');
    }
  };

  const handleBatchDelete = () => {
    Modal.confirm({
      title: `确定删除选中的 ${selectedRowKeys.length} 个接口？`,
      content: '删除后关联的巡检日志和告警也将自动删除，不可恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiApi.batchDelete(selectedRowKeys as number[]);
          message.success(`已删除 ${selectedRowKeys.length} 个接口`);
          setSelectedRowKeys([]);
          fetchList();
        } catch {
          message.error('批量删除失败');
        }
      },
    },);
  };

  const openAuthModal = async () => {
    try {
      const [usersRes, authRes] = await Promise.all([
        authApi.listUsers(1, 200),
        apiApi.getAuthorizations(),
      ]);
      const ops = (usersRes.items || []).filter((u: UserInfo) => u.role === 'operator');
      setOperators(ops);
      setAuthorizations(authRes || {});
      // 计算被选接口的授权用户（并集：任一接口有授权的用户都选中）
      const selectedIds = selectedRowKeys as number[];
      const unionSet = new Set<number>();
      selectedIds.forEach((apiId) => {
        const authUserIds = authRes[apiId] || [];
        authUserIds.forEach((id: number) => unionSet.add(id));
      });
      setSelectedAuthOpIds([...unionSet]);
      setAuthModalOpen(true);
    } catch { message.error('加载授权数据失败'); }
  };

  const handleSaveAuth = async () => {
    const selectedIds = selectedRowKeys as number[];
    try {
      for (const apiId of selectedIds) {
        await apiApi.updateAuthorization(apiId, selectedAuthOpIds);
      }
      message.success(`已更新 ${selectedIds.length} 个接口的授权`);
      setAuthModalOpen(false);
      fetchList();
    } catch { message.error('授权更新失败'); }
  };

  const openTestModal = (item: ApiItem) => {
    setTestApi(item);
    setTestResult(null);
    testForm.setFieldsValue({
      method: item.method,
      url: item.url,
      headers: item.headers || '',
      body: item.body || '',
      body_type: item.body_type || 'json',
      timeout: item.timeout,
    });
    setTestModalOpen(true);
  };

  const handleTestCheck = async () => {
    if (!testApi) return;
    try {
      setTestLoading(true);
      setTestResult(null);
      const values = await testForm.validateFields();
      const result = await apiApi.check(testApi.id, {
        method: values.method,
        url: values.url,
        headers: values.headers || undefined,
        body: values.body || undefined,
        body_type: values.body_type,
        timeout: values.timeout,
      });
      setTestResult(result.check_log);
      fetchList(); // 刷新列表更新最新状态
      message.success('测试完成');
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    } finally {
      setTestLoading(false);
    }
  };

  const openCreate = () => {
    setEditItem(null);
    form.resetFields();
    setDrawerOpen(true);
  };

  const openEdit = (item: ApiItem) => {
    setEditItem(item);
    form.setFieldsValue({
      name: item.name, url: item.url, method: item.method,
      timeout: item.timeout,
      expected_status: item.expected_status, expected_response_time: item.expected_response_time,
      check_interval: item.check_interval, enabled: item.enabled,
      group_name: item.group_name, tags: item.tags,
    });
    setDrawerOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await apiApi.delete(id);
      message.success('删除成功');
      setPage(1);
      fetchList();
    } catch { message.error('删除失败'); }
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editItem) {
        await apiApi.update(editItem.id, values as ApiUpdate);
        message.success('更新成功');
      } else {
        await apiApi.create(values as ApiCreate);
        message.success('创建成功');
        setPage(1); // 新建后跳回第1页，新接口显示在最前面
      }
      setDrawerOpen(false);
      fetchList();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 200,
      render: (v: string) => <Tooltip title={v}><span>{v}</span></Tooltip> },
    { title: 'URL', dataIndex: 'url', key: 'url', width: 300,
      render: (v: string) => <Tooltip title={v}><span>{v}</span></Tooltip> },
    { title: '方法', dataIndex: 'method', key: 'method', width: 80,
      render: (v: string) => <Tag color={methodColors[v] || 'default'}>{v}</Tag> },
    { title: '分组', dataIndex: 'group_name', key: 'group_name', width: 100 },
    { title: '状态', dataIndex: 'last_status', key: 'last_status', width: 80,
      render: (v: string | null, record: any) => {
        if (!record.enabled) return <Tag color="default">已禁用</Tag>;
        if (!v) return <Tag>未巡检</Tag>;
        const color = v === 'success' ? 'green' : 'red';
        const label = v === 'success' ? '正常' : '故障';
        return <Tag color={color}>{label}</Tag>;
      } },
    { title: '最近响应', dataIndex: 'last_response_time_ms', key: 'last_response_time', width: 90,
      render: (v: number | null) => v ? `${v}ms` : '-' },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
    { title: '操作', key: 'action', width: 320,
      render: (_: any, record: ApiItem) => (
        <div onClick={(e) => e.stopPropagation()}>
          <Space size="small">
            {canCheck && <Tooltip title="快速巡检（使用接口配置）"><Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleCheck(record.id)} /></Tooltip>}
            {canCheck && <Button size="small" onClick={() => openTestModal(record)}>测试</Button>}
            <Tooltip title="查看该接口的巡检日志"><Button size="small" icon={<HistoryOutlined />} onClick={() => navigate(`/logs?api_id=${record.id}`)}>日志</Button></Tooltip>
            {isAdmin && (
              <Tooltip title={record.enabled ? '禁用接口（暂停巡检）' : '启用接口'}><Button size="small" onClick={() => handleToggleEnabled(record.id, record.enabled)}>{record.enabled ? '禁用' : '启用'}</Button></Tooltip>
            )}
            {isAdmin && <Button size="small" onClick={() => openEdit(record)}>编辑</Button>}
            {isAdmin && (
              <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
                <Button size="small" danger>删除</Button>
              </Popconfirm>
            )}
          </Space>
        </div>
      ),
    },
  ];

  return (
    <Card
      title="接口管理"
      extra={isAdmin && <Space>
        <Button icon={<DownloadOutlined />} loading={importing} onClick={() => fileInputRef.current?.click()}>导入Excel</Button>
        <Button onClick={downloadTemplate}>下载excel模版</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增接口</Button>
      </Space>}
    >
      <input type="file" accept=".xlsx,.xls" ref={fileInputRef} style={{ display: 'none' }} onChange={handleFileImport} />
      <Space style={{ marginBottom: 16, flexWrap: 'wrap' }}>
        <Input prefix={<SearchOutlined />} placeholder="搜索接口名称" allowClear onChange={(e) => { setSearch(e.target.value); setPage(1); }} style={{ width: 200 }} />
        <Select placeholder="分组筛选" allowClear onChange={(v) => { setGroup(v); setPage(1); }} style={{ width: 140 }}>
          {[...new Set(data.map((d) => d.group_name).filter(Boolean))].map((g) => (
            <Select.Option key={g!} value={g!}>{g}</Select.Option>
          ))}
        </Select>
        <Select placeholder="启用状态" allowClear onChange={(v) => { setEnableFilter(v); setPage(1); }} style={{ width: 120 }}>
          <Select.Option value={1}>已启用</Select.Option>
          <Select.Option value={0}>已禁用</Select.Option>
        </Select>
        <Select placeholder="标签筛选" allowClear onChange={(v) => { setTagFilter(v); setPage(1); }} style={{ width: 130 }}>
          {[...new Set(data.flatMap((d) => { try { return JSON.parse(d.tags || '[]'); } catch { return []; } }))].map((t) => (
            <Select.Option key={t as string} value={t as string}>{t as string}</Select.Option>
          ))}
        </Select>
        <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
      </Space>
      {healthFilter && (
        <div style={{ marginBottom: 12 }}>
          <Tag color={healthFilter === 'healthy' ? 'green' : 'red'} closable onClose={() => { setHealthFilter(undefined); setPage(1); navigate('/apis', { replace: true }); }}>
            {healthFilter === 'healthy' ? '健康' : '故障'}
          </Tag>
          <Button type="link" size="small" onClick={() => { setHealthFilter(undefined); setEnableFilter(undefined); setPage(1); navigate('/apis', { replace: true }); }}>清除筛选</Button>
        </div>
      )}
      {isAdmin && selectedRowKeys.length > 0 && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: '#e6f7ff', borderRadius: 6, border: '1px solid #91d5ff' }}>
          <span style={{ marginRight: 12 }}>已选 <b>{selectedRowKeys.length}</b> 个接口</span>
          <Button size="small" onClick={() => setBatchIntervalModalOpen(true)}>批量设置巡检间隔</Button>
          <Button size="small" style={{ marginLeft: 8 }} onClick={openAuthModal}>授权管理</Button>
          <Button size="small" style={{ marginLeft: 8 }} onClick={() => handleBatchEnabled(true)}>批量启用</Button>
          <Button size="small" style={{ marginLeft: 8 }} onClick={() => handleBatchEnabled(false)}>批量禁用</Button>
          <Button size="small" style={{ marginLeft: 8 }} danger onClick={handleBatchDelete}>批量删除</Button>
          <Button size="small" style={{ marginLeft: 8 }} onClick={() => setSelectedRowKeys([])}>取消选择</Button>
        </div>
      )}

      <Table
        dataSource={data} columns={columns} rowKey="id" loading={loading}
        rowSelection={isAdmin ? { selectedRowKeys, onChange: setSelectedRowKeys } : undefined}
        onRow={(record) => ({ onClick: (e) => { const target = e.target as HTMLElement; if (target.closest('.ant-checkbox')) return; setDetailItem(record); setDetailOpen(true); }, style: { cursor: 'pointer' } })}
        pagination={{ current: page, total, pageSize: 10, onChange: (p: number) => setPage(p), showTotal: (t: number) => `共 ${t} 条`, showSizeChanger: false }}
        scroll={{ x: 800 }}
      />

      <Drawer
        title={editItem ? '编辑接口' : '新增接口'}
        size="large" open={drawerOpen} onClose={() => setDrawerOpen(false)}
        extra={<Button type="primary" onClick={handleSubmit}>{editItem ? '更新' : '创建'}</Button>}
      >
        <Form form={form} layout="vertical" initialValues={{ method: 'GET', timeout: 5000, expected_status: 200, check_interval: 300, enabled: true }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="url" label="URL" rules={[{ required: true, type: 'url', message: '请输入有效的URL' }]}><Input /></Form.Item>
          <Form.Item name="method" label="方法"><Select>
            <Select.Option value="GET">GET</Select.Option>
            <Select.Option value="POST">POST</Select.Option>
            <Select.Option value="PUT">PUT</Select.Option>
            <Select.Option value="DELETE">DELETE</Select.Option>
          </Select></Form.Item>
          <Form.Item name="timeout" label="超时(ms)"><InputNumber min={100} max={60000} /></Form.Item>
          <Form.Item name="expected_status" label="期望状态码"><InputNumber min={100} max={599} /></Form.Item>
          <Form.Item name="expected_response_time" label="期望响应时间(ms)"><InputNumber min={0} /></Form.Item>
          <Form.Item name="check_interval" label="巡检间隔(秒)"><InputNumber min={10} /></Form.Item>
          <Form.Item name="group_name" label="分组"><Input /></Form.Item>
          <Form.Item name="tags" label="标签 (JSON数组)"><Input /></Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Drawer>
      {/* 自定义手动测试弹窗 */}
      <Modal
        title={`自定义测试 - ${testApi?.name || ''}`}
        open={testModalOpen}
        onCancel={() => { setTestModalOpen(false); setTestResult(null); }}
        footer={[
          <Button key="close" onClick={() => { setTestModalOpen(false); setTestResult(null); }}>关闭</Button>,
          <Button key="test" type="primary" loading={testLoading} icon={<PlayCircleOutlined />} onClick={handleTestCheck}>发送请求</Button>,
        ]}
        width={640}
      >
        <Form form={testForm} layout="vertical" initialValues={{ body_type: 'json', timeout: 5000 }}>
          <Space style={{ width: '100%' }} size="middle">
            <Form.Item name="method" label="方法" rules={[{ required: true }]}>
              <Select style={{ width: 110 }}>
                <Select.Option value="GET">GET</Select.Option>
                <Select.Option value="POST">POST</Select.Option>
                <Select.Option value="PUT">PUT</Select.Option>
                <Select.Option value="PATCH">PATCH</Select.Option>
                <Select.Option value="DELETE">DELETE</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="timeout" label="超时(ms)" style={{ width: 130 }}>
              <InputNumber min={100} max={60000} />
            </Form.Item>
          </Space>
          <Form.Item name="url" label="URL" rules={[{ required: true }]}>
            <Input placeholder="请求地址（默认使用接口配置URL）" />
          </Form.Item>
          <Form.Item name="headers" label="Headers (JSON)">
            <Input.TextArea rows={2} placeholder='{"Content-Type": "application/json"}' />
          </Form.Item>
          <Space style={{ width: '100%' }} align="start">
            <Form.Item name="body_type" label="Body 类型">
              <Radio.Group>
                <Radio value="json">JSON</Radio>
                <Radio value="data">Form Data</Radio>
              </Radio.Group>
            </Form.Item>
          </Space>
          <Form.Item name="body" label="请求体">
            <Input.TextArea rows={4} placeholder='{"key": "value"}' />
          </Form.Item>
        </Form>
        {testResult && (
          <Card size="small" title="测试结果" style={{ marginTop: 8 }}>
            <p><Tag color={testResult.status === 'success' ? 'green' : 'red'}>{testResult.status}</Tag></p>
            <p>HTTP 状态码: <strong>{testResult.http_status}</strong> | 响应时间: <strong>{testResult.response_time_ms}ms</strong> | 大小: <strong>{testResult.response_size}bytes</strong></p>
            {testResult.error_message && <p style={{ color: 'red' }}>错误: {testResult.error_message}</p>}
            {testResult.response_summary && (
              <Input.TextArea rows={4} readOnly value={testResult.response_summary} style={{ fontSize: 12, fontFamily: 'monospace' }} />
            )}
          </Card>
        )}
      </Modal>

      {/* 批量设置巡检间隔弹窗 */}
      <Modal
        title={`批量设置巡检间隔（已选 ${selectedRowKeys.length} 个接口）`}
        open={batchIntervalModalOpen}
        onCancel={() => setBatchIntervalModalOpen(false)}
        onOk={handleBatchInterval}
        okText="确认设置"
      >
        <div style={{ margin: '16px 0' }}>
          <span>巡检间隔（秒）：</span>
          <InputNumber min={10} max={86400} value={batchIntervalValue} onChange={(v) => setBatchIntervalValue(v ?? 300)} style={{ width: 200 }} />
          <span style={{ marginLeft: 8, color: '#999' }}>最小10秒</span>
        </div>
      </Modal>

      {/* 授权管理弹窗 */}
      <Modal
        title={`授权管理（已选 ${selectedRowKeys.length} 个接口）`}
        open={authModalOpen}
        onCancel={() => { setAuthModalOpen(false); setSelectedAuthOpIds([]); }}
        onOk={handleSaveAuth}
        okText="保存授权"
      >
        <div style={{ margin: '16px 0' }}>
          <p style={{ marginBottom: 8, color: '#666' }}>
            正在设置 <b>{selectedRowKeys.length}</b> 个接口的授权，勾选的运维人员可查看和接收这些接口的告警通知：
          </p>
          <p style={{ marginBottom: 12, color: '#999', fontSize: 13 }}>
            💡 保存后将替换所有选中接口的授权，取消勾选即撤销该运维人员对这些接口的授权
          </p>
          {operators.length === 0 ? (
            <p style={{ color: '#999' }}>暂无可选运维人员</p>
          ) : (
            <Checkbox.Group
              value={selectedAuthOpIds}
              onChange={(values) => setSelectedAuthOpIds(values as number[])}
              style={{ width: '100%' }}
            >
              <Row gutter={[16, 12]}>
                {operators.map((op) => (
                  <Col span={12} key={op.id}>
                    <Checkbox value={op.id}>
                      {op.display_name || op.username}
                      {op.email ? ` (${op.email})` : ''}
                    </Checkbox>
                  </Col>
                ))}
              </Row>
            </Checkbox.Group>
          )}
        </div>
      </Modal>

      {/* 接口详情抽屉 */}
      <Drawer title="接口详情" size="large" open={detailOpen} onClose={() => setDetailOpen(false)}>
        {detailItem && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="接口ID">{detailItem.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{detailItem.name}</Descriptions.Item>
            <Descriptions.Item label="URL">{detailItem.url}</Descriptions.Item>
            <Descriptions.Item label="方法"><Tag color={{ GET: 'green', POST: 'blue', PUT: 'orange', DELETE: 'red' }[detailItem.method] || 'default'}>{detailItem.method}</Tag></Descriptions.Item>
            <Descriptions.Item label="请求头">{detailItem.headers || '-'}</Descriptions.Item>
            <Descriptions.Item label="请求体">{detailItem.body || '-'}</Descriptions.Item>
            <Descriptions.Item label="超时(ms)">{detailItem.timeout}</Descriptions.Item>
            <Descriptions.Item label="期望状态码">{detailItem.expected_status}</Descriptions.Item>
            <Descriptions.Item label="期望响应时间(ms)">{detailItem.expected_response_time}</Descriptions.Item>
            <Descriptions.Item label="巡检间隔(秒)">{detailItem.check_interval}</Descriptions.Item>
            <Descriptions.Item label="启用状态">{detailItem.enabled ? <Tag color="green">已启用</Tag> : <Tag color="default">已禁用</Tag>}</Descriptions.Item>
            <Descriptions.Item label="分组">{detailItem.group_name || '-'}</Descriptions.Item>
            <Descriptions.Item label="标签">{detailItem.tags || '-'}</Descriptions.Item>
            <Descriptions.Item label="最近状态">
              {detailItem.last_status === 'success' ? <Tag color="green">正常</Tag> :
               detailItem.last_status === 'failure' ? <Tag color="red">故障</Tag> : <Tag>未巡检</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="最近响应时间">{detailItem.last_response_time_ms ? `${detailItem.last_response_time_ms}ms` : '-'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{dayjs(detailItem.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{dayjs(detailItem.updated_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </Card>
  );
}
