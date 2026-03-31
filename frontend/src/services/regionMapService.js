// src/services/regionMapService.js
import { CONFIG } from '../utils/config';
import axios from 'axios';

// 简易前端缓存，避免跨页重复请求/预测
let _allRegionsCache = null; // Array
const _region24hCache = {};  // { [regionId]: prediction }

export const clearPredictionCaches = () => {
  _allRegionsCache = null;
  Object.keys(_region24hCache).forEach(k => delete _region24hCache[k]);
};

/**
 * 获取所有275个区域数据
 */
export const getAllRegions = async (refresh = false) => {
  try {
    console.log('🌍 获取区域数据...');
    if (!refresh && Array.isArray(_allRegionsCache) && _allRegionsCache.length > 0) {
      return _allRegionsCache;
    }
    
    const response = await axios.get(`${CONFIG.API_BASE_URL}/api/regions/all`, {
      params: { refresh }
    });
    
    if (response.data && response.data.success && response.data.regions) {
      const regions = response.data.regions;
      console.log(`✅ 成功获取 ${regions.length} 个区域`);
      console.log('前3个区域示例:', regions.slice(0, 3));
      _allRegionsCache = regions;
      if (refresh) {
        Object.keys(_region24hCache).forEach(k => delete _region24hCache[k]);
      }
      return regions;
    }
    
    console.warn('⚠️ 返回数据格式不正确');
    return [];
  } catch (error) {
    console.error('❌ 获取区域数据失败:', error);
    return [];
  }
};

/**
 * 获取单个区域24小时预测
 */
export const getRegion24hPrediction = async (regionId, refresh = false) => {
  try {
    if (!refresh && _region24hCache[regionId]) {
      return _region24hCache[regionId];
    }
    const response = await axios.get(
      `${CONFIG.API_BASE_URL}/api/regions/${regionId}/predict`, { params: { refresh } }
    );
    
    if (response.data && response.data.success) {
      _region24hCache[regionId] = response.data.predictions;
      return _region24hCache[regionId];
    }
    
    return null;
  } catch (error) {
    console.error(`❌ 获取区域${regionId}预测失败:`, error);
    return null;
  }
};

/**
 * 根据用户位置推荐区域
 */
export const recommendRegions = async (latitude, longitude, topK = 5) => {
  try {
    const response = await axios.post(
      `${CONFIG.API_BASE_URL}/api/recommend`,
      { latitude, longitude, top_k: topK }
    );
    
    if (response.data && response.data.success) {
      return response.data.recommendations;
    }
    
    return [];
  } catch (error) {
    console.error('❌ 推荐失败:', error);
    return [];
  }
};

/**
 * 获取拥挤度配置
 */
export const getCongestionConfig = (occupancyPercent) => {
  if (occupancyPercent === null || occupancyPercent === undefined) {
    return CONFIG.CONGESTION_COLORS.unknown;
  }
  
  if (occupancyPercent < 30) {
    return CONFIG.CONGESTION_COLORS.low;
  } else if (occupancyPercent < 60) {
    return CONFIG.CONGESTION_COLORS.medium;
  } else if (occupancyPercent < 85) {
    return CONFIG.CONGESTION_COLORS.high;
  } else {
    return CONFIG.CONGESTION_COLORS['very-high'];
  }
};

/**
 * 加载高德地图脚本
 */
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