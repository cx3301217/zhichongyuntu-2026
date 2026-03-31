// src/components/OccupancyPredictionDashboard.js
import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Spin, message, Empty, Statistic, Tag, Input, Space, Alert, Button } from 'antd';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { ThunderboltOutlined, RiseOutlined, FallOutlined, SearchOutlined, WarningOutlined } from '@ant-design/icons';
import axios from 'axios';
import { CONFIG } from '../utils/config';
import { getCongestionConfig } from '../services/regionMapService';

const { Search } = Input;

const OccupancyPredictionDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [regions, setRegions] = useState([]);
  const [filteredRegions, setFilteredRegions] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [searchText, setSearchText] = useState('');
  const [dataUploaded, setDataUploaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const pageWrapperStyle = {
    backgroundImage: `url(${process.env.PUBLIC_URL}/bg/occupancy-bg.jpg)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    backgroundAttachment: 'fixed',
    padding: '24px',
    minHeight: 'calc(100vh - 64px)'
  };

  useEffect(() => {
    checkDataStatus();
  }, []);

  useEffect(() => {
    if (dataUploaded) {
      loadPredictions();
    }
  }, [dataUploaded]);

  useEffect(() => {
    if (searchText.trim() === '') {
      setFilteredRegions(regions);
    } else {
      const filtered = regions.filter(region => 
        region.name.toLowerCase().includes(searchText.toLowerCase()) ||
        region.district.toLowerCase().includes(searchText.toLowerCase()) ||
        region.region_id.toString().includes(searchText)
      );
      setFilteredRegions(filtered);
    }
  }, [searchText, regions]);

  const checkDataStatus = async () => {
    try {
      const response = await axios.get(`${CONFIG.API_BASE_URL}/api/data-status`);
      setDataUploaded(response.data.uploaded);
      
      if (!response.data.uploaded) {
        setLoading(false);
        message.warning('请先在管理后台上传训练数据');
      }
    } catch (error) {
      console.error('检查数据状态失败:', error);
      setLoading(false);
    }
  };

  const loadPredictions = async (refresh = false) => {
    try {
      setLoading(true);
      if (refresh) setRefreshing(true);
      
      const response = await axios.get(`${CONFIG.API_BASE_URL}/api/regions/all`, { 
        params: { refresh },
        timeout: 120000  // ⭐ 方案1：增加超时到120秒
      });
      
      if (response.data && response.data.success && response.data.regions) {
        const regionsData = response.data.regions;
        setRegions(regionsData);
        setFilteredRegions(regionsData);
        
        const predictionsData = {};

        // ⭐ 方案2：优化批量请求策略
        const batchSize = 25;  // 减少批量大小 50 → 25
        const totalBatches = Math.ceil(regionsData.length / batchSize);
        
        for (let i = 0; i < regionsData.length; i += batchSize) {
          const batchIndex = Math.floor(i / batchSize) + 1;
          const batch = regionsData.slice(i, i + batchSize);
          
          // 显示进度
          const hide = message.loading(`正在加载预测... ${Math.min(i + batchSize, regionsData.length)}/${regionsData.length}`, 0);
          
          const requests = batch.map(region => 
            axios.get(`${CONFIG.API_BASE_URL}/api/regions/${region.region_id}/predict`, { 
              params: { refresh },
              timeout: 30000  // 单个请求30秒超时
            })
              .then(predResponse => ({ regionId: region.region_id, data: predResponse.data }))
              .catch(err => ({ regionId: region.region_id, error: err }))
          );

          const results = await Promise.all(requests);
          results.forEach(res => {
            if (res.error) {
              console.error(`获取区域${res.regionId}预测失败:`, res.error);
              return;
            }
            const payload = res.data;
            if (payload && payload.success && payload.predictions) {
              predictionsData[res.regionId] = payload.predictions;
              const pred = payload.predictions;
              if (!pred || !pred.predictions || !pred.predictions.occupancy || !pred.predictions.timestamps) {
                console.warn(`区域 ${res.regionId} 数据结构不完整:`, pred);
              }
            } else {
              console.warn(`区域 ${res.regionId} 预测失败:`, payload);
            }
          });
          
          hide();
          console.log(`批次 ${batchIndex}/${totalBatches} 完成，已加载 ${Object.keys(predictionsData).length}/${regionsData.length} 个区域`);
          
          // 批次间短暂延迟，减轻服务器压力
          if (i + batchSize < regionsData.length) {
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        }
        
        setPredictions(predictionsData);
        
        // 在页面顶部显示加载完成提示（3秒后自动消失）
        const successDiv = document.createElement('div');
        successDiv.id = 'occupancy-load-status';
        successDiv.style.cssText = `
          position: fixed;
          top: 80px;
          left: 50%;
          transform: translateX(-50%);
          background: linear-gradient(135deg, #95de64 0%, #d9f7be 100%);
          color: #237804;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 14px;
          font-weight: bold;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          z-index: 9999;
          animation: fadeOut 3s ease-in-out forwards;
        `;
        successDiv.textContent = `✓ 已加载完成 ${regionsData.length} 个区域的24小时充电桩占用率实时预测`;
        
        // 添加淡出动画样式（如果还未添加）
        if (!document.getElementById('fadeout-animation-style')) {
          const style = document.createElement('style');
          style.id = 'fadeout-animation-style';
          style.textContent = `
            @keyframes fadeOut {
              0% { opacity: 1; }
              70% { opacity: 1; }
              100% { opacity: 0; visibility: hidden; }
            }
          `;
          document.head.appendChild(style);
        }
        
        // 清除旧提示
        const oldDiv = document.getElementById('occupancy-load-status');
        if (oldDiv) oldDiv.remove();
        
        document.body.appendChild(successDiv);
      }
    } catch (error) {
      console.error('加载预测数据失败:', error);
      message.error('加载失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    loadPredictions(true);
  };

  const formatChartData = (predictionData) => {
    if (!predictionData || !predictionData.predictions) return [];
    
    const { occupancy, timestamps } = predictionData.predictions;
    
    if (!timestamps || !Array.isArray(timestamps) || 
        !occupancy || !Array.isArray(occupancy)) {
      return [];
    }
    
    return timestamps.map((time, index) => ({
      time: time.split(' ')[1].substring(0, 5),
      occupancy: occupancy[index]
    }));
  };

  const calculateTrend = (predictionData) => {
    if (!predictionData || !predictionData.predictions) return 0;
    
    const occupancy = predictionData.predictions.occupancy;
    
    if (!occupancy || !Array.isArray(occupancy) || occupancy.length < 2) {
      return 0;
    }
    
    const first = occupancy[0];
    const last = occupancy[occupancy.length - 1];
    
    const trend = (last - first) / first * 100;
    return Math.round(trend * 10) / 10;  // 四舍五入到1位小数
  };

  const getAverageOccupancy = (predictionData) => {
    if (!predictionData || !predictionData.predictions) return 0;
    
    const occupancy = predictionData.predictions.occupancy;
    
    if (!occupancy || !Array.isArray(occupancy) || occupancy.length === 0) {
      return 0;
    }
    
    const sum = occupancy.reduce((acc, val) => acc + val, 0);
    return Math.round((sum / occupancy.length) * 10) / 10;  // 四舍五入到1位小数
  };

  if (!dataUploaded) {
    return (
      <div className="prediction-dashboard" style={pageWrapperStyle}>
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <ThunderboltOutlined style={{ fontSize: 24 }} />
                  <span>24小时充电桩占用率实时预测</span>
                </div>
                <Space>
                  <Button size="small" disabled>
                    刷新
                  </Button>
                </Space>
              </div>
            }
            style={{ width: '100%', height: '100%', minHeight: '800px' }}
          >
            <Empty
              style={{ padding: '250px 0' }}
              imageStyle={{ height: 80 }}
              description={
                <Space direction="vertical" size="large" style={{ width: '100%', maxWidth: 600, margin: '0 auto' }}>
                  <div style={{ fontSize: 16 }}>
                    <WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />
                    暂无预测数据
                  </div>
                  <Alert
                    message="请先上传训练数据"
                    description="请前往管理后台的数据上传页面，上传4个CSV文件以启用预测功能"
                    type="warning"
                    showIcon
                    style={{ textAlign: 'left' }}
                  />
                </Space>
              }
            />
          </Card>
        </div>
      </div>
    );
  }

  

  return (
    <div className="prediction-dashboard" style={pageWrapperStyle}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Card 
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ThunderboltOutlined style={{ fontSize: 24 }} />
              <span>24小时充电桩占用率实时预测</span>
            </div>
            <Space>
              {filteredRegions.length > 0 && (
                <Tag color="blue">共 {filteredRegions.length} 个区域</Tag>
              )}
              <Button size="small" loading={refreshing} onClick={handleRefresh}>
                刷新
              </Button>
            </Space>
          </div>
        }
        style={{ height: '100%', minHeight: '800px' }}
      >
        <div style={{ marginBottom: 24 }}>
          <Search
            placeholder="搜索区域名称、所属区域或ID"
            allowClear
            enterButton={<SearchOutlined />}
            size="large"
            onSearch={setSearchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: '100%' }}
          />
          {searchText && (
            <div style={{ marginTop: 12, color: '#666', fontSize: 14 }}>
              找到 <strong>{filteredRegions.length}</strong> 个匹配的区域
            </div>
          )}
        </div>

        <Spin spinning={loading} tip="正在加载预测数据...">
          {filteredRegions.length === 0 ? (
            <div style={{ minHeight: 480, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty 
                description={searchText ? "没有找到匹配的区域" : "暂无数据"}
                imageStyle={{ height: 80 }}
              />
            </div>
          ) : (
            <Row gutter={[24, 24]}>
              {filteredRegions.map((region) => {
                const predictionData = predictions[region.region_id];
                const chartData = formatChartData(predictionData);
                const trend = calculateTrend(predictionData);
                const avgOccupancy = getAverageOccupancy(predictionData);
                // 使用当前占用率判断拥挤度，而不是平均预测
                const congestionInfo = getCongestionConfig(region.current_occupancy ?? 0);
                
                return (
                  <Col xs={24} sm={24} md={12} lg={12} xl={8} key={region.region_id}>
                    <Card 
                      className="prediction-card"
                      bordered={false}
                      style={{ 
                        height: '100%',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                        borderRadius: 8
                      }}
                    >
                      <div style={{ marginBottom: 16 }}>
                        <h3 style={{ marginBottom: 8, fontSize: 16 }}>
                          {region.name}
                        </h3>
                        <p style={{ color: '#666', fontSize: 12, margin: 0 }}>
                          {region.district} | 充电桩数量: {region.charge_count}个
                        </p>
                      </div>

                      <Row gutter={16} style={{ marginBottom: 16 }}>
                        <Col span={8}>
                          <Statistic 
                            title="当前占用率"
                            value={region.current_occupancy}
                            precision={1}
                            suffix="%"
                            valueStyle={{ fontSize: 18 }}
                          />
                        </Col>
                        <Col span={8}>
                          <Statistic 
                            title="平均预测"
                            value={Math.round((avgOccupancy ?? 0) * 10) / 10}
                            suffix="%"
                            valueStyle={{ fontSize: 18, color: congestionInfo.color }}
                          />
                        </Col>
                        <Col span={8}>
                          <Statistic 
                            title="24h趋势"
                            value={Math.round(Math.abs(trend ?? 0) * 10) / 10}
                            suffix="%"
                            prefix={(trend ?? 0) >= 0 ? <RiseOutlined /> : <FallOutlined />}
                            valueStyle={{
                              fontSize: 18,
                              color: (trend ?? 0) >= 0 ? '#cf1322' : '#3f8600'
                            }}
                          />
                        </Col>
                      </Row>

                      <div style={{ marginBottom: 8 }}>
                        <Tag color={congestionInfo.color}>
                          {congestionInfo.text}
                        </Tag>
                      </div>

                      {chartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                          <AreaChart data={chartData}>
                            <defs>
                              <linearGradient id={`color-occ-${region.region_id}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#1890ff" stopOpacity={0.8}/>
                                <stop offset="95%" stopColor="#1890ff" stopOpacity={0.1}/>
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis 
                              dataKey="time"
                              tick={{ fontSize: 10 }}
                              interval="preserveStartEnd"
                            />
                            <YAxis 
                              domain={[0, 100]}
                              tick={{ fontSize: 10 }}
                            />
                            <Tooltip 
                              contentStyle={{ fontSize: 12 }}
                              formatter={(value) => [`${value.toFixed(1)}%`, '占用率']}
                            />
                            <Area 
                              type="monotone"
                              dataKey="occupancy"
                              stroke="#1890ff"
                              strokeWidth={2}
                              fill={`url(#color-occ-${region.region_id})`}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      ) : (
                        <Empty 
                          description="正在加载预测数据..."
                          style={{ padding: '20px 0' }}
                          imageStyle={{ height: 60 }}
                        />
                      )}
                    </Card>
                  </Col>
                );
              })}
            </Row>
          )}
        </Spin>
      </Card>
      </div>
    </div>
  );
};

export default OccupancyPredictionDashboard;