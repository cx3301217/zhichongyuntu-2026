// src/components/UserPage.js
import React from 'react';
import { Layout, Menu } from 'antd';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { 
  EnvironmentOutlined, 
  ThunderboltOutlined,
  AimOutlined,
  LogoutOutlined 
} from '@ant-design/icons';

// ⭐ 确保所有导入都是默认导入
import RegionMap from './RegionMap';
import OccupancyPredictionDashboard from './OccupancyPredictionDashboard';
import RecommendPage from './RecommendPage';

const { Header, Content } = Layout;

const UserPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/user/map',
      icon: <EnvironmentOutlined />,
      label: '区域地图'
    },
    {
      key: '/user/prediction',
      icon: <ThunderboltOutlined />,
      label: '占用率预测'
    },
    {
      key: '/user/recommend',
      icon: <AimOutlined />,
      label: '智能推荐'
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      style: { marginLeft: 'auto' }
    }
  ];

  const handleMenuClick = ({ key }) => {
    if (key === 'logout') {
      localStorage.removeItem('isAuthenticated');
      navigate('/login');
    } else {
      navigate(key);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        background: 'linear-gradient(90deg, #e6fffb 0%, #d9f7be 100%)', 
        padding: '0 24px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '2px solid #b7eb8f'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ThunderboltOutlined style={{ fontSize: 24, color: '#52c41a' }} />
          <svg width="600" height="40" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="headerGradient1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: '#52c41a', stopOpacity: 1 }} />
                <stop offset="100%" style={{ stopColor: '#1890ff', stopOpacity: 1 }} />
              </linearGradient>
            </defs>
            <text x="0" y="20" dominantBaseline="middle" 
                  fill="url(#headerGradient1)" fontSize="18" fontWeight="bold" letterSpacing="2"
                  fontFamily="Microsoft YaHei, PingFang SC, sans-serif">
              智充云图
            </text>
            <text x="100" y="20" dominantBaseline="middle" 
                  fill="url(#headerGradient1)" fontSize="13" fontWeight="500"
                  fontFamily="Microsoft YaHei, PingFang SC, Source Han Sans CN, sans-serif">
              基于TFT的城市级新能源汽车充电桩网络服务拥挤度可视化信息系统
            </text>
          </svg>
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[location.pathname]}
          onClick={handleMenuClick}
          items={menuItems}
          style={{ 
            border: 'none',
            background: 'transparent'
          }}
        />
      </Header>

      <Content style={{ padding: 0 }}>
        <Routes>
          <Route path="map" element={
            <div style={{
              backgroundImage: `url(${process.env.PUBLIC_URL}/bg/map-bg.jpg)`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat',
              backgroundAttachment: 'fixed',
              padding: '24px',
              minHeight: 'calc(100vh - 64px)'
            }}>
              <div style={{ maxWidth: 1400, margin: '0 auto' }}>
                <RegionMap />
              </div>
            </div>
          } />
          <Route path="prediction" element={<OccupancyPredictionDashboard />} />
          <Route path="recommend" element={<RecommendPage />} />
          <Route path="/" element={
            <div style={{
              backgroundImage: `url(${process.env.PUBLIC_URL}/bg/map-bg.jpg)`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat',
              backgroundAttachment: 'fixed',
              padding: '24px',
              minHeight: 'calc(100vh - 64px)'
            }}>
              <div style={{ maxWidth: 1400, margin: '0 auto' }}>
                <RegionMap />
              </div>
            </div>
          } />
        </Routes>
      </Content>
    </Layout>
  );
};

export default UserPage;