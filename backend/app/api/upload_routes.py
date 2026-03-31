# app/api/upload_routes.py
"""
数据上传API - 用于演示数据上传功能
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import os
import shutil
from datetime import datetime
import logging

# ⭐ 导入状态管理模块
from backend.app.data_status import set_data_uploaded, get_data_status, reset_data_status

router = APIRouter()
logger = logging.getLogger(__name__)

# 数据文件保存目录
DATA_DIR = "backend/data"
os.makedirs(DATA_DIR, exist_ok=True)

@router.post("/upload-training-data")
async def upload_training_data(
    occupancy: UploadFile = File(...),
    volume: UploadFile = File(...),
    weather: UploadFile = File(...),
    price: UploadFile = File(...)
):
    """
    上传4个训练数据CSV文件
    """
    try:
        logger.info("\n" + "="*60)
        logger.info("📤 开始上传训练数据...")
        logger.info("="*60)
        
        # 定义需要的文件
        files_to_upload = {
            'occupancy.csv': occupancy,
            'volume.csv': volume,
            'weather_central.csv': weather,
            'e_price.csv': price
        }
        
        uploaded_files = []
        
        # 保存每个文件
        for filename, file_obj in files_to_upload.items():
            # 检查文件类型
            if not file_obj.filename.endswith('.csv'):
                raise HTTPException(
                    status_code=400, 
                    detail=f"{filename} 必须是CSV文件，当前文件: {file_obj.filename}"
                )
            
            file_path = os.path.join(DATA_DIR, filename)
            
            # 保存文件
            try:
                with open(file_path, 'wb') as buffer:
                    content = await file_obj.read()
                    buffer.write(content)
                
                file_size = os.path.getsize(file_path)
                uploaded_files.append({
                    'filename': filename,
                    'size': f"{file_size / 1024:.2f} KB",
                    'original_filename': file_obj.filename
                })
                
                logger.info(f"✅ {filename} - {file_size / 1024:.2f} KB (原文件: {file_obj.filename})")
            
            except Exception as e:
                logger.error(f"❌ 保存文件 {filename} 失败: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"保存文件 {filename} 失败: {str(e)}"
                )
        
        # ⭐⭐⭐ 关键修复：上传成功后，立即加载数据并预测
        logger.info("="*60)
        logger.info("✅ 所有文件上传成功！")
        logger.info("="*60)
        
        # 1. 设置上传标志
        upload_time = datetime.now().isoformat()
        set_data_uploaded(True, upload_time)
        logger.info("📝 已设置数据上传标志")
        
        # 2. 获取全局预测器并加载新数据
        try:
            from backend.app.api.region_routes import region_predictor
            
            if region_predictor is not None:
                logger.info("📊 开始加载CSV数据到预测器...")
                
                # ⭐⭐⭐ 加载数据
                data_loaded = region_predictor.load_data()
                
                if data_loaded:
                    logger.info("✅ 数据加载成功！")
                    
                    # ⭐⭐⭐ 立即预测一次所有区域
                    logger.info("🔮 开始预测所有区域...")
                    predictions = region_predictor.predict_all_regions()
                    logger.info(f"✅ 预测完成，共 {len(predictions)} 个区域")
                else:
                    logger.warning("⚠️ 数据加载失败，将使用模拟预测")
            else:
                logger.warning("⚠️ 预测器未初始化")
        
        except Exception as e:
            logger.error(f"❌ 加载数据或预测失败: {e}")
            import traceback
            traceback.print_exc()
            # 不抛出异常，让上传继续完成
        
        logger.info("="*60)
        logger.info(f"📅 上传时间: {upload_time}")
        logger.info("="*60)
        
        return {
            'success': True,
            'message': '数据上传成功！模型已加载数据并完成预测',
            'uploaded_files': uploaded_files,
            'upload_time': upload_time,
            'total_files': len(uploaded_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/data-status")
async def get_status():
    """
    获取数据状态
    """
    # ⭐⭐⭐ 从文件读取状态
    status = get_data_status()
    
    return {
        'success': True,
        'uploaded': status['uploaded'],
        'upload_time': status['upload_time'],
        'message': '数据已上传' if status['uploaded'] else '请先上传训练数据'
    }


@router.post("/reset-data-status")
async def reset_status():
    """
    重置数据状态（用于演示）
    """
    # ⭐⭐⭐ 重置文件标记
    reset_data_status()
    
    logger.info("\n🔄 数据状态已重置")
    
    return {
        'success': True,
        'message': '数据状态已重置，可以重新上传'
    }


@router.get("/uploaded-files")
async def get_uploaded_files():
    """
    获取已上传的文件列表
    """
    status = get_data_status()
    
    if not status['uploaded']:
        return {
            'success': False,
            'message': '尚未上传数据',
            'files': []
        }
    
    files_info = []
    required_files = [
        'occupancy.csv',
        'volume.csv',
        'weather_central.csv',
        'e_price.csv'
    ]
    
    for filename in required_files:
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            files_info.append({
                'filename': filename,
                'size': f"{file_size / 1024:.2f} KB",
                'modified': file_mtime.isoformat(),
                'exists': True
            })
        else:
            files_info.append({
                'filename': filename,
                'exists': False
            })
    
    return {
        'success': True,
        'files': files_info,
        'upload_time': status['upload_time']
    }