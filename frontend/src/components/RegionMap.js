// src/components/RegionMap.js
import React, { useEffect, useState, useRef } from 'react';
import { Card, Spin, Alert, Button, Modal, Statistic, Row, Col, message, Empty, Space } from 'antd';
import { EnvironmentOutlined, ReloadOutlined, CloseOutlined, WarningOutlined } from '@ant-design/icons';
import axios from 'axios';
import { 
  getAllRegions, 
  getRegion24hPrediction,
  recommendRegions,
  getCongestionConfig, 
  loadAmapScript 
} from '../services/regionMapService';
import { CONFIG } from '../utils/config';

const RegionMap = () => {
  const [loading, setLoading] = useState(true);
  const [regions, setRegions] = useState([]);
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [prediction24h, setPrediction24h] = useState(null);
  const [predictionsCache, setPredictionsCache] = useState({}); // region_id -> 24h prediction
  const [modalVisible, setModalVisible] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [dataUploaded, setDataUploaded] = useState(false);  // ⭐ 新增状态
  const [refreshing, setRefreshing] = useState(false);
  
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const circlesRef = useRef([]);
  const markersRef = useRef([]);

  useEffect(() => {
    checkDataStatusAndInitMap();
  }, []);

  // ⭐⭐⭐ 新增：检查数据状态并初始化地图
  const checkDataStatusAndInitMap = async () => {
    try {
      setLoading(true);
      
      // 检查数据是否上传
      const response = await axios.get(`${CONFIG.API_BASE_URL}/api/data-status`);
      const uploaded = response.data.uploaded;
      setDataUploaded(uploaded);
      
      if (!uploaded) {
        setLoading(false);
        message.warning('请先在管理后台上传训练数据');
        return;
      }
      
      // 数据已上传，初始化地图
      await initMap();
      
    } catch (error) {
      console.error('检查数据状态失败:', error);
      setLoading(false);
    }
  };

  const initMap = async () => {
    try {
      setLoading(true);
      
      // 1. 加载高德地图
      console.log('📍 加载高德地图...');
      const AMap = await loadAmapScript();
      
      // 2. 创建地图实例
      console.log('🗺️ 创建地图实例...');
      const map = new AMap.Map('region-map-container', {
        zoom: CONFIG.DEFAULT_ZOOM,
        center: [CONFIG.MAP_CENTER.longitude, CONFIG.MAP_CENTER.latitude],
        mapStyle: 'amap://styles/normal'
      });
      
      mapInstance.current = map;
      
      // 3. 添加图例
      addLegend(map);
      
      // 4. 加载区域数据
      console.log('📊 加载区域数据...');
      const regionsData = await getAllRegions(false);
      setRegions(regionsData);
      
      // 5. 渲染区域
      if (regionsData.length > 0) {
        renderRegions(AMap, map, regionsData);
      } else {
        message.error('未能加载区域数据，请检查后端是否正常运行');
      }
      
      setLoading(false);
      console.log('✅ 地图初始化完成');
      
    } catch (error) {
      console.error('❌ 地图初始化失败:', error);
      message.error('地图初始化失败: ' + error.message);
      setLoading(false);
    }
  };

  const addLegend = (map) => {
    const legend = document.createElement('div');
    legend.style.cssText = `
      position: absolute;
      bottom: 20px;
      right: 20px;
      background: white;
      padding: 15px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      z-index: 1000;
    `;
    
    legend.innerHTML = `
      <h4 style="margin: 0 0 10px 0; font-size: 14px;">拥挤度图例</h4>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div style="display: flex; align-items: center;">
          <span style="width: 20px; height: 15px; background: ${CONFIG.CONGESTION_COLORS.low.color}; margin-right: 8px; border-radius: 2px;"></span>
          <span style="font-size: 12px;">${CONFIG.CONGESTION_COLORS.low.text} (&lt;30%)</span>
        </div>
        <div style="display: flex; align-items: center;">
          <span style="width: 20px; height: 15px; background: ${CONFIG.CONGESTION_COLORS.medium.color}; margin-right: 8px; border-radius: 2px;"></span>
          <span style="font-size: 12px;">${CONFIG.CONGESTION_COLORS.medium.text} (30-60%)</span>
        </div>
        <div style="display: flex; align-items: center;">
          <span style="width: 20px; height: 15px; background: ${CONFIG.CONGESTION_COLORS.high.color}; margin-right: 8px; border-radius: 2px;"></span>
          <span style="font-size: 12px;">${CONFIG.CONGESTION_COLORS.high.text} (60-85%)</span>
        </div>
        <div style="display: flex; align-items: center;">
          <span style="width: 20px; height: 15px; background: ${CONFIG.CONGESTION_COLORS['very-high'].color}; margin-right: 8px; border-radius: 2px;"></span>
          <span style="font-size: 12px;">${CONFIG.CONGESTION_COLORS['very-high'].text} (&gt;85%)</span>
        </div>
      </div>
    `;
    
    document.getElementById('region-map-container').appendChild(legend);
  };

  const renderRegions = (AMap, map, regionsData) => {
    console.log(`🎨 渲染 ${regionsData.length} 个区域...`);

    // 清除旧的标记
    circlesRef.current.forEach(c => c.setMap(null));
    markersRef.current.forEach(m => m.setMap(null));
    circlesRef.current = [];
    markersRef.current = [];

    let renderedCount = 0;

    regionsData.forEach((region, index) => {
      // 若无预测，用中性样式渲染（灰色、无百分比），保证275个区域全部显示
      const hasPrediction = region.current_occupancy !== null && region.current_occupancy !== undefined;
      const occupancy = hasPrediction ? region.current_occupancy : 0;
      const congestionConfig = hasPrediction ? getCongestionConfig(occupancy) : {
        color: '#c0c4cc',
        fillColor: 'rgba(192,196,204,0.25)',
        text: 'unknown',
      };

      // 创建圆形覆盖物
      const circle = new AMap.Circle({
        center: [region.longitude, region.latitude],
        radius: CONFIG.REGION_CIRCLE_RADIUS,
        strokeColor: congestionConfig.color,
        strokeWeight: 2,
        fillColor: congestionConfig.fillColor,
        fillOpacity: 0.4,
        cursor: 'pointer',
        extData: region
      });

      // 创建文字标记
      const marker = new AMap.Marker({
        position: [region.longitude, region.latitude],
        content: `<div style="
          background: white;
          padding: 3px 8px;
          border-radius: 4px;
          border: 1px solid ${congestionConfig.color};
          font-size: 12px;
          color: ${congestionConfig.color};
          font-weight: bold;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">${hasPrediction ? occupancy.toFixed(0) + '%' : '—'}</div>`,
        offset: new AMap.Pixel(-20, -10),
        extData: region
      });

      // 点击事件
      circle.on('click', () => handleRegionClick(region));
      marker.on('click', () => handleRegionClick(region));

      circle.setMap(map);
      marker.setMap(map);

      circlesRef.current.push(circle);
      markersRef.current.push(marker);
      renderedCount++;

      if (renderedCount % 50 === 0) {
        console.log(`   进度: ${renderedCount}/${regionsData.length}`);
      }
    });

    console.log('✅ 区域渲染完成');
    
    // 在地图上叠加显示加载完成信息
    if (renderedCount > 0) {
      const infoDiv = document.createElement('div');
      infoDiv.id = 'map-load-status';
      infoDiv.style.cssText = `
        position: absolute;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #95de64 0%, #d9f7be 100%);
        color: #237804;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1001;
        animation: fadeOut 3s ease-in-out forwards;
      `;
      infoDiv.textContent = `✓ 已加载完成 ${renderedCount} 个区域`;
      
      // 添加淡出动画
      const style = document.createElement('style');
      style.textContent = `
        @keyframes fadeOut {
          0% { opacity: 1; }
          70% { opacity: 1; }
          100% { opacity: 0; visibility: hidden; }
        }
      `;
      document.head.appendChild(style);
      
      const mapContainer = document.getElementById('region-map-container');
      if (mapContainer) {
        // 清除旧的状态提示
        const oldStatus = document.getElementById('map-load-status');
        if (oldStatus) oldStatus.remove();
        
        mapContainer.appendChild(infoDiv);
      }
    } else {
      message.warning('没有可显示的预测数据，请先上传训练数据');
    }
  };

  const handleRegionClick = async (region) => {
    console.log('🖱️ 点击区域:', region.region_id);
    setSelectedRegion(region);
    setModalVisible(true);
    setPrediction24h(null);
    
    // 加载24小时预测
    try {
      // 优先用本地缓存
      if (predictionsCache[region.region_id]) {
        setPrediction24h(predictionsCache[region.region_id]);
        return;
      }
      const prediction = await getRegion24hPrediction(region.region_id, false);
      console.log('📈 获取到预测数据:', prediction);
      setPrediction24h(prediction);
      setPredictionsCache(prev => ({ ...prev, [region.region_id]: prediction }));
    } catch (error) {
      console.error('获取预测失败:', error);
      message.error('获取预测数据失败');
    }
  };

  const handleRefresh = () => {
    console.log('🔄 刷新数据...');
    setRefreshing(true);
    setLoading(true);
    const hide = message.loading('正在刷新预测，请稍候...', 0);
    // 强制刷新：清空本地缓存，并请求服务端刷新
    setPredictionsCache({});
    (async () => {
      try {
        const AMap = await loadAmapScript();
        const refreshed = await getAllRegions(true);
        setRegions(refreshed);
        if (mapInstance.current) {
          renderRegions(AMap, mapInstance.current, refreshed);
        }
        hide();
        message.success('已刷新最新预测');
      } catch (e) {
        console.error(e);
        hide();
        message.error('刷新失败');
      } finally {
        setRefreshing(false);
        setLoading(false);
      }
    })();
  };

  const handleGetRecommendations = async () => {
    try {
      if (navigator.geolocation) {
        message.info('正在获取您的位置...');
        
        navigator.geolocation.getCurrentPosition(
          async (position) => {
            const { latitude, longitude } = position.coords;
            
            console.log('📍 用户位置:', latitude, longitude);
            message.success(`位置获取成功: ${latitude.toFixed(4)}, ${longitude.toFixed(4)}`);
            
            // 获取推荐
            const recs = await recommendRegions(latitude, longitude, 5);
            setRecommendations(recs);
            
            if (recs.length > 0) {
              message.success(`为您推荐了 ${recs.length} 个区域`);
              highlightRecommendations(recs);
            } else {
              message.warning('未找到推荐区域');
            }
          },
          (error) => {
            console.error('获取位置失败:', error);
            message.error('无法获取您的位置，请允许位置权限');
          }
        );
      } else {
        message.error('您的浏览器不支持地理定位');
      }
    } catch (error) {
      console.error('推荐失败:', error);
      message.error('推荐失败: ' + error.message);
    }
  };

  const highlightRecommendations = (recs) => {
    console.log('🎯 高亮推荐区域:', recs.map(r => r.region_id));
    
    if (mapInstance.current && recs.length > 0) {
      const bounds = new window.AMap.Bounds(
        [recs[0].longitude, recs[0].latitude],
        [recs[0].longitude, recs[0].latitude]
      );
      
      recs.forEach(rec => {
        bounds.extend([rec.longitude, rec.latitude]);
      });
      
      mapInstance.current.setBounds(bounds);
    }
  };

  const renderPredictionChart = () => {
    if (!prediction24h) {
      return (
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Spin tip="加载预测数据..." />
        </div>
      );
    }

    if (!prediction24h.predictions) {
      return (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#ff4d4f' }}>
          预测数据格式错误
        </div>
      );
    }

    const { occupancy, timestamps } = prediction24h.predictions;

    if (!occupancy || !Array.isArray(occupancy) || occupancy.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#ff4d4f' }}>
          占用率数据不可用
        </div>
      );
    }

    if (!timestamps || !Array.isArray(timestamps) || timestamps.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#ff4d4f' }}>
          时间戳数据不可用
        </div>
      );
    }

    if (occupancy.length !== timestamps.length) {
      return (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#ff4d4f' }}>
          数据长度不匹配
        </div>
      );
    }

    return (
      <div style={{ marginTop: 20 }}>
        <h4>未来24小时占用率预测</h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(8, 1fr)', 
          gap: '8px',
          marginTop: 10
        }}>
          {occupancy.slice(0, 24).map((occ, idx) => {
            const config = getCongestionConfig(occ);
            const timeStr = timestamps[idx].split(' ')[1]?.substring(0, 5) || `${idx}:00`;
            
            return (
              <div key={idx} style={{
                padding: '8px',
                borderRadius: '4px',
                backgroundColor: config.backgroundColor || config.fillColor,
                border: `1px solid ${config.color}`,
                textAlign: 'center',
                fontSize: '12px'
              }}>
                <div style={{ fontWeight: 'bold' }}>{timeStr}</div>
                <div style={{ color: config.color, fontWeight: 'bold' }}>
                  {occ.toFixed(0)}%
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // ⭐⭐⭐ 新增：数据未上传时的显示
  if (!dataUploaded) {
    return (
      <Card>
        <Empty
          description={
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div style={{ fontSize: 16 }}>
                <WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />
                暂无区域数据
              </div>
              <Alert
                message="请先上传训练数据"
                description="请前往管理后台的数据上传页面，上传CSV文件以启用区域地图功能"
                type="warning"
                showIcon
                style={{ textAlign: 'left' }}
              />
            </Space>
          }
        />
      </Card>
    );
  }

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>深圳市275个交通区域充电桩监控</span>
          <div>
            <Button 
              icon={<EnvironmentOutlined />} 
              onClick={handleGetRecommendations}
              style={{ marginRight: 8 }}
              type="primary"
            >
              智能推荐
            </Button>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={handleRefresh}
              loading={refreshing}
            >
              刷新
            </Button>
          </div>
        </div>
      }
      style={{ height: '100%', minHeight: '800px' }}
    >
      <Spin spinning={loading} tip={refreshing ? '正在刷新预测...' : '加载中...'}>
        <div 
          id="region-map-container" 
          ref={mapRef}
          style={{ 
            width: '100%', 
            height: '700px',
            position: 'relative',
            borderRadius: '8px',
            overflow: 'hidden'
          }}
        />
        
        {recommendations.length > 0 && (
          <Alert
            message="推荐结果"
            description={
              <div>
                为您推荐以下区域（按综合评分排序）：
                <ul style={{ marginTop: 8, marginBottom: 0 }}>
                  {recommendations.slice(0, 3).map((rec, idx) => (
                    <li key={rec.region_id}>
                      {rec.name} - 距离{rec.distance.toFixed(2)}km，占用率{rec.current_occupancy.toFixed(0)}%
                    </li>
                  ))}
                </ul>
              </div>
            }
            type="info"
            showIcon
            closable
            onClose={() => setRecommendations([])}
            style={{ marginTop: 16 }}
          />
        )}
      </Spin>
      
      {/* 区域详情弹窗 */}
      <Modal
        key={selectedRegion?.region_id || 'region-modal'}
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{selectedRegion?.name || ''}</span>
            <Button 
              type="text" 
              icon={<CloseOutlined />} 
              onClick={() => setModalVisible(false)}
            />
          </div>
        }
        open={modalVisible}
        onCancel={() => { setModalVisible(false); setSelectedRegion(null); setPrediction24h(null); }}
        footer={null}
        width={900}
        closable={false}
        destroyOnClose
      >
        {selectedRegion && (
          <div>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic 
                  title="当前占用率" 
                  value={Math.round(((selectedRegion.current_occupancy ?? 0)) * 10) / 10} 
                  suffix="%" 
                  valueStyle={{ 
                    color: getCongestionConfig(selectedRegion.current_occupancy).color 
                  }}
                />
              </Col>
              <Col span={8}>
                <Statistic 
                  title="充电负荷" 
                  value={Math.round(((selectedRegion.current_volume ?? 0)) * 10) / 10} 
                  suffix="kWh" 
                />
              </Col>
              <Col span={8}>
                <Statistic 
                  title="充电桩数量" 
                  value={selectedRegion.charge_count} 
                  suffix="个" 
                />
              </Col>
            </Row>
            
            <div style={{ marginTop: 24 }}>
              <p><strong>所属区域:</strong> {selectedRegion.district}</p>
              <p><strong>位置:</strong> ({selectedRegion.longitude.toFixed(4)}, {selectedRegion.latitude.toFixed(4)})</p>
              <p><strong>拥挤度:</strong> <span style={{
                color: getCongestionConfig(selectedRegion.current_occupancy).color,
                fontWeight: 'bold'
              }}>{getCongestionConfig(selectedRegion.current_occupancy).text}</span></p>
              <p><strong>区域面积:</strong> {(selectedRegion.area / 1000000).toFixed(2)} km²</p>
            </div>
            
            <div style={{ marginTop: 24 }}>
              {renderPredictionChart()}
            </div>
          </div>
        )}
      </Modal>
    </Card>
  );
};

export default RegionMap;