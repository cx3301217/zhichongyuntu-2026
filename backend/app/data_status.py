# app/data_status.py
"""
数据状态管理 - 使用文件标记来持久化上传状态
"""
import os
import json
from datetime import datetime
from typing import Optional

# 状态文件路径（基于 __file__ 推导，兼容本地开发和容器）
_STATUS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
STATUS_FILE = os.path.join(_STATUS_DIR, "upload_status.json")

def set_data_uploaded(uploaded: bool = True, upload_time: Optional[str] = None):
    """
    设置数据上传状态
    """
    status = {
        'uploaded': uploaded,
        'upload_time': upload_time or datetime.now().isoformat()
    }
    
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 数据状态已设置: uploaded={uploaded}")
    return status


def get_data_status() -> dict:
    """
    获取数据上传状态
    """
    if not os.path.exists(STATUS_FILE):
        return {
            'uploaded': False,
            'upload_time': None
        }
    
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            'uploaded': False,
            'upload_time': None
        }


def reset_data_status():
    """
    重置数据状态
    """
    return set_data_uploaded(False, None)


def is_data_uploaded() -> bool:
    """
    检查数据是否已上传
    """
    status = get_data_status()
    return status.get('uploaded', False)