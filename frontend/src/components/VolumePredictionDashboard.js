// src/components/VolumePredictionDashboard.js
import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Spin, message, Empty, Statistic, Tag, Input, Space, Alert, Button } from 'antd';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { ThunderboltOutlined, RiseOutlined, FallOutlined, SearchOutlined, WarningOutlined } from '@ant-design/icons';
import axios from 'axios';
import { CONFIG } from '../utils/config';

const { Search } = Input;

const VolumePredictionDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [regions, setRegions] = useState([]);
  const [filteredRegions, setFilteredRegions] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [searchText, setSearchText] = useState('');
  const [dataUploaded, setDataUploaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const pageWrapperStyle = {
    backgroundImage: `url(${process.env.PUBLIC_URL}/bg/volume-bg.jpg)`,
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
            if (payload && payload.success) {
              predictionsData[res.regionId] = payload.predictions;
              const pred = payload.predictions;
              if (!pred || !pred.predictions || !pred.predictions.volume || !pred.predictions.timestamps) {
                console.warn(`区域 ${res.regionId} 电量负荷数据结构不完整:`, pred);
              }
            } else {
              console.warn(`区域 ${res.regionId} 电量负荷预测失败:`, payload);
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
        successDiv.id = 'volume-load-status';
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
        successDiv.textContent = `✓ 已加载完成 ${regionsData.length} 个区域的24小时充电桩电量负荷实时预测`;
        
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
        const oldDiv = document.getElementById('volume-load-status');
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
    
    const { volume, timestamps } = predictionData.predictions;
    
    if (!timestamps || !Array.isArray(timestamps) || 
        !volume || !Array.isArray(volume)) {
      return [];
    }
    
    return timestamps.map((time, index) => ({
      time: time.split(' ')[1].substring(0, 5),
      volume: volume[index]
    }));
  };

  const calculateTrend = (predictionData) => {
    if (!predictionData || !predictionData.predictions) return 0;
    
    const volume = predictionData.predictions.volume;
    
    if (!volume || !Array.isArray(volume) || volume.length < 2) {
      return 0;
    }
    
    const first = volume[0];
    const last = volume[volume.length - 1];
    
    const trend = (last - first) / first * 100;
    return Math.round(trend * 10) / 10;  // 四舍五入到1位小数
  };

  const getAverageVolume = (predictionData) => {
    if (!predictionData || !predictionData.predictions) return 0;
    
    const volume = predictionData.predictions.volume;
    
    if (!volume || !Array.isArray(volume) || volume.length === 0) {
      return 0;
    }
    
    const sum = volume.reduce((acc, val) => acc + val, 0);
    return Math.round((sum / volume.length) * 10) / 10;  // 四舍五入到1位小数
  };

  const getPeakVolume = (predictionData) => {
    if (!predictionData || !predictionData.predictions) return 0;
    
    const volume = predictionData.predictions.volume;
    
    if (!volume || !Array.isArray(volume) || volume.length === 0) {
      return 0;
    }
    
    return Math.round(Math.max(...volume) * 10) / 10;  // 四舍五入到1位小数
  };

  const getVolumeLevel = (volume) => {
    const vol = parseFloat(volume);
    if (vol < 50) {
      return { text: '低负荷', color: 'success' };
    } else if (vol < 100) {
      return { text: '中等负荷', color: 'warning' };
    } else if (vol < 150) {
      return { text: '高负荷', color: 'error' };
    } else {
      return { text: '超高负荷', color: 'error' };
    }
  };

  if (!dataUploaded) {
    return (
      <div className="volume-prediction-dashboard" style={pageWrapperStyle}>
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <ThunderboltOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
                  <span>24小时充电桩电量负荷实时预测</span>
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
    <div className="volume-prediction-dashboard" style={pageWrapperStyle}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Card 
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ThunderboltOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
              <span>24小时充电桩电量负荷实时预测</span>
            </div>
            <Space>
              {filteredRegions.length > 0 && (
                <Tag color="red">共 {filteredRegions.length} 个区域</Tag>
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
                const avgVolume = getAverageVolume(predictionData);
                const peakVolume = getPeakVolume(predictionData);
                // 使用当前负荷或平均负荷（取较大值）判断负荷等级
                const volumeForLevel = Math.max(avgVolume, region.current_volume ?? 0);
                const volumeLevel = getVolumeLevel(volumeForLevel);
                
                return (
                  <Col xs={24} sm={24} md={12} lg={12} xl={8} key={region.region_id}>
                    <Card 
                      className="volume-prediction-card"
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
                            title="平均负荷"
                            value={Math.round((avgVolume ?? 0) * 10) / 10}
                            suffix="kWh"
                            valueStyle={{ fontSize: 18, color: '#ff4d4f' }}
                          />
                        </Col>
                        <Col span={8}>
                          <Statistic 
                            title="峰值负荷"
                            value={Math.round((peakVolume ?? 0) * 10) / 10}
                            suffix="kWh"
                            valueStyle={{ fontSize: 18, color: '#cf1322' }}
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
                        <Tag color={volumeLevel.color}>
                          {volumeLevel.text}
                        </Tag>
                      </div>

                      {chartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                          <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis 
                              dataKey="time"
                              tick={{ fontSize: 10 }}
                              interval="preserveStartEnd"
                            />
                            <YAxis 
                              tick={{ fontSize: 10 }}
                            />
                            <Tooltip 
                              contentStyle={{ fontSize: 12 }}
                              formatter={(value) => [`${value.toFixed(1)} kWh`, '电量负荷']}
                            />
                            <Line 
                              type="monotone"
                              dataKey="volume"
                              stroke="#ff4d4f"
                              strokeWidth={2}
                              dot={{ r: 3 }}
                              activeDot={{ r: 5 }}
                            />
                          </LineChart>
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

export default VolumePredictionDashboard;