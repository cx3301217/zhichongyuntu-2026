// src/utils/config.js
export const CONFIG = {
  // 🎯 后端API地址
  // 开发环境: localhost:8000
  // 生产环境: 自动使用环境变量或相对路径（通过代理）
  API_BASE_URL: process.env.REACT_APP_API_BASE_URL || 'https://zhichongyuntu.zeabur.app/api',
  
  // 🗺️ 高德地图配置（使用您的Key）
  AMAP_KEY: '380c947d5057e79f18474eb97d757554',  // Web端Key
  AMAP_SECURITY_KEY: '97d9f5e33a7bcd5afbf0e6c462c00a4d',  // 安全密钥
  AMAP_WEB_SERVICE_KEY: '39ce9b8f4db87e11b5e7ae0561415d5b',  // Web服务Key
  
  // 🌍 地图中心（深圳）
  MAP_CENTER: {
    longitude: 114.0579,
    latitude: 22.5431
  },
  
  // 🔢 默认配置
  DEFAULT_ZOOM: 11,
  REGION_CIRCLE_RADIUS: 400,  // 区域圆圈半径（米）
  
  // 🎨 拥挤度颜色配置
  CONGESTION_COLORS: {
    low: {
      color: '#52c41a',
      fillColor: 'rgba(82, 196, 26, 0.3)',
      text: '空闲'
    },
    medium: {
      color: '#faad14',
      fillColor: 'rgba(250, 173, 20, 0.3)',
      text: '一般'
    },
    high: {
      color: '#ff7a45',
      fillColor: 'rgba(255, 122, 69, 0.3)',
      text: '繁忙'
    },
    'very-high': {
      color: '#f5222d',
      fillColor: 'rgba(245, 34, 45, 0.3)',
      text: '拥挤'
    },
    unknown: {
      color: '#999999',
      fillColor: 'rgba(153, 153, 153, 0.3)',
      text: '暂无数据'
    }
  }
};

// 设置高德地图安全密钥
if (typeof window !== 'undefined') {
  window._AMapSecurityConfig = {
    securityJsCode: CONFIG.AMAP_SECURITY_KEY
  };
}

export default CONFIG;