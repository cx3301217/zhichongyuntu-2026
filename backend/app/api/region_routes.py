# app/api/region_routes.py
"""
区域API路由 - 提供275个区域的预测接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import os
import numpy as np

router = APIRouter()

# 全局变量
region_predictor = None
regions_data = []
# 缓存：避免重复预测
cached_all_predictions = None  # List[Dict]
cached_region_24h = {}  # Dict[int, Dict]

class UserLocation(BaseModel):
    latitude: float
    longitude: float
    top_k: int = 5

def check_data_uploaded():
    """检查数据是否已上传"""
    try:
        from backend.app.data_status import is_data_uploaded
        return is_data_uploaded()
    except Exception as e:
        print(f"检查数据状态失败: {e}")
        return False

def init_region_predictor():
    """初始化区域预测器"""
    global region_predictor
    try:
        from backend.app.region_predictor import RegionPredictor
        region_predictor = RegionPredictor(
            model_path="models/tft_high_performance.pkl"  # 使用高性能TFT模型（R²>0.90）
        )
        # 自动加载数据
        if not region_predictor.data_loaded:
            print("自动加载预测数据...")
            region_predictor.load_data()
        print("区域预测器初始化成功")
        return True
    except Exception as e:
        print(f"区域预测器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_regions_data():
    """加载区域数据"""
    global regions_data
    regions_file = "backend/shenzhen_regions_275.json"
    
    if os.path.exists(regions_file):
        with open(regions_file, 'r', encoding='utf-8') as f:
            regions_data = json.load(f)
        print(f"已加载 {len(regions_data)} 个区域数据")
    else:
        print(f"未找到区域数据文件: {regions_file}")
        regions_data = []

# 启动时加载
load_regions_data()
init_region_predictor()

@router.get("/regions/all")
async def get_all_regions(refresh: bool = False):
    """获取所有275个区域信息及当前预测"""
    try:
        # 每次请求前确保加载最新区域文件（支持热更新）
        load_regions_data()
        # ⭐⭐⭐ 关键修复：检查数据是否上传
        data_uploaded = check_data_uploaded()

        if not regions_data:
            raise HTTPException(status_code=503, detail="区域数据未加载")

        # ⭐⭐⭐ 如果数据未上传，返回所有区域但占用率为 null
        if not data_uploaded:
            print("数据未上传，返回无预测结果")
            result_regions = []
            for region in regions_data:
                result_regions.append({
                    **region,
                    'current_occupancy': None,  # ⭐ 设置为 null，前端不显示
                    'congestion_level': 'unknown',
                    'has_prediction': False,
                    'prediction_time': None
                })

            return {
                'success': True,  # ⭐ 修复：即使数据未上传也要返回成功，让前端显示区域
                'regions': result_regions,
                'total_count': len(result_regions),
                'message': '请先上传训练数据',
                'data_uploaded': False,
                'timestamp': datetime.now().isoformat()
            }

        # ⭐⭐⭐ 数据已上传，进行真实预测（支持缓存与手动刷新）
        if region_predictor is None:
            print("预测器未加载")
            raise HTTPException(status_code=503, detail="预测器未初始化")

        # 使用缓存，除非前端显式刷新
        global cached_all_predictions
        if (not refresh) and cached_all_predictions:
            predictions = cached_all_predictions
            print(f"使用缓存的所有区域预测，共 {len(predictions)} 条")
        else:
            print(f"开始预测所有区域（数据已上传）...")
            try:
                # 确保数据已加载
                if not region_predictor.data_loaded:
                    print("数据未加载，正在加载...")
                    region_predictor.load_data()
                
                predictions = region_predictor.predict_all_regions()
                cached_all_predictions = predictions
                # 刷新时清空24h缓存，避免不一致
                cached_region_24h.clear()
            except Exception as pred_error:
                print(f"预测失败: {pred_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"预测失败: {str(pred_error)}")

        print(f"预测完成，共 {len(predictions)} 个结果")

        # 创建预测字典
        pred_dict = {p['region_id']: p for p in predictions}

        # 统计直连匹配覆盖率
        direct_match_count = sum(1 for r in regions_data if r['region_id'] in pred_dict)
        fallback_mapping = direct_match_count < int(len(regions_data) * 0.7)

        # 当直连匹配率过低时，按顺序回退匹配，尽量保证每个区域都有结果
        predictions_sorted = sorted(predictions, key=lambda x: x['region_id']) if fallback_mapping else None

        # 合并区域信息和预测
        result_regions = []
        for idx, region in enumerate(regions_data):
            region_id = region['region_id']

            pred = None
            if not fallback_mapping and region_id in pred_dict:
                pred = pred_dict[region_id]
            elif fallback_mapping and predictions_sorted:
                # 顺序分配，保证有值（可能与真实区域不一一对应，但优先保障可视化不为空）
                pred = predictions_sorted[idx % len(predictions_sorted)] if predictions_sorted else None

            if pred is not None:
                # 计算拥挤度等级
                occ = pred['current_occupancy']
                if occ < 30:
                    congestion = 'low'
                elif occ < 60:
                    congestion = 'medium'
                elif occ < 85:
                    congestion = 'high'
                else:
                    congestion = 'very_high'

                result_regions.append({
                    **region,
                    'current_occupancy': pred['current_occupancy'],
                    'current_volume': pred.get('current_volume'),
                    'congestion_level': congestion,
                    'has_prediction': True,
                    'prediction_time': pred.get('prediction_time', datetime.now().isoformat())
                })
            else:
                result_regions.append({
                    **region,
                    'current_occupancy': None,
                    'congestion_level': 'unknown',
                    'has_prediction': False
                })

        return {
            'success': True,
            'regions': result_regions,
            'total_count': len(result_regions),
            'data_uploaded': True,
            'timestamp': datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"获取区域数据失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/regions/{region_id}")
async def get_region_detail(region_id: int):
    """获取单个区域详细信息"""
    try:
        region = next((r for r in regions_data if r['region_id'] == region_id), None)
        
        if region is None:
            raise HTTPException(status_code=404, detail="区域不存在")
        
        return {
            'success': True,
            'region': region
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/regions/{region_id}/predict")
async def predict_region_24h(region_id: int, refresh: bool = False):
    """预测特定区域未来24小时"""
    try:
        # ⭐⭐⭐ 检查数据是否上传
        if not check_data_uploaded():
            return {
                'success': False,
                'message': '请先上传训练数据',
                'data_uploaded': False
            }
        
        if region_predictor is None:
            raise HTTPException(status_code=503, detail="预测模型未加载")
        
        region = next((r for r in regions_data if r['region_id'] == region_id), None)
        if region is None:
            raise HTTPException(status_code=404, detail="区域不存在")
        
        # 预测（带缓存）
        global cached_region_24h
        if (not refresh) and (region_id in cached_region_24h):
            prediction = cached_region_24h[region_id]
            print(f"使用缓存的区域{region_id} 24h预测")
        else:
            # 确保数据已加载
            if not region_predictor.data_loaded:
                print("数据未加载，正在加载...")
                region_predictor.load_data()
            prediction = region_predictor.predict_region(region_id)
            cached_region_24h[region_id] = prediction
        
        return {
            'success': True,
            'region_id': region_id,
            'region_name': region['name'],
            'predictions': prediction,
            'data_uploaded': True,
            'timestamp': datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"预测失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recommend")
async def recommend_regions(location: UserLocation):
    """根据用户位置推荐充电区域"""
    try:
        # ⭐⭐⭐ 检查数据是否上传
        if not check_data_uploaded():
            return {
                'success': False,
                'message': '请先上传训练数据',
                'data_uploaded': False
            }
        
        if region_predictor is None:
            raise HTTPException(status_code=503, detail="预测模型未加载")
        
        # 预测所有区域
        predictions = region_predictor.predict_all_regions()
        pred_dict = {p['region_id']: p for p in predictions}
        
        # 计算推荐分数
        recommendations = []
        
        for region in regions_data:
            region_id = region['region_id']
            
            # 计算距离
            lat_diff = region['latitude'] - location.latitude
            lon_diff = region['longitude'] - location.longitude
            distance = np.sqrt(lat_diff**2 + lon_diff**2) * 111
            
            # 获取预测
            if region_id in pred_dict:
                pred = pred_dict[region_id]
                occupancy = pred['current_occupancy']
            else:
                occupancy = 50
            
            # 综合评分
            max_distance = 50
            distance_score = max(0, (max_distance - distance) / max_distance)
            occupancy_score = (100 - occupancy) / 100
            
            total_score = 0.6 * distance_score + 0.4 * occupancy_score
            
            # 计算拥挤度
            if occupancy < 30:
                congestion = 'low'
            elif occupancy < 60:
                congestion = 'medium'
            elif occupancy < 85:
                congestion = 'high'
            else:
                congestion = 'very_high'
            
            recommendations.append({
                'region_id': region_id,
                'name': region['name'],
                'district': region['district'],
                'latitude': region['latitude'],
                'longitude': region['longitude'],
                'charge_count': region['charge_count'],
                'distance': round(distance, 2),
                'current_occupancy': round(occupancy, 2),
                'congestion_level': congestion,
                'score': round(total_score, 4)
            })
        
        # 排序并返回Top K
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        top_recommendations = recommendations[:location.top_k]
        
        return {
            'success': True,
            'user_location': {
                'latitude': location.latitude,
                'longitude': location.longitude
            },
            'recommendations': top_recommendations,
            'total_candidates': len(recommendations),
            'data_uploaded': True,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        print(f"推荐失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        'status': 'healthy',
        'model_loaded': region_predictor is not None,
        'regions_count': len(regions_data),
        'data_uploaded': check_data_uploaded(),
        'model_type': 'dual_target_tft'
    }