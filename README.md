# 智充云图 - 充电桩预测系统

基于TFT模型的城市级新能源汽车充电桩网络服务拥挤度可视化信息系统

## 📁 项目结构

```
智充云图/
├── backend/                    # 后端代码（FastAPI + PyTorch）
│   ├── app/                   # FastAPI应用
│   │   ├── api/              # API路由
│   │   │   ├── region_routes.py    # 区域预测路由
│   │   │   └── upload_routes.py    # 数据上传路由
│   │   ├── main.py           # FastAPI主程序
│   │   ├── models.py         # 数据模型
│   │   ├── region_predictor.py     # 预测器
│   │   └── data_status.py    # 数据状态管理
│   ├── data/                 # 数据文件
│   │   ├── occupancy.csv     # 占用率数据
│   │   ├── volume.csv        # 电量负荷数据
│   │   ├── weather_central.csv    # 天气数据
│   │   └── e_price.csv       # 电价数据
│   ├── models/               # 训练好的模型
│   │   ├── best_model.pth
│   │   └── dual_tft_model_complete_cpu.pkl
│   ├── prepare_region_data.py      # 数据准备脚本
│   ├── train_tft_model_optimized.py # 模型训练脚本
│   ├── requirements.txt      # Python依赖
│   └── shenzhen_regions_275.json   # 深圳275个区域数据
│
├── frontend/                  # 前端代码（React）
│   ├── public/               # 静态资源
│   ├── src/                  # 源代码
│   │   ├── components/       # React组件
│   │   ├── services/         # API服务
│   │   └── utils/           # 工具函数
│   ├── package.json          # NPM依赖
│   └── README.md
│
└── README.md                 # 本文件
```

## 🚀 快速开始

### 1. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 启动后端服务（在backend目录内）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端API地址：`http://localhost:8000`  
API文档：`http://localhost:8000/docs`

### 2. 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm start
```

前端地址：`http://localhost:3000`

## 📊 功能特点

### 用户端
- 🗺️ **实时地图监控**：查看深圳市275个区域的充电桩占用率
- 📈 **24小时预测**：点击区域查看未来24小时占用率和电量负荷趋势
- 🎯 **智能推荐**：根据当前位置推荐最优充电区域
- 📊 **数据可视化**：ECharts图表展示预测数据

### 管理端
- 📤 **数据上传**：支持CSV批量上传训练数据
- 📊 **数据状态管理**：查看数据上传状态
- 🎛️ **系统监控**：实时监控系统运行状态

## 🔧 技术栈

### 后端
- **Python 3.8+**
- **FastAPI**：高性能Web框架
- **PyTorch**：深度学习框架
- **TFT模型**：时间融合Transformer（Temporal Fusion Transformer）

### 前端
- **React 18**
- **高德地图API**：地图展示
- **ECharts**：数据可视化
- **Ant Design**：UI组件库

## 📝 API文档

启动后端后，访问 `http://localhost:8000/docs` 查看完整的API文档

主要接口：
- `GET /api/regions/all` - 获取所有区域及预测
- `GET /api/regions/{region_id}` - 获取单个区域信息
- `GET /api/regions/{region_id}/predict` - 预测区域未来24小时
- `POST /api/recommend` - 获取推荐区域
- `POST /api/upload-training-data` - 上传训练数据

## 🎓 模型说明

### TFT模型参数
- **输入窗口**：168小时（7天）
- **预测窗口**：24小时
- **模型结构**：
  - 隐藏层维度：256
  - 注意力头数：8
  - Transformer层数：4
  - Dropout：0.15

### 训练特点
- 双目标预测：同时预测占用率和电量负荷
- 采用Huber Loss，对异常值更鲁棒
- 学习率自适应调整（ReduceLROnPlateau）
- 早停机制防止过拟合

## 📋 待办事项

- [ ] 添加用户认证系统
- [ ] 支持更多城市
- [ ] 优化模型预测精度
- [ ] 添加历史数据回溯功能
- [ ] 移动端适配

## 📄 许可证

MIT License

## 👥 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题，请提交Issue或联系开发团队。

