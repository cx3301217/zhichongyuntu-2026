import { CONFIG } from '../utils/config';
import axios from 'axios';

// 从后端API获取充电站数据
export const getChargingStations = async () => {
  try {
    console.log('正在从后端获取充电站数据...');
    
    const response = await axios.get(`${CONFIG.API_BASE_URL}/api/stations/with-predictions`);
    
    console.log('后端返回数据:', response.data);
    
    if (response.data && response.data.stations && Array.isArray(response.data.stations)) {
      const stations = response.data.stations
        .filter(station => station.has_data)  // 只显示有数据的站点
        .map(station => ({
          id: station.poi_id,
          name: station.name,
          address: station.address,
          location: [station.longitude, station.latitude],
          type: station.type || '',
          tel: station.tel || '暂无电话',
          distance: 0,
          businessArea: station.district || '',
          congestion: station.congestion_level,
          congestionLevel: station.congestion_level,
          // 关键：occupancy_rate 已经是百分比（0-100）
          predictedLoad: station.occupancy_rate,  // 使用 occupancy_rate 而非 predicted_load
          capacity: station.capacity,
          currentLoad: station.current_load
        }));
      
      console.log(`成功获取 ${stations.length} 个充电站`);
      console.log('前3个站点预览:', stations.slice(0, 3));
      return stations;
    }
    
    console.warn('返回数据格式不正确');
    return [];
  } catch (error) {
    console.error('从后端获取数据失败:', error.message);
    if (error.response) {
      console.error('错误响应:', error.response.data);
      console.error('状态码:', error.response.status);
    }
    return [];
  }
};

// 计算拥挤度等级（输入是百分比0-100）
export const getCongestionLevel = (occupancyPercent) => {
  if (occupancyPercent === null || occupancyPercent === undefined) {
    return { level: 'unknown', color: '#999', text: '暂无数据' };
  }
  
  // occupancyPercent 已经是百分比（0-100）
  if (occupancyPercent < 30) {
    return { level: 'low', color: '#52c41a', text: '空闲' };
  } else if (occupancyPercent < 60) {
    return { level: 'medium', color: '#faad14', text: '一般' };
  } else if (occupancyPercent < 85) {
    return { level: 'high', color: '#ff7a45', text: '繁忙' };
  } else {
    return { level: 'very-high', color: '#f5222d', text: '拥挤' };
  }
};

// 加载高德地图脚本
export const loadAmapScript = () => {
  return new Promise((resolve, reject) => {
    if (window.AMap) {
      resolve(window.AMap);
      return;
    }

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${CONFIG.AMAP_KEY}`;
    script.onerror = reject;
    script.onload = () => {
      resolve(window.AMap);
    };
    document.head.appendChild(script);
  });
};