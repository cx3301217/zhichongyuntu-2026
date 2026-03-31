# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="智充云图",
    description="基于TFT的城市级新能源汽车充电桩网络服务拥挤度可视化信息系统",
    version="1.0.0"
)

# ⭐⭐⭐ 配置CORS - 非常重要！
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# ⭐⭐⭐ 注册路由
try:
    from app.api import region_routes, upload_routes
    
    # 注册区域路由
    app.include_router(
        region_routes.router,
        prefix="/api",
        tags=["regions"]
    )
    
    # 注册上传路由
    app.include_router(
        upload_routes.router,
        prefix="/api",
        tags=["upload"]
    )
    
    logger.info("✅ 路由注册成功")
    
except Exception as e:
    logger.error(f"❌ 路由注册失败: {e}")
    import traceback
    traceback.print_exc()


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "充电桩预测系统API",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs",
        "api_base": "/api",
        "endpoints": {
            "health": "/api/health",
            "all_regions": "/api/regions/all",
            "region_detail": "/api/regions/{region_id}",
            "region_predict": "/api/regions/{region_id}/predict",
            "recommend": "/api/recommend",
            "upload_data": "/api/upload-training-data",
            "data_status": "/api/data-status",
            "reset_status": "/api/reset-data-status"
        }
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "message": "服务运行正常"
    }


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    logger.info("="*60)
    logger.info("🚀 充电桩预测系统启动中...")
    logger.info("="*60)
    logger.info("📍 API文档: http://localhost:8000/docs")
    logger.info("📍 API地址: http://localhost:8000/api")
    logger.info("📍 健康检查: http://localhost:8000/api/health")
    logger.info("📍 数据上传: http://localhost:8000/api/upload-training-data")
    logger.info("📍 数据状态: http://localhost:8000/api/data-status")
    logger.info("="*60)


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理"""
    logger.info("👋 充电桩预测系统关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )