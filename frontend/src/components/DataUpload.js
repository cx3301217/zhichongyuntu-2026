// src/components/DataUpload.js
import React, { useState } from 'react';
import { Upload, Button, Card, message, Alert, Steps, Divider, Space, Progress, List } from 'antd';
import { UploadOutlined, FileTextOutlined, CheckCircleOutlined, CloseOutlined } from '@ant-design/icons';
import axios from 'axios';
import { CONFIG } from '../utils/config';

const { Step } = Steps;

const DataUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [fileList, setFileList] = useState({
    occupancy: null,
    volume: null,
    weather: null,
    price: null
  });

  const requiredFiles = [
    { 
      key: 'occupancy', 
      label: '占用率数据', 
      description: '区域占用率历史数据',
      paramName: 'occupancy'
    },
    { 
      key: 'volume', 
      label: '电量负荷数据', 
      description: '充电负荷历史数据',
      paramName: 'volume'
    },
    { 
      key: 'weather', 
      label: '天气数据', 
      description: '天气数据（温度、湿度、降雨）',
      paramName: 'weather'
    },
    { 
      key: 'price', 
      label: '电价数据', 
      description: '电价数据',
      paramName: 'price'
    }
  ];

  // ⭐⭐⭐ 修复：正确的文件选择处理函数
  const handleFileSelect = (fileKey) => (file) => {
    console.log(`📁 选择文件 [${fileKey}]:`, file.name);
    
    if (!file.name.endsWith('.csv')) {
      message.error(`${file.name} 不是CSV文件，请选择CSV文件！`);
      return false;
    }

    // 更新文件列表
    setFileList(prev => {
      const newList = {
        ...prev,
        [fileKey]: file
      };
      console.log('📋 当前文件列表:', newList);
      return newList;
    });
    
    message.success(`✅ ${file.name} 已选择`);
    return false; // 阻止自动上传
  };

  const handleUpload = async () => {
    console.log('🚀 开始上传流程...');
    console.log('📋 当前文件列表:', fileList);

    // 检查是否所有文件都已选择
    const missingFiles = requiredFiles.filter(file => !fileList[file.key]);
    
    if (missingFiles.length > 0) {
      const missingNames = missingFiles.map(f => f.label).join(', ');
      message.error(`请选择所有文件！缺少: ${missingNames}`);
      console.log('❌ 缺少文件:', missingNames);
      return;
    }

    // 创建FormData
    const formData = new FormData();
    
    // ⭐⭐⭐ 关键：使用正确的参数名添加文件
    formData.append('occupancy', fileList.occupancy);
    formData.append('volume', fileList.volume);
    formData.append('weather', fileList.weather);
    formData.append('price', fileList.price);

    console.log('📦 FormData已创建');
    console.log('📁 文件详情:', {
      occupancy: fileList.occupancy.name,
      volume: fileList.volume.name,
      weather: fileList.weather.name,
      price: fileList.price.name
    });

    setUploading(true);
    setUploadResult(null);

    try {
      console.log('🌐 发送上传请求...');
      
      const response = await axios.post(
        `${CONFIG.API_BASE_URL}/api/upload-training-data`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 60000,
        }
      );

      console.log('✅ 上传响应:', response.data);

      if (response.data.success) {
        message.success('数据上传成功！模型已准备就绪', 2);
        setUploadResult(response.data);
        
        // 3秒后自动刷新
        message.info('页面将在3秒后自动刷新...', 2);
        setTimeout(() => {
          console.log('🔄 刷新页面...');
          window.location.reload();
        }, 3000);
        
      } else {
        message.error('上传失败：' + (response.data.message || '未知错误'));
      }
    } catch (error) {
      console.error('❌ 上传错误:', error);
      
      if (error.response) {
        console.error('服务器错误:', error.response.data);
        message.error(`上传失败：${error.response.data.detail || error.response.statusText}`);
      } else if (error.request) {
        console.error('网络错误:', error.request);
        message.error('网络错误：无法连接到服务器，请检查后端是否启动');
      } else {
        console.error('错误:', error.message);
        message.error('上传失败：' + error.message);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleReset = async () => {
    try {
      await axios.post(`${CONFIG.API_BASE_URL}/api/reset-data-status`);
      message.success('数据状态已重置');
      
      setFileList({
        occupancy: null,
        volume: null,
        weather: null,
        price: null
      });
      setUploadResult(null);
      
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (error) {
      console.error('重置失败:', error);
      message.error('重置失败');
    }
  };

  const handleRemoveFile = (fileKey) => {
    setFileList(prev => ({
      ...prev,
      [fileKey]: null
    }));
    message.info('文件已移除');
  };

  const allFilesSelected = Object.values(fileList).every(file => file !== null);
  const currentStep = uploadResult ? 2 : (allFilesSelected ? 1 : 0);

  const pageWrapperStyle = {
    backgroundImage: `url(${process.env.PUBLIC_URL}/bg/upload-bg.jpg)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    backgroundAttachment: 'fixed',
    padding: '24px',
    minHeight: 'calc(100vh - 64px)'
  };

  return (
    <div style={pageWrapperStyle}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Card title="📤 预测数据上传" bordered={false}>

        <Steps current={currentStep} style={{ marginBottom: 32 }}>
          <Step 
            title="选择文件" 
            description={`已选择 ${Object.values(fileList).filter(f => f).length}/4 个文件`}
            icon={<FileTextOutlined />} 
          />
          <Step title="上传数据" description="上传到服务器" icon={<UploadOutlined />} />
          <Step title="完成" description="预测模型已就绪" icon={<CheckCircleOutlined />} />
        </Steps>

        <Card 
          title="📁 选择训练数据文件"
          style={{ marginBottom: 24 }}
          type="inner"
        >
          <List
            dataSource={requiredFiles}
            renderItem={(file) => {
              const isSelected = fileList[file.key] !== null;
              
              return (
                <List.Item
                  style={{
                    padding: '16px',
                    background: isSelected ? '#f6ffed' : '#fff',
                    border: isSelected ? '1px solid #b7eb8f' : '1px solid #f0f0f0',
                    borderRadius: 8,
                    marginBottom: 12
                  }}
                  actions={[
                    <Upload
                      key="upload"
                      accept=".csv"
                      beforeUpload={handleFileSelect(file.key)}
                      showUploadList={false}
                      disabled={uploading}
                    >
                      <Button 
                        icon={<UploadOutlined />}
                        type={isSelected ? "default" : "primary"}
                        disabled={uploading}
                      >
                        {isSelected ? '重新选择' : '选择文件'}
                      </Button>
                    </Upload>,
                    isSelected && (
                      <Button
                        key="remove"
                        danger
                        icon={<CloseOutlined />}
                        onClick={() => handleRemoveFile(file.key)}
                        disabled={uploading}
                      >
                        移除
                      </Button>
                    )
                  ].filter(Boolean)}
                >
                  <List.Item.Meta
                    avatar={
                      <div style={{ 
                        fontSize: 24, 
                        color: isSelected ? '#52c41a' : '#d9d9d9' 
                      }}>
                        {isSelected ? <CheckCircleOutlined /> : <FileTextOutlined />}
                      </div>
                    }
                    title={
                      <div>
                        <strong style={{ fontSize: 16 }}>{file.label}</strong>
                        {isSelected && (
                          <span style={{ 
                            marginLeft: 12, 
                            color: '#52c41a', 
                            fontSize: 14 
                          }}>
                            ✓ 已选择
                          </span>
                        )}
                      </div>
                    }
                    description={
                      <div>
                        <div style={{ color: '#666', marginBottom: 4 }}>
                          {file.description}
                        </div>
                        {isSelected && fileList[file.key] && (
                          <div style={{ color: '#1890ff', fontSize: 12 }}>
                            文件名: {fileList[file.key].name} ({(fileList[file.key].size / 1024).toFixed(2)} KB)
                          </div>
                        )}
                      </div>
                    }
                  />
                </List.Item>
              );
            }}
          />

          <Divider />

          <div style={{ textAlign: 'center' }}>
            <Space size="large">
              <Button
                type="primary"
                size="large"
                icon={<UploadOutlined />}
                onClick={handleUpload}
                loading={uploading}
                disabled={!allFilesSelected || uploading}
                style={{ minWidth: 200 }}
              >
                {uploading ? '上传中...' : `开始上传 (${Object.values(fileList).filter(f => f).length}/4)`}
              </Button>
              {uploadResult && (
                <Button
                  danger
                  size="large"
                  onClick={handleReset}
                  disabled={uploading}
                >
                  重置状态（重新演示）
                </Button>
              )}
            </Space>
          </div>
        </Card>

        {uploading && (
          <Card style={{ marginTop: 24 }} type="inner">
            <Progress percent={100} status="active" />
            <p style={{ textAlign: 'center', marginTop: 16, color: '#1890ff' }}>
              正在上传数据到服务器，请稍候...
            </p>
          </Card>
        )}

        {uploadResult && (
          <Card 
            style={{ marginTop: 24 }}
            type="inner"
          >
            <Alert
              message="✅ 数据上传成功！"
              description={
                <div>
                  <p><strong>上传时间：</strong>{new Date(uploadResult.upload_time).toLocaleString('zh-CN')}</p>
                  <p><strong>文件数量：</strong>{uploadResult.total_files} 个</p>
                  <Divider />
                  <p><strong>已上传的文件：</strong></p>
                  <ul>
                    {uploadResult.uploaded_files?.map((file, index) => (
                      <li key={index}>
                        ✓ {file.filename} - {file.size}
                        {file.original_filename && ` (原文件: ${file.original_filename})`}
                      </li>
                    ))}
                  </ul>
                  <Divider />
                  <p style={{ color: '#52c41a', fontWeight: 'bold', fontSize: 16 }}>
                    🎉 预测模型已启用！页面即将自动刷新...
                  </p>
                </div>
              }
              type="success"
              showIcon
            />
          </Card>
        )}
      </Card>
      </div>
    </div>
  );
};

export default DataUpload;