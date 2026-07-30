import { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Button, Dropdown, Avatar, Typography, Drawer, message } from 'antd';
import {
  DashboardOutlined, ApiOutlined, FileTextOutlined,
  AlertOutlined, BarChartOutlined, TeamOutlined,
  LogoutOutlined, MenuOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../features/auth/store';
import NotificationBell from '../features/alerts/NotificationBell';
import { isSoundEnabled, setSoundEnabled } from './sound';
import { authApi } from '../features/auth/api';

const { Header, Sider, Content, Footer } = AntLayout;

const allMenuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/apis', icon: <ApiOutlined />, label: '接口管理' },
  { key: '/logs', icon: <FileTextOutlined />, label: '巡检日志' },
  { key: '/alerts', icon: <AlertOutlined />, label: '告警管理' },
  { key: '/reports', icon: <BarChartOutlined />, label: '统计报表' },
  { key: '/users', icon: <TeamOutlined />, label: '用户管理' },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [collapsed, setCollapsed] = useState(window.innerWidth < 768);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [soundOn, setSoundOn] = useState(isSoundEnabled);
  const isMobile = window.innerWidth < 768;
  const isAdmin = user?.role === 'admin';

  // 非管理员不显示用户管理菜单
  const menuItems = allMenuItems.filter(item => item.key !== '/users' || isAdmin);

  useEffect(() => {
    const onResize = () => {
      const m = window.innerWidth < 768;
      setCollapsed(m);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const selectedKey = '/' + location.pathname.split('/').filter(Boolean)[0];

  const menu = (
    <Menu
      mode="inline"
      selectedKeys={[selectedKey]}
      items={menuItems}
      onClick={({ key }) => {
        navigate(key);
        if (isMobile) setMobileOpen(false);
      }}
      style={{ borderRight: 0, height: '100%' }}
    />
  );

  const userMenu = {
    items: [
      { key: 'role', label: `角色: ${user?.role}`, disabled: true },
      ...(user?.role === 'admin' ? [
        { type: 'divider' as const },
        { key: 'download_log', icon: <FileTextOutlined />, label: '下载审计日志' },
      ] : []),
      { type: 'divider' as const },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
    ],
    onClick: async ({ key }: { key: string }) => {
      if (key === 'logout') {
        logout();
        navigate('/login');
      } else if (key === 'download_log') {
        try {
          await authApi.downloadLog();
          message.success('日志下载成功');
        } catch {
          message.error('日志下载失败，可能当天暂无操作日志');
        }
      }
    },
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      {isMobile ? (
        <Drawer
          placement="left"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          width={240}
          styles={{ body: { padding: 0 } }}
        >
          {menu}
        </Drawer>
      ) : (
        <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="light" width={220}>
          <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: collapsed ? 14 : 18, borderBottom: '1px solid #f0f0f0' }}>
            {collapsed ? '📊' : '📊 API Monitor'}
          </div>
          {menu}
        </Sider>
      )}
      <AntLayout>
        <Header style={{ background: '#001529', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {isMobile && (
              <Button type="text" icon={<MenuOutlined />} onClick={() => setMobileOpen(true)} style={{ color: '#fff' }} />
            )}
            {isMobile && <Typography.Text strong style={{ color: '#fff', fontSize: 16 }}>API Monitor</Typography.Text>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <NotificationBell />
            <Button
              type="text"
              style={{ color: '#fff', fontSize: 18 }}
              onClick={() => {
                const next = !soundOn;
                setSoundEnabled(next);
                setSoundOn(next);
              }}
            >
              {soundOn ? '🔊' : '🔇'}
            </Button>
            <Dropdown menu={userMenu} placement="bottomRight">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', color: '#fff' }}>
                <Avatar size="small" style={{ backgroundColor: '#1890ff' }}>{user?.display_name?.[0] || 'U'}</Avatar>
                <span>{user?.display_name || user?.username}</span>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content style={{ margin: 16, minHeight: 280 }}>
          <Outlet />
        </Content>
        <Footer style={{ textAlign: 'center', color: '#999', padding: 12 }}>© 2026 API Monitor</Footer>
      </AntLayout>
    </AntLayout>
  );
}
