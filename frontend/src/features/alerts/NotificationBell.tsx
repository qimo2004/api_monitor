import { useEffect, useRef, useState } from 'react';
import { Badge, Dropdown, List, Typography } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { alertApi, type AlertItem } from './api';
import { useAlertStore } from './store';
import { playAlertSound } from '../../shared/sound';

export default function NotificationBell() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const pendingCount = useAlertStore((s) => s.pendingCount);
  const setPendingCount = useAlertStore((s) => s.setPendingCount);
  const refreshTrigger = useAlertStore((s) => s.refreshTrigger);
  const prevAlertIds = useRef<Set<number>>(new Set());
  const [hasNewAlert, setHasNewAlert] = useState(false);
  const originTitle = 'API Monitor';

  // 页面标题闪烁效果
  useEffect(() => {
    if (!hasNewAlert) {
      document.title = originTitle;
      return;
    }

    const blinkTimer = setInterval(() => {
      document.title = document.title === originTitle
        ? '⚠ 有新告警 - API Monitor'
        : originTitle;
    }, 1000);

    return () => clearInterval(blinkTimer);
  }, [hasNewAlert]);

  // 页面焦点监听：重新获得焦点时清除标题闪烁
  useEffect(() => {
    const onFocus = () => setHasNewAlert(false);
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);

  const fetchPending = async () => {
    try {
      const data = await alertApi.list({ status: 'pending', page_size: 5 });
      const items = data.items || [];
      const currentIds = new Set<number>(items.map((a: AlertItem) => a.id));
      // 检测是否有新告警（不在上一次列表中的）
      const hasNew = items.some((a: AlertItem) => !prevAlertIds.current.has(a.id));
      if (hasNew && prevAlertIds.current.size > 0) {
        playAlertSound();
        setHasNewAlert(true);
      }
      prevAlertIds.current = currentIds;
      setAlerts(items);
      setPendingCount(data.total || 0);
    } catch { /* ignore */ }
  };

  // 首次加载 + 监听外部刷新触发（告警管理界面解决告警后）+ 定时轮询（30秒）
  useEffect(() => {
    fetchPending();
    const timer = setInterval(fetchPending, 30000);
    return () => clearInterval(timer);
  }, [refreshTrigger]);

  return (
    <Dropdown
      placement="bottomRight"
      popupRender={() => (
        <div style={{ width: 320, maxHeight: 400, overflow: 'auto', background: '#fff', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
          <div style={{ padding: '8px 16px', fontWeight: 600, borderBottom: '1px solid #f0f0f0' }}>
            待处理告警 ({pendingCount})
          </div>
          <List
            dataSource={alerts}
            locale={{ emptyText: '🎉 目前没有待处理的告警' }}
            renderItem={(item) => (
              <List.Item
                style={{ cursor: 'pointer', padding: '8px 16px' }}
                onClick={() => navigate(`/alerts?api_id=${item.api_id}`)}
              >
                <List.Item.Meta
                  title={
                    <Typography.Text ellipsis style={{ maxWidth: 260 }}>
                      [{item.alert_type}] {item.message}
                    </Typography.Text>
                  }
                  description={item.api_name}
                />
              </List.Item>
            )}
          />
        </div>
      )}
    >
      <Badge count={pendingCount} size="small" offset={[-4, 4]}>
        <BellOutlined style={{ fontSize: 20, color: '#fff', cursor: 'pointer' }} />
      </Badge>
    </Dropdown>
  );
}
