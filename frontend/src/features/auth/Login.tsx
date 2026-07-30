import { useState } from 'react';
import { Form, Input, Button, Card, Typography, Checkbox, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { authApi } from './api';
import { useAuthStore } from './store';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { username: string; password: string; remember: boolean }) => {
    setLoading(true);
    try {
      const result = await authApi.login(values);
      setAuth(result.token, result.user);
      message.success('登录成功');
      // 管理员跳转请求来源页或仪表盘，运维人员跳转接口管理页
      const defaultPath = result.user.role === 'operator' ? '/apis' : '/dashboard';
      const target = (location.state as any)?.from?.pathname || defaultPath;
      navigate(target, { replace: true });
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '用户名或密码错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <Card style={{ width: 400, borderRadius: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.2)' }}>
        <Typography.Title level={3} style={{ textAlign: 'center', marginBottom: 8 }}>
          📊 API Monitor
        </Typography.Title>
        <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 24 }}>
          企业接口巡检与稳定性监控系统
        </Typography.Text>
        <Form onFinish={onFinish} initialValues={{ remember: true }} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[
            { required: true, message: '请输入密码' },
            { min: 6, message: '密码长度至少6位' },
          ]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Form.Item name="remember" valuePropName="checked" noStyle>
              <Checkbox>记住我</Checkbox>
            </Form.Item>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登 录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
