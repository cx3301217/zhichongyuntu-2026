// src/services/api.js

import axios from 'axios';
import { CONFIG } from '../utils/config';

// 创建axios实例
const apiClient = axios.create({
  baseURL: CONFIG.API_BASE_URL,
  timeout: 120000,  // 120秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.url);
    return config;
  },
  (error) => {
    console.error('请求拦截器错误:', error);
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log('响应成功:', response.config.url);
    return response.data;
  },
  (error) => {
    console.error('API错误:', error);
    
    // 详细的错误日志
    if (error.response) {
      console.error('错误响应数据:', error.response.data);
      console.error('错误状态码:', error.response.status);
      console.error('错误响应头:', error.response.headers);
    } else if (error.request) {
      console.error('请求已发送但没有收到响应:', error.request);
    } else {
      console.error('请求配置错误:', error.message);
    }
    
    return Promise.reject(error);
  }
);

// API方法
export const API = {
  // 获取所有充电站的预测数据
  getStationPredictions: async () => {
    try {
      const response = await apiClient.get('/api/predictions');
      return response;
    } catch (error) {
      console.error('获取预测数据失败:', error);
      throw error;
    }
  },

  // 获取单个充电站的预测数据
  getStationPrediction: async (stationId) => {
    try {
      const response = await apiClient.get(`/api/predict/${stationId}`);
      return response;
    } catch (error) {
      console.error('获取充电站预测失败:', error);
      throw error;
    }
  },

  // 商家上传数据（单个）
  uploadStationData: async (formData) => {
    try {
      const response = await apiClient.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response;
    } catch (error) {
      console.error('上传数据失败:', error);
      throw error;
    }
  },

  // 获取充电站24小时预测
  get24HourPrediction: async (stationId) => {
    try {
      const response = await apiClient.get(`/api/predict/24hours/${stationId}`);
      return response;
    } catch (error) {
      console.error('获取24小时预测失败:', error);
      throw error;
    }
  },

  // 上传CSV文件（关键接口）
  uploadCSV: async (formData) => {
    try {
      console.log('开始上传CSV文件...');
      
      const response = await apiClient.post('/api/upload-csv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000,  // 单独设置120秒超时
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          console.log(`上传进度: ${percentCompleted}%`);
        },
      });
      
      console.log('CSV上传成功，服务器响应:', response);
      return response;
    } catch (error) {
      console.error('上传CSV失败，详细错误:', error);
      
      // 提供更详细的错误信息
      if (error.code === 'ECONNABORTED') {
        console.error('请求超时，可能是文件太大或网络问题');
      }
      
      throw error;
    }
  },

  // 批量上传充电站数据
  batchUploadStationData: async (stations) => {
    try {
      const response = await apiClient.post('/api/batch-upload', {
        stations: stations
      });
      return response;
    } catch (error) {
      console.error('批量上传数据失败:', error);
      throw error;
    }
  },

  // 获取所有充电站POI信息
  getAllStationsPOI: async () => {
    try {
      const response = await apiClient.get('/api/stations/poi');
      return response;
    } catch (error) {
      console.error('获取POI数据失败:', error);
      throw error;
    }
  },

  // 获取所有充电站及其预测数据
  getStationsWithPredictions: async () => {
    try {
      const response = await apiClient.get('/api/stations/with-predictions');
      return response;
    } catch (error) {
      console.error('获取充电站预测数据失败:', error);
      throw error;
    }
  },

  // 健康检查
  healthCheck: async () => {
    try {
      const response = await apiClient.get('/api/health');
      return response;
    } catch (error) {
      console.error('健康检查失败:', error);
      throw error;
    }
  },
};

export default apiClient;