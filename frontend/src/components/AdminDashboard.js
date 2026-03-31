// src/components/AdminDashboard.js
import React, { useState } from 'react';
import { Layout, Menu, Button } from 'antd';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  UploadOutlined,
  EnvironmentOutlined,
  ThunderboltOutlined,
  FireOutlined,
  AimOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined
} from '@ant-design/icons';

// ⭐ 确保所有导入都是默认导入
import DataUpload from './DataUpload';
import MapMonitor from './MapMonitor';
import OccupancyPredictionDashboard from './OccupancyPredictionDashboard';
import VolumePredictionDashboard from './VolumePredictionDashboard';
import RecommendPage from './RecommendPage';

const { Header, Sider, Content } = Layout;

const AdminDashboard = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [

    {
      key: '/admin/map',
      icon: <EnvironmentOutlined />,
      label: '区域地图'
    },
    {
      key: '/admin/occupancy-prediction',
      icon: <ThunderboltOutlined />,
      label: '占用率预测'
    },
    {
      key: '/admin/volume-prediction',
      icon: <FireOutlined />,
      label: '电量负荷预测'
    },
    {
      key: '/admin/recommend',
      icon: <AimOutlined />,
      label: '智能推荐'
    },
    {
      key: '/admin/upload',
      icon: <UploadOutlined />,
      label: '数据上传'
    }
  ];

  const handleMenuClick = ({ key }) => {
    navigate(key);
  };

  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated');
    navigate('/login');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        background: 'linear-gradient(90deg, #e6fffb 0%, #d9f7be 100%)', 
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        borderBottom: '2px solid #b7eb8f',
        position: 'sticky',
        top: 0,
        zIndex: 100
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <svg width="600" height="40" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="adminHeaderGradient1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: '#52c41a', stopOpacity: 1 }} />
                <stop offset="100%" style={{ stopColor: '#1890ff', stopOpacity: 1 }} />
              </linearGradient>
            </defs>
            <text x="0" y="20" dominantBaseline="middle" 
                  fill="url(#adminHeaderGradient1)" fontSize="18" fontWeight="bold" letterSpacing="2"
                  fontFamily="Microsoft YaHei, PingFang SC, sans-serif">
              智充云图
            </text>
            <text x="100" y="20" dominantBaseline="middle" 
                  fill="url(#adminHeaderGradient1)" fontSize="13" fontWeight="500"
                  fontFamily="Microsoft YaHei, PingFang SC, Source Han Sans CN, sans-serif">
              基于TFT的城市级新能源汽车充电桩网络服务拥挤度可视化信息系统
            </text>
          </svg>
        </div>
        
        <div style={{ flex: 1 }} />
        <Menu
          mode="horizontal"
          selectedKeys={[location.pathname]}
          onClick={handleMenuClick}
          items={menuItems}
          style={{ 
            border: 'none',
            background: 'transparent',
            marginRight: 16
          }}
        />
        
        <Button 
          type="primary"
          danger
          icon={<LogoutOutlined />}
          onClick={handleLogout}
        >
          退出登录
        </Button>
      </Header>

      <Content style={{ 
        padding: 0, 
        minHeight: 'calc(100vh - 64px)' 
      }}>
        <Routes>
          <Route path="dashboard" element={<MapMonitor />} />
          <Route path="map" element={<MapMonitor />} />
          <Route path="occupancy-prediction" element={<OccupancyPredictionDashboard />} />
          <Route path="volume-prediction" element={<VolumePredictionDashboard />} />
          <Route path="recommend" element={<RecommendPage />} />
          <Route path="upload" element={<DataUpload />} />
          <Route path="/" element={<MapMonitor />} />
        </Routes>
      </Content>
    </Layout>
  );
};

export default AdminDashboard;