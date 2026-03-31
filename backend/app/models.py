from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class StaticFeatures(BaseModel):
    """静态特征"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    charge_count: float = Field(..., description="充电桩数量")


class PredictionRequest(BaseModel):
    """预测请求"""
    station_id: str = Field(..., description="充电站ID")
    hist_occupancy: List[float] = Field(..., min_items=168, max_items=168, description="历史占用率(168小时)")
    hist_volume: List[float] = Field(..., min_items=168, max_items=168, description="历史充电量(168小时)")
    hist_price: List[float] = Field(..., min_items=168, max_items=168, description="历史价格(168小时)")
    time_features: List[List[float]] = Field(..., min_items=168, max_items=168, description="历史时间特征(168x18)")
    future_time_features: List[List[float]] = Field(..., min_items=24, max_items=24, description="未来时间特征(24x18)")
    static_features: StaticFeatures = Field(..., description="静态特征")

    class Config:
        json_schema_extra = {
            "example": {
                "station_id": "station_001",
                "hist_occupancy": [0.5] * 168,
                "hist_volume": [100.0] * 168,
                "hist_price": [1.5] * 168,
                "time_features": [[0.0] * 18] * 168,
                "future_time_features": [[0.0] * 18] * 24,
                "static_features": {
                    "longitude": 121.5,
                    "latitude": 31.2,
                    "charge_count": 10.0
                }
            }
        }


class PredictionResponse(BaseModel):
    """预测响应"""
    station_id: str
    predictions: List[float]
    timestamps: List[str]
    congestion_levels: List[str]
    average_occupancy: float
    peak_hour: int
    peak_occupancy: float


class StationListResponse(BaseModel):
    """充电站列表响应"""
    stations: List[str]
    total: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    message: str
    model_loaded: bool
    device: str