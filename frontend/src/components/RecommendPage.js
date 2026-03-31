// src/components/RecommendPage.js
import React, { useState, useEffect, useRef } from 'react';
import { Card, Button, Spin, message, Empty, Row, Col, Statistic, Tag, Alert, Space, Pagination } from 'antd';
import { EnvironmentOutlined, AimOutlined, ThunderboltOutlined, CarOutlined } from '@ant-design/icons';
import axios from 'axios';
import { CONFIG } from '../utils/config';
import { loadAmapScript, getCongestionConfig } from '../services/regionMapService';

const RecommendPage = () => {
  const [loading, setLoading] = useState(false);
  const [userLocation, setUserLocation] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [mapInstance, setMapInstance] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 2; // 每页显示2个区域
  const mapRef = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    initMap();
  }, []);

  useEffect(() => {
    if (mapInstance && recommendations.length > 0) {
      showRecommendationsOnMap();
    }
  }, [recommendations, mapInstance]);

  const initMap = async () => {
    try {
      console.log('🗺️ 开始初始化地图...');
      const AMap = await loadAmapScript();
      
      const map = new AMap.Map(mapRef.current, {
        zoom: 11,
        center: [114.0579, 22.5431], // 深圳中心
        viewMode: '3D',
        pitch: 0
      });
      
      setMapInstance(map);
      console.log('✅ 地图初始化成功');
    } catch (error) {
      console.error('❌ 地图初始化失败:', error);
      message.error('地图加载失败：' + error.message);
    }
  };

  const getUserLocation = () => {
    console.log('📍 开始获取用户位置...');
    setLoading(true);
    
    if (!navigator.geolocation) {
      message.error('您的浏览器不支持地理定位');
      setLoading(false);
      return;
    }

    // 智能定位策略：先快速定位，再尝试高精度
    let hasGotLocation = false;
    let loadingMsg = message.loading('正在快速定位...', 0);

    const handleLocationSuccess = async (position, isHighAccuracy = false) => {
      if (hasGotLocation && !isHighAccuracy) {
        return; // 如果已经获取过位置，且这次不是高精度，则忽略
      }
      
      loadingMsg();
      hasGotLocation = true;
      
      console.log(`✅ ${isHighAccuracy ? '高精度' : '快速'}定位成功:`, position.coords);
      
      const accuracy = position.coords.accuracy;
      const location = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude
      };
      
      setUserLocation(location);
      
      // 根据精度显示不同的消息
      if (accuracy < 100) {
        message.success(`✅ 位置获取成功！精度：${accuracy.toFixed(0)}米`, 3);
      } else if (accuracy < 1000) {
        message.success(`✅ 位置获取成功，精度：${accuracy.toFixed(0)}米`, 3);
      } else {
        message.success(`✅ 位置获取成功（精度：${(accuracy/1000).toFixed(1)}公里）`, 3);
      }
      
      console.log(`📍 定位精度: ${accuracy}米`);
      console.log(`📍 纬度: ${location.latitude}, 经度: ${location.longitude}`);
      
      // 地图移动到用户位置
      if (mapInstance) {
        console.log('🗺️ 移动地图到用户位置');
        mapInstance.setCenter([location.longitude, location.latitude]);
        mapInstance.setZoom(13);
        
        // 清除旧标记
        clearMarkers();
        
        // 添加用户位置标记
        const AMap = window.AMap;
        const userMarker = new AMap.Marker({
          position: [location.longitude, location.latitude],
          icon: new AMap.Icon({
            size: new AMap.Size(40, 40),
            image: '//a.amap.com/jsapi_demos/static/demo-center/icons/poi-marker-red.png',
            imageSize: new AMap.Size(40, 40)
          }),
          title: `您的位置（精度:±${accuracy.toFixed(0)}米）`,
          zIndex: 999
        });
        
        mapInstance.add(userMarker);
        markersRef.current.push(userMarker);
      }
      
      // 获取推荐
      await getRecommendations(location);
    };

    // 策略1：快速定位（低精度，使用WiFi/IP，5秒超时）
    console.log('🚀 尝试快速网络定位...');
    navigator.geolocation.getCurrentPosition(
      (position) => handleLocationSuccess(position, false),
      (error) => {
        console.log('⚠️ 快速定位失败，尝试高精度定位...', error.message);
      },
      {
        enableHighAccuracy: false,  // 不要求高精度，使用网络定位
        timeout: 5000,              // 5秒超时
        maximumAge: 60000           // 可使用1分钟内的缓存
      }
    );

    // 策略2：高精度定位（如果设备支持GPS，30秒后尝试）
    setTimeout(() => {
      if (!hasGotLocation) {
        loadingMsg();
        loadingMsg = message.loading('快速定位未成功，尝试高精度GPS定位（可能需要30秒）...', 0);
        console.log('🛰️ 尝试高精度GPS定位...');
      }
      
      navigator.geolocation.getCurrentPosition(
        (position) => handleLocationSuccess(position, true),
        (error) => {
          if (!hasGotLocation) {
            loadingMsg();
            console.error('❌ 所有定位方式都失败了:', error);
            
            let errorMessage = '无法获取您的位置';
            let helpInfo = '';
            
            switch(error.code) {
              case error.PERMISSION_DENIED:
                errorMessage = '❌ 位置权限被拒绝';
                helpInfo = '请点击地址栏左侧的锁图标，允许位置访问';
                break;
              case error.POSITION_UNAVAILABLE:
                errorMessage = '❌ 位置信息不可用';
                helpInfo = 'Windows：设置 → 隐私 → 位置 → 开启"位置服务"';
                break;
              case error.TIMEOUT:
                errorMessage = '⏱️ 定位超时';
                helpInfo = '建议：使用手机访问，或开启Windows位置服务';
                break;
              default:
                errorMessage = '❌ 定位失败';
                helpInfo = '建议使用手机打开本网站';
            }
            
            message.error({
              content: (
                <div>
                  <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{errorMessage}</div>
                  {helpInfo && <div style={{ fontSize: 12, color: '#888' }}>💡 {helpInfo}</div>}
                </div>
              ),
              duration: 10
            });
            setLoading(false);
          }
        },
        {
          enableHighAccuracy: true,   // 启用高精度GPS
          timeout: 30000,             // 30秒超时
          maximumAge: 0               // 不使用缓存
        }
      );
    }, 5000); // 5秒后如果快速定位还没成功，就尝试高精度
  };

  const getRecommendations = async (location) => {
    try {
      console.log('🔍 开始获取推荐，位置:', location);
      
      const response = await axios.post(
        `${CONFIG.API_BASE_URL}/api/recommend`,
        {
          latitude: location.latitude,
          longitude: location.longitude,
          top_k: 5
        }
      );
      
      console.log('📊 推荐响应:', response.data);
      
      if (response.data && response.data.success) {
        const recs = response.data.recommendations;
        console.log(`✅ 获取到 ${recs.length} 个推荐区域`);
        setRecommendations(recs);
        setCurrentPage(1); // 重置到第一页
        message.success(`已为您推荐 ${recs.length} 个最优区域`);
      } else {
        console.warn('⚠️ 推荐失败:', response.data);
        message.warning('推荐失败：' + (response.data.message || '未知错误'));
      }
    } catch (error) {
      console.error('❌ 推荐请求失败:', error);
      
      if (error.response) {
        console.error('服务器错误:', error.response.data);
        message.error(`推荐失败：${error.response.data.detail || error.response.statusText}`);
      } else if (error.request) {
        console.error('网络错误，无响应');
        message.error('网络错误：无法连接到服务器，请检查后端是否启动');
      } else {
        console.error('请求配置错误:', error.message);
        message.error('推荐失败：' + error.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const clearMarkers = () => {
    if (mapInstance && markersRef.current.length > 0) {
      console.log(`🧹 清除 ${markersRef.current.length} 个标记`);
      markersRef.current.forEach(marker => {
        mapInstance.remove(marker);
      });
      markersRef.current = [];
    }
  };

  const showRecommendationsOnMap = () => {
    if (!mapInstance) {
      console.warn('⚠️ 地图实例不存在，无法显示推荐');
      return;
    }
    
    console.log('🗺️ 在地图上显示推荐结果');
    clearMarkers();
    
    const AMap = window.AMap;
    
    // 重新添加用户位置标记
    if (userLocation) {
      const userMarker = new AMap.Marker({
        position: [userLocation.longitude, userLocation.latitude],
        icon: new AMap.Icon({
          size: new AMap.Size(40, 40),
          image: '//a.amap.com/jsapi_demos/static/demo-center/icons/poi-marker-red.png',
          imageSize: new AMap.Size(40, 40)
        }),
        title: '您的位置',
        zIndex: 999
      });
      
      mapInstance.add(userMarker);
      markersRef.current.push(userMarker);
    }
    
    // 添加推荐区域标记
    recommendations.forEach((rec, index) => {
      const congestionInfo = getCongestionConfig(rec.current_occupancy);
      
      const marker = new AMap.Marker({
        position: [rec.longitude, rec.latitude],
        icon: new AMap.Icon({
          size: new AMap.Size(32, 32),
          image: `//webapi.amap.com/theme/v1.3/markers/n/mark_b${index + 1}.png`,
          imageSize: new AMap.Size(32, 32)
        }),
        title: rec.name,
        extData: rec
      });
      
      const infoWindow = new AMap.InfoWindow({
        content: `
          <div style="padding: 12px; min-width: 200px;">
            <h4 style="margin: 0 0 8px 0; color: #1890ff;">
              🏆 推荐${index + 1}: ${rec.name}
            </h4>
            <p style="margin: 4px 0; color: #666;">
              📍 ${rec.district}
            </p>
            <p style="margin: 4px 0;">
              🚗 距离: <strong style="color: #1890ff;">${rec.distance.toFixed(2)} km</strong>
            </p>
            <p style="margin: 4px 0;">
              ⚡ 占用率: <strong style="color: ${congestionInfo.color};">${rec.current_occupancy}%</strong>
            </p>
            <p style="margin: 4px 0;">
              🔌 充电桩: <strong>${rec.charge_count}个</strong>
            </p>
            <p style="margin: 4px 0;">
              ⭐ 推荐分数: <strong style="color: #52c41a;">${(rec.score * 100).toFixed(1)}</strong>
            </p>
          </div>
        `,
        offset: new AMap.Pixel(0, -30)
      });
      
      marker.on('click', () => {
        infoWindow.open(mapInstance, marker.getPosition());
        setSelectedRegion(rec);
      });
      
      mapInstance.add(marker);
      markersRef.current.push(marker);
    });
    
    // 自动缩放到包含所有标记
    const points = recommendations.map(rec => [rec.longitude, rec.latitude]);
    if (userLocation) {
      points.push([userLocation.longitude, userLocation.latitude]);
    }
    
    if (points.length > 0) {
      mapInstance.setFitView();
    }
    
    console.log('✅ 推荐标记已显示在地图上');
  };

  const navigateToRegion = (region) => {
    if (!region) return;
    
    const url = `https://uri.amap.com/marker?position=${region.longitude},${region.latitude}&name=${encodeURIComponent(region.name)}&coordinate=gaode`;
    window.open(url, '_blank');
  };

  const getRankIcon = (index) => {
    const icons = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'];
    return icons[index] || '⭐';
  };

  const pageWrapperStyle = {
    backgroundImage: `url(${process.env.PUBLIC_URL}/bg/recommend-bg.jpg)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    backgroundAttachment: 'fixed',
    padding: '24px',
    minHeight: 'calc(100vh - 64px)'
  };

  return (
    <div style={pageWrapperStyle}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Card 
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <AimOutlined style={{ fontSize: 24, color: '#52c41a' }} />
            <span>智能推荐 - 为您找到最优充电区域</span>
          </div>
        }
        extra={
          <Button
            type="primary"
            size="large"
            icon={<EnvironmentOutlined />}
            onClick={getUserLocation}
            loading={loading}
          >
            获取我的位置
          </Button>
        }
      >
        <Row gutter={24}>
          <Col xs={24} lg={14}>
            <Card 
              title="📍 地图视图"
              bordered={false}
              style={{ marginBottom: 24 }}
            >
              <div
                ref={mapRef}
                style={{
                  width: '100%',
                  height: 600,
                  borderRadius: 8,
                  overflow: 'hidden'
                }}
              />
            </Card>
          </Col>

          <Col xs={24} lg={10}>
            <Card 
              title={
                <Space>
                  <ThunderboltOutlined style={{ color: '#52c41a' }} />
                  <span>推荐结果</span>
                  {recommendations.length > 0 && (
                    <Tag color="success">{recommendations.length} 个区域</Tag>
                  )}
                </Space>
              }
              bordered={false}
            >
              {loading ? (
                <div style={{ textAlign: 'center', padding: '60px 0' }}>
                  <Spin size="large" tip="正在智能推荐..." />
                </div>
              ) : recommendations.length === 0 ? (
                <Empty
                  description={
                    <Space direction="vertical" size="large">
                      <div style={{ fontSize: 16 }}>
                        点击"获取我的位置"开始智能推荐
                      </div>
                      <div style={{ color: '#666', fontSize: 14 }}>
                        系统将根据您的位置和实时占用率<br/>
                        为您推荐最优的充电区域
                      </div>
                    </Space>
                  }
                  style={{ padding: '60px 0' }}
                />
              ) : (
                <>
                  <Space direction="vertical" size="large" style={{ width: '100%' }}>
                    {recommendations
                      .slice((currentPage - 1) * pageSize, currentPage * pageSize)
                      .map((rec, idx) => {
                        const index = (currentPage - 1) * pageSize + idx; // 全局索引
                        const congestionInfo = getCongestionConfig(rec.current_occupancy);
                        
                        return (
                          <Card
                            key={rec.region_id}
                            type="inner"
                            style={{
                              border: selectedRegion?.region_id === rec.region_id 
                                ? '2px solid #52c41a' 
                                : '1px solid #f0f0f0'
                            }}
                          >
                            <div style={{ marginBottom: 12 }}>
                              <h3 style={{ margin: 0, fontSize: 16 }}>
                                {getRankIcon(index)} {rec.name}
                              </h3>
                              <p style={{ margin: '4px 0 0 0', color: '#666', fontSize: 12 }}>
                                {rec.district}
                              </p>
                            </div>

                            <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
                              <Col span={12}>
                                <Statistic
                                  title="距离"
                                  value={rec.distance}
                                  precision={2}
                                  suffix="km"
                                  valueStyle={{ fontSize: 18, color: '#1890ff' }}
                                />
                              </Col>
                              <Col span={12}>
                                <Statistic
                                  title="推荐分数"
                                  value={rec.score * 100}
                                  precision={1}
                                  valueStyle={{ fontSize: 18, color: '#52c41a' }}
                                />
                              </Col>
                            </Row>

                            <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
                              <Col span={12}>
                                <div style={{ fontSize: 12, color: '#666' }}>占用率</div>
                                <div style={{ fontSize: 16, fontWeight: 'bold', color: congestionInfo.color }}>
                                  {rec.current_occupancy}%
                                </div>
                              </Col>
                              <Col span={12}>
                                <div style={{ fontSize: 12, color: '#666' }}>充电桩数量</div>
                                <div style={{ fontSize: 16, fontWeight: 'bold' }}>
                                  {rec.charge_count} 个
                                </div>
                              </Col>
                            </Row>

                            <div style={{ marginBottom: 12 }}>
                              <Tag color={congestionInfo.color}>
                                {congestionInfo.text}
                              </Tag>
                            </div>

                            <Button
                              type="primary"
                              icon={<CarOutlined />}
                              onClick={() => navigateToRegion(rec)}
                              block
                            >
                              导航到此区域
                            </Button>
                          </Card>
                        );
                      })}
                  </Space>
                  
                  {/* 分页组件 */}
                  {recommendations.length > pageSize && (
                    <div style={{ textAlign: 'center', marginTop: 24 }}>
                      <Pagination
                        current={currentPage}
                        pageSize={pageSize}
                        total={recommendations.length}
                        onChange={(page) => setCurrentPage(page)}
                        showSizeChanger={false}
                        showTotal={(total) => `共 ${total} 个推荐区域`}
                      />
                    </div>
                  )}
                </>
              )}
            </Card>
          </Col>
        </Row>

        {userLocation && (
          <Alert
            message="您的位置"
            description={`纬度: ${userLocation.latitude.toFixed(6)}, 经度: ${userLocation.longitude.toFixed(6)}`}
            type="success"
            showIcon
            style={{ marginTop: 24 }}
          />
        )}
      </Card>
      </div>
    </div>
  );
};

export default RecommendPage;