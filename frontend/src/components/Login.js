// src/components/Login.js

import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Tabs, Select } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, SafetyOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../services/authService';
import './Login.css';

// 管理员卡密
const ADMIN_CARD_KEY = 'ADMIN2025';

const Login = () => {
  const [activeTab, setActiveTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState('user');  // ⭐ 追踪选择的角色
  const navigate = useNavigate();

  const onLogin = async (values) => {
    setLoading(true);
    try {
      const result = login(values.username, values.password);
      if (result.success) {
        message.success('登录成功！');
        if (result.user.role === 'admin') {
          navigate('/admin/dashboard');
        } else {
          navigate('/user/map');
        }
      } else {
        message.error(result.message);
      }
    } catch (error) {
      message.error('登录失败');
    } finally {
      setLoading(false);
    }
  };

  const onRegister = async (values) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次密码输入不一致');
      return;
    }

    // ⭐⭐⭐ 验证管理员卡密
    if (values.role === 'admin') {
      if (!values.adminKey) {
        message.error('请输入管理员卡密！');
        return;
      }
      
      if (values.adminKey !== ADMIN_CARD_KEY) {
        message.error('管理员卡密错误，无法注册管理员账号！');
        return;
      }
      
      message.success('管理员卡密验证通过');
    }
    
    setLoading(true);
    try {
      const result = register(values.username, values.password, values.email, values.role || 'user');
      if (result.success) {
        message.success('注册成功！请登录');
        setActiveTab('login');
      } else {
        message.error(result.message);
      }
    } catch (error) {
      message.error('注册失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="login-container custom-bg"
      style={{ backgroundImage: `url(${process.env.PUBLIC_URL}/login-bg.jpg)` }}
    >
      <Card style={{ 
        width: 400, 
        minHeight: 520,
        boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
        borderRadius: 12,
        background: 'rgba(255,255,255,0.95)'
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          {/* 使用SVG渐变文字 - 彻底解决曼哈顿度问题 */}
          <svg width="100%" height="60" xmlns="http://www.w3.org/2000/svg" style={{ marginBottom: 16 }}>
            <defs>
              <linearGradient id="textGradient1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: '#52c41a', stopOpacity: 1 }} />
                <stop offset="100%" style={{ stopColor: '#1890ff', stopOpacity: 1 }} />
              </linearGradient>
            </defs>
            <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" 
                  fill="url(#textGradient1)" fontSize="36" fontWeight="bold" letterSpacing="4"
                  fontFamily="Microsoft YaHei, PingFang SC, sans-serif">
              智充云图
            </text>
          </svg>
          
          <svg width="100%" height="55" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="textGradient2" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style={{ stopColor: '#52c41a', stopOpacity: 1 }} />
                <stop offset="100%" style={{ stopColor: '#1890ff', stopOpacity: 1 }} />
              </linearGradient>
            </defs>
            <text x="50%" y="30%" dominantBaseline="middle" textAnchor="middle" 
                  fill="url(#textGradient2)" fontSize="13" fontWeight="500"
                  fontFamily="Microsoft YaHei, PingFang SC, Source Han Sans CN, sans-serif">
              基于TFT的城市级新能源汽车充电桩网络服务拥挤度可视化
            </text>
            <text x="50%" y="70%" dominantBaseline="middle" textAnchor="middle" 
                  fill="url(#textGradient2)" fontSize="13" fontWeight="500"
                  fontFamily="Microsoft YaHei, PingFang SC, Source Han Sans CN, sans-serif">
              信息系统
            </text>
          </svg>
        </div>
        
        <Tabs activeKey={activeTab} onChange={setActiveTab} centered>
          <Tabs.TabPane tab="登录" key="login">
            <Form onFinish={onLogin} size="large">
              <Form.Item
                name="username"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input prefix={<UserOutlined />} placeholder="用户名" />
              </Form.Item>
              
              <Form.Item
                name="password"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="密码" />
              </Form.Item>
              
              <Form.Item>
                <Button type="primary" htmlType="submit" block loading={loading}>
                  登录
                </Button>
              </Form.Item>
            </Form>
          </Tabs.TabPane>
          
          <Tabs.TabPane tab="注册" key="register">
            <Form onFinish={onRegister} size="large">
              <Form.Item
                name="username"
                rules={[
                  { required: true, message: '请输入用户名' },
                  { min: 3, message: '用户名至少3个字符' }
                ]}
              >
                <Input prefix={<UserOutlined />} placeholder="用户名" />
              </Form.Item>
              
              <Form.Item
                name="email"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '请输入有效的邮箱' }
                ]}
              >
                <Input prefix={<MailOutlined />} placeholder="邮箱" />
              </Form.Item>
              
              <Form.Item
                name="password"
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码至少6个字符' }
                ]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="密码" />
              </Form.Item>
              
              <Form.Item
                name="confirmPassword"
                rules={[{ required: true, message: '请确认密码' }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
              </Form.Item>
              
              <Form.Item
                name="role"
                rules={[{ required: true, message: '请选择角色' }]}
              >
                <Select 
                  placeholder="选择角色"
                  size="large"
                  onChange={(value) => setSelectedRole(value)}
                >
                  <Select.Option value="user">普通用户</Select.Option>
                  <Select.Option value="admin">管理员</Select.Option>
                </Select>
              </Form.Item>

              {/* ⭐⭐⭐ 管理员卡密输入框（仅选择管理员时显示） */}
              {selectedRole === 'admin' && (
                <>
                  <Form.Item
                    name="adminKey"
                    rules={[{ required: true, message: '请输入管理员卡密' }]}
                  >
                    <Input.Password
                      prefix={<SafetyOutlined />}
                      placeholder="请输入管理员卡密"
                      style={{
                        borderColor: '#ff4d4f',
                        boxShadow: '0 0 0 2px rgba(255, 77, 79, 0.1)'
                      }}
                    />
                  </Form.Item>
                  <div style={{ 
                    marginTop: -16,
                    marginBottom: 24,
                    fontSize: 12, 
                    color: '#ff4d4f',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4
                  }}>
                    <SafetyOutlined />
                    注册管理员账号需要提供管理员卡密
                  </div>
                </>
              )}
              
              <Form.Item>
                <Button type="primary" htmlType="submit" block loading={loading}>
                  注册
                </Button>
              </Form.Item>
            </Form>
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </div>
  );
};

export default Login;