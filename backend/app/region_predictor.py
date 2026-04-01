# app/region_predictor.py
"""
区域预测器 - 预测275个交通区域的占用率和负荷
"""
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time
import os

# ============================================
# CPU 环境兜底：Zeabur 容器无 GPU，强制禁用 CUDA，
# 确保任何 pickle / torch.load 路径都不会尝试访问 GPU。
# ============================================
torch.cuda.is_available = lambda: False
torch.cuda.device_count = lambda: 0
torch.cuda._cached_device_count = 0

# ============================================
# 模型结构定义（与训练时完全相同）
# ============================================

class TemporalFusionTransformer(nn.Module):
    """时间融合Transformer模型"""
    
    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        output_size: int = 2
    ):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # 输入嵌入层
        self.input_embedding = nn.Linear(input_size, hidden_size)
        
        # Transformer编码器
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=hidden_size * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers
        )
        
        # 输出层
        self.output_layer = nn.Linear(hidden_size, output_size)
        
    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        embedded = self.input_embedding(x)
        encoded = self.transformer_encoder(embedded)
        output = self.output_layer(encoded[:, -1, :])
        return output


class DualTFTModel(nn.Module):
    """双输出TFT模型 - 同时预测占用率和电量负荷"""
    
    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1
    ):
        super().__init__()
        
        # 共享的特征提取器
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # Transformer编码器
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=hidden_size * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers
        )
        
        # 占用率预测头
        self.occupancy_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1)
        )
        
        # 电量负荷预测头
        self.volume_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1)
        )
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        features = self.feature_extractor(x)
        encoded = self.transformer_encoder(features)
        last_hidden = encoded[:, -1, :]
        
        occupancy = self.occupancy_head(last_hidden)
        volume = self.volume_head(last_hidden)
        
        return occupancy, volume


# ============================================
# 改进版模型（与优化训练脚本一致）
# ============================================

class PositionalEncoding(nn.Module):
    """位置编码（用于改进版模型）"""
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class GatedResidualNetwork(nn.Module):
    """门控残差网络（TFT核心组件）"""
    
    def __init__(self, input_size, hidden_size, output_size, dropout=0.1):
        super().__init__()
        
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.elu = nn.ELU()
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.dropout = nn.Dropout(dropout)
        
        self.output_fc = nn.Linear(hidden_size, output_size)
        self.gate_fc = nn.Linear(hidden_size, output_size)
        self.gate_norm = nn.LayerNorm(output_size)
        
        if input_size != output_size:
            self.skip_fc = nn.Linear(input_size, output_size)
        else:
            self.skip_fc = None
    
    def forward(self, x):
        if self.skip_fc is not None:
            residual = self.skip_fc(x)
        else:
            residual = x
        
        x = self.fc1(x)
        x = self.elu(x)
        x = self.fc2(x)
        x = self.dropout(x)
        
        x_out = self.output_fc(x)
        gate = torch.sigmoid(self.gate_fc(x))
        
        x = x_out * gate
        x = self.gate_norm(x + residual)
        
        return x


class ImprovedTFTModel(nn.Module):
    """与 train_tft_model_optimized.py 对齐的改进版TFT模型"""
    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,
        num_heads: int = 8,
        num_layers: int = 3,
        dropout: float = 0.15,
        ff_dim: int = 512
    ):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size

        self.input_embedding = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        self.pos_encoder = PositionalEncoding(hidden_size)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=ff_dim,
            dropout=dropout,
            activation='gelu',
            batch_first=True,
            norm_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
            norm=nn.LayerNorm(hidden_size)
        )

        self.attention_pool = nn.MultiheadAttention(
            hidden_size, num_heads, dropout=dropout, batch_first=True
        )

        self.occupancy_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.LayerNorm(hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.GELU(),
            nn.Dropout(dropout / 2 if dropout > 0 else 0.0),
            nn.Linear(hidden_size // 4, 1),
            nn.Sigmoid()
        )

        self.volume_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.LayerNorm(hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.GELU(),
            nn.Dropout(dropout / 2 if dropout > 0 else 0.0),
            nn.Linear(hidden_size // 4, 1),
            nn.ReLU()
        )

    def forward(self, x):
        embedded = self.input_embedding(x)
        embedded = self.pos_encoder(embedded)
        encoded = self.transformer_encoder(embedded)
        query = encoded[:, -1:, :]
        pooled, _ = self.attention_pool(query, encoded, encoded)
        pooled = pooled.squeeze(1)
        occupancy = self.occupancy_head(pooled)
        volume = self.volume_head(pooled)
        return occupancy, volume


class HighPerformanceTFT(nn.Module):
    """高性能TFT模型（与train_tft_high_performance.py一致）- R²>0.90"""
    
    def __init__(self, input_size, hidden_size=256, lstm_layers=3, 
                 num_heads=8, dropout=0.15, horizon=24):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.horizon = horizon
        
        # 1. 输入投影（带GRN）
        self.input_grn = GatedResidualNetwork(
            input_size=input_size,
            hidden_size=hidden_size,
            output_size=hidden_size,
            dropout=dropout
        )
        
        # 2. 位置编码
        self.pos_encoder = PositionalEncoding(hidden_size)
        
        # 3. LSTM编码器（TFT核心）
        self.lstm = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=lstm_layers,
            dropout=dropout if lstm_layers > 1 else 0,
            batch_first=True,
            bidirectional=False
        )
        
        # 4. 后LSTM的GRN
        self.post_lstm_grn = GatedResidualNetwork(
            input_size=hidden_size,
            hidden_size=hidden_size,
            output_size=hidden_size,
            dropout=dropout
        )
        
        # 5. 自注意力（TFT核心）
        self.self_attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # 6. 注意力后的GRN
        self.post_attention_grn = GatedResidualNetwork(
            input_size=hidden_size,
            hidden_size=hidden_size,
            output_size=hidden_size,
            dropout=dropout
        )
        
        # 7. 上下文注意力（用于序列池化）
        self.context_attention = nn.MultiheadAttention(
            hidden_size, num_heads, dropout=dropout, batch_first=True
        )
        
        # 8. 占用率预测头
        self.occ_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.BatchNorm1d(hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, horizon),
            nn.Sigmoid()  # 占用率限制在[0,1]
        )
        
        # 9. 电量负荷预测头
        self.vol_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.BatchNorm1d(hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, horizon),
            nn.ReLU()  # 电量非负
        )
    
    def forward(self, x):
        """
        Args:
            x: (batch, lookback, input_size)
        Returns:
            occ_pred: (batch, horizon)
            vol_pred: (batch, horizon)
        """
        # 1. 输入投影 + GRN
        embedded = self.input_grn(x)
        
        # 2. 位置编码
        embedded = self.pos_encoder(embedded)
        
        # 3. LSTM编码
        lstm_out, (h_n, c_n) = self.lstm(embedded)
        
        # 4. 后LSTM的GRN
        lstm_out = self.post_lstm_grn(lstm_out)
        
        # 5. 自注意力
        attn_out, _ = self.self_attention(lstm_out, lstm_out, lstm_out)
        
        # 6. 注意力后的GRN
        attn_out = self.post_attention_grn(attn_out)
        
        # 7. 上下文注意力池化
        context, _ = self.context_attention(
            attn_out[:, -1:, :],  # query: 最后一个时间步
            attn_out,             # key
            attn_out              # value
        )
        context = context.squeeze(1)
        
        # 8. 双头预测
        occ_pred = self.occ_head(context)
        vol_pred = self.vol_head(context)
        
        return occ_pred, vol_pred


# ============================================
# 区域预测器
# ============================================

class RegionPredictor:
    """
    区域预测器
    使用训练好的TFT模型预测275个区域的占用率和电量负荷
    """
    
    def __init__(
        self,
        model_path: str = "tft_high_performance.pkl",
        data_dir: str = "data",
        lookback: int = 48,  # ⭐ 修改为与训练一致：48小时
        horizon: int = 24
    ):
        """
        初始化预测器
        """
        _base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        _models_base = os.path.join(_base, "models")
        _data_base = os.path.join(_base, "data")

        self.model_path = (
            model_path
            if os.path.isabs(model_path)
            else os.path.join(_models_base, model_path)
        )
        self.data_dir = (
            data_dir
            if os.path.isabs(data_dir)
            else os.path.join(_data_base, data_dir)
        )
        self.lookback = lookback
        self.horizon = horizon
        self.device = torch.device('cpu')
        
        # 数据容器
        self.occupancy_data = None
        self.volume_data = None
        self.region_info = None
        self.weather_data = None
        self.price_data = None
        self.data_loaded = False
        self.scalers = None  # 从检查点读取的scaler，用于反标准化
        self.config = None   # 从检查点读取的config
        self.n_regions = None  # 从检查点读取的区域数量
        
        # 加载模型
        self.model = self._load_model()
        
        print(f"区域预测器初始化完成")
        print(f"   - 模型路径: {model_path}")
        print(f"   - 数据目录: {data_dir}")
        print(f"   - 历史窗口: {lookback}小时")
        print(f"   - 预测窗口: {horizon}小时")
    
    def _resolve_model_path(self, candidate: str) -> str:
        """解析模型路径：若给定不存在，则尝试常见别名（均使用绝对路径）。"""
        _base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        _models_dir = os.path.join(_base, "models")

        aliases = [
            candidate,
            "dual_tft_model_complete_cpu.pkl",
            "dual_tft_model_complete_cpu_pkl",
            "duai_tft_model_complete_cpu_pkl",
            "best_model.pth",
        ]
        for name in aliases:
            path = name if os.path.isabs(name) else os.path.join(_models_dir, name)
            if os.path.exists(path):
                return path
        # 若都找不到，返回原路径（让上层抛错）
        return candidate

    def _load_model(self) -> Optional[nn.Module]:
        """加载训练好的模型，并根据权重自动匹配架构"""
        try:
            resolved_path = self._resolve_model_path(self.model_path)
            if not os.path.exists(resolved_path):
                print(f"模型文件不存在: {resolved_path}")
                print(f"   请先训练模型！")
                raise FileNotFoundError(f"模型文件不存在: {resolved_path}")

            # 根据文件扩展名选择加载方式
            if resolved_path.endswith('.pkl'):
                # 模型用 torch.save 存入 pickle，底层包含 CUDA 设备信息，
                # 必须用 torch.load 并指定 map_location='cpu' 才能在无 GPU 环境加载
                checkpoint = torch.load(resolved_path, map_location='cpu')
            else:
                checkpoint = torch.load(resolved_path, map_location=self.device)

            # 检查文件格式
            if isinstance(checkpoint, dict):
                # 如果是字典，尝试提取 state_dict 和 scalers
                if 'model_state' in checkpoint:
                    print("检测到完整检查点格式（包含 model_state）")
                    state_dict = checkpoint['model_state']
                    # 读取scalers（若有）
                    if 'scalers' in checkpoint:
                        self.scalers = checkpoint['scalers']
                elif 'state_dict' in checkpoint:
                    print("检测到检查点格式（包含 state_dict）")
                    state_dict = checkpoint['state_dict']
                    if 'scalers' in checkpoint:
                        self.scalers = checkpoint['scalers']
                elif 'model_state_dict' in checkpoint:
                    print("检测到高性能TFT完整包格式（包含 model_state_dict）")
                    state_dict = checkpoint['model_state_dict']
                    # 读取scalers（高性能TFT必须有）
                    if 'scalers' in checkpoint:
                        self.scalers = checkpoint['scalers']
                        print(f"  ✓ 加载了scalers: {list(self.scalers.keys())}")
                    # 读取其他配置信息
                    if 'config' in checkpoint:
                        self.config = checkpoint['config']
                        print(f"  ✓ 加载了config")
                    if 'n_regions' in checkpoint:
                        self.n_regions = checkpoint['n_regions']
                        print(f"  ✓ 区域数量: {self.n_regions}")
                else:
                    print("检测到直接 state_dict 格式")
                    state_dict = checkpoint
            else:
                print("检测到模型对象格式")
                state_dict = checkpoint

            # 根据权重键名判断架构
            keys = list(state_dict.keys())
            
            # 判断是否为高性能TFT（包含LSTM+GRN）
            use_high_perf = any("input_grn" in k for k in keys) or any("lstm" in k for k in keys) or any("post_lstm_grn" in k for k in keys)
            
            # 判断是否为改进版TFT（Transformer+注意力池化）
            use_improved = any(k.startswith("input_embedding.") for k in keys) or any("attention_pool" in k for k in keys)

            if use_high_perf:
                # 高性能TFT模型（R²>0.90）
                print("检测到高性能TFT模型架构（包含LSTM+GRN+自注意力）")
                
                # 从checkpoint提取配置（已在前面的model_state_dict分支中提取）
                if self.config is None:
                    self.config = checkpoint.get('config', {}) if isinstance(checkpoint, dict) else {}
                if self.n_regions is None:
                    self.n_regions = checkpoint.get('n_regions', 275) if isinstance(checkpoint, dict) else 275
                
                cfg = self.config
                n_regions = self.n_regions
                
                # 从checkpoint的权重shape推断input_size（最准确）
                input_size = state_dict['input_grn.fc1.weight'].shape[1]
                print(f"  从checkpoint推断input_size: {input_size}")
                
                # 或者从数据维度计算（假设price_dim与n_regions相同）
                weather_dim = 6  # 天气特征维度
                price_dim = n_regions  # 电价维度（每个区域不同）
                
                model = HighPerformanceTFT(
                    input_size=input_size,
                    hidden_size=cfg.get('hidden_size', 256),
                    lstm_layers=cfg.get('lstm_layers', 3),
                    num_heads=cfg.get('num_heads', 8),
                    dropout=cfg.get('dropout', 0.15),
                    horizon=cfg.get('horizon', 24)
                )
                print(f"  ✓ 输入维度: {input_size}")
                print(f"     (occ={n_regions} + vol={n_regions} + weather={weather_dim} + price={price_dim})")
                print(f"  ✓ 隐藏层: {cfg.get('hidden_size', 256)}, LSTM层数: {cfg.get('lstm_layers', 3)}")
                
            elif use_improved:
                # 改进版Transformer模型
                print("检测到改进版Transformer模型架构")
                cfg = checkpoint.get('config', {}) if isinstance(checkpoint, dict) else {}
                model = ImprovedTFTModel(
                    input_size=cfg.get('input_size', 10),
                    hidden_size=cfg.get('hidden_size', 128),
                    num_heads=cfg.get('num_heads', 8),
                    num_layers=cfg.get('num_layers', 3),
                    dropout=cfg.get('dropout', 0.15),
                    ff_dim=cfg.get('ff_dim', 512)
                )
            else:
                # 基础双输出模型
                print("检测到基础TFT模型架构")
                model = DualTFTModel(
                    input_size=10,
                    hidden_size=64,
                    num_heads=4,
                    num_layers=2,
                    dropout=0.1
                )

            # 加载权重（严格匹配）
            model.load_state_dict(state_dict)
            model.eval()
            print(f"模型加载成功")
            return model

        except Exception as e:
            print(f"模型加载失败: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"模型加载失败: {e}")
    
    def load_data(self) -> bool:
        """
        加载上传的CSV数据
        """
        try:
            print("\n开始加载CSV数据...")
            
            # 检查所有文件是否存在（inf.csv 为可选）
            required_files = {
                'occupancy': 'occupancy.csv',
                'volume': 'volume.csv',
                'weather': 'weather_central.csv',
                'price': 'e_price.csv'
            }
            
            for key, filename in required_files.items():
                filepath = os.path.join(self.data_dir, filename)
                if not os.path.exists(filepath):
                    print(f"文件不存在: {filepath}")
                    return False
            
            # 读取区域信息（可选，仅用于日志，不参与推理）
            inf_path = os.path.join(self.data_dir, 'inf.csv')
            if os.path.exists(inf_path):
                self.region_info = pd.read_csv(inf_path)
                print(f"区域信息: {len(self.region_info)} 个区域（可选）")
            else:
                self.region_info = None
                print(f"inf.csv 不存在（可选文件，不影响预测）")
            
            # 读取占用率数据
            occ_path = os.path.join(self.data_dir, 'occupancy.csv')
            occ_df = pd.read_csv(occ_path)
            self.occupancy_data = occ_df
            print(f"占用率数据: {self.occupancy_data.shape}")
            
            # 读取电量负荷数据
            vol_path = os.path.join(self.data_dir, 'volume.csv')
            vol_df = pd.read_csv(vol_path)
            self.volume_data = vol_df
            print(f"电量负荷数据: {self.volume_data.shape}")
            
            # 读取天气数据
            weather_path = os.path.join(self.data_dir, 'weather_central.csv')
            self.weather_data = pd.read_csv(weather_path)
            print(f"天气数据: {self.weather_data.shape}")
            
            # 读取电价数据
            price_path = os.path.join(self.data_dir, 'e_price.csv')
            self.price_data = pd.read_csv(price_path)
            print(f"电价数据: {self.price_data.shape}")
            
            self.data_loaded = True
            print("所有数据加载成功\n")
            return True
            
        except Exception as e:
            print(f"数据加载失败: {e}")
            import traceback
            traceback.print_exc()
            self.data_loaded = False
            return False
    
    def _get_latest_data(self, region_id: int) -> Optional[Dict]:
        """
        获取指定区域的最新数据
        """
        try:
            # 从占用率数据中获取最新值
            occ_cols = [col for col in self.occupancy_data.columns if col != 'time']
            if occ_cols:
                latest_occ = self.occupancy_data[occ_cols].iloc[-1].mean()
            else:
                latest_occ = 50.0
            
            # 从电量负荷数据中获取最新值
            vol_cols = [col for col in self.volume_data.columns if col != 'time']
            if vol_cols:
                latest_vol = self.volume_data[vol_cols].iloc[-1].mean()
            else:
                latest_vol = 100.0
            
            return {
                'occupancy': float(latest_occ),
                'volume': float(latest_vol)
            }
            
        except Exception as e:
            print(f"获取区域{region_id}最新数据失败: {e}")
            return {'occupancy': 50.0, 'volume': 100.0}

    def _get_numeric_arrays(self):
        """获取数值矩阵及列名列表。"""
        occ_cols = [c for c in self.occupancy_data.columns if c != 'time']
        vol_cols = [c for c in self.volume_data.columns if c != 'time']
        weather_cols = [c for c in self.weather_data.columns if c != 'time']
        price_cols = [c for c in self.price_data.columns if c != 'time']

        occ_np = self.occupancy_data[occ_cols].values
        vol_np = self.volume_data[vol_cols].values
        weather_np = self.weather_data[weather_cols].values
        price_np = self.price_data[price_cols].values
        return occ_np, vol_np, price_np, weather_np, occ_cols

    def _scale_arrays(self, occ_np: np.ndarray, vol_np: np.ndarray, price_np: np.ndarray, weather_np: np.ndarray) -> tuple:
        """按训练时保存的scaler进行标准化，若无scaler则使用简单标准化。"""
        if not self.scalers or not isinstance(self.scalers, dict):
            # 无scaler时使用简单标准化（0均值1标准差）
            occ_np = (occ_np - np.mean(occ_np)) / (np.std(occ_np) + 1e-8)
            vol_np = (vol_np - np.mean(vol_np)) / (np.std(vol_np) + 1e-8)
            price_np = (price_np - np.mean(price_np)) / (np.std(price_np) + 1e-8)
            weather_np = (weather_np - np.mean(weather_np, axis=0, keepdims=True)) / (np.std(weather_np, axis=0, keepdims=True) + 1e-8)
            return occ_np, vol_np, price_np, weather_np
        
        try:
            from sklearn.preprocessing import RobustScaler, StandardScaler
            occ_scaler = self.scalers.get('occupancy')
            vol_scaler = self.scalers.get('volume')
            price_scaler = self.scalers.get('price')
            weather_scaler = self.scalers.get('weather')

            if occ_scaler is not None:
                occ_np = occ_scaler.transform(occ_np)
            if vol_scaler is not None:
                vol_np = vol_scaler.transform(vol_np)
            if price_scaler is not None:
                price_np = price_scaler.transform(price_np)
            if weather_scaler is not None:
                weather_np = weather_scaler.transform(weather_np)
        except Exception as e:
            print(f"使用训练scaler失败，使用简单标准化: {e}")
            occ_np = (occ_np - np.mean(occ_np)) / (np.std(occ_np) + 1e-8)
            vol_np = (vol_np - np.mean(vol_np)) / (np.std(vol_np) + 1e-8)
            price_np = (price_np - np.mean(price_np)) / (np.std(price_np) + 1e-8)
            weather_np = (weather_np - np.mean(weather_np, axis=0, keepdims=True)) / (np.std(weather_np, axis=0, keepdims=True) + 1e-8)
        return occ_np, vol_np, price_np, weather_np

    def _inverse_scale_single(self, value: float, scaler, feature_index: int, data_array: np.ndarray) -> float:
        """使用已保存的scaler或数据统计进行反标准化。"""
        if scaler is None:
            # 无scaler时使用数据本身的统计量
            try:
                if feature_index < data_array.shape[1]:
                    mean_val = np.mean(data_array[:, feature_index])
                    std_val = np.std(data_array[:, feature_index]) + 1e-8
                    return float(value * std_val + mean_val)
                else:
                    # 如果索引超出范围，返回原值
                    return float(value)
            except Exception as e:
                print(f"反标准化失败: {e}")
                return float(value)
        
        try:
            # RobustScaler/StandardScaler 均有 center_/scale_ 或 mean_/scale_
            if hasattr(scaler, 'center_') and hasattr(scaler, 'scale_'):
                if feature_index < len(scaler.scale_):
                    return float(value * scaler.scale_[feature_index] + scaler.center_[feature_index])
            if hasattr(scaler, 'mean_') and hasattr(scaler, 'scale_'):
                if feature_index < len(scaler.scale_):
                    return float(value * scaler.scale_[feature_index] + scaler.mean_[feature_index])
        except Exception as e:
            print(f"scaler反标准化失败: {e}")
        return float(value)

    def _is_high_perf_model(self) -> bool:
        """判断当前模型是否为高性能TFT（需要全区域输入）"""
        return isinstance(self.model, HighPerformanceTFT)
    
    def _build_input_sequence(self, region_index: int = 0) -> Optional[torch.Tensor]:
        """
        构建输入序列张量。
        - 高性能TFT: (1, lookback, 831) = (1, lookback, 275+275+6+275) 包含所有区域
        - 其他模型: (1, lookback, 9) 单区域特征
        """
        try:
            occ_np, vol_np, price_np, weather_np, occ_cols = self._get_numeric_arrays()
            
            # 检查数据长度
            if len(occ_np) < self.lookback:
                print(f"数据长度不足: {len(occ_np)} < {self.lookback}")
                return None
            
            # 按训练scaler进行标准化
            occ_np, vol_np, price_np, weather_np = self._scale_arrays(occ_np, vol_np, price_np, weather_np)
            
            # 取最后lookback步
            hist_occ = occ_np[-self.lookback:, :]      # (lookback, regions)
            hist_vol = vol_np[-self.lookback:, :]      # (lookback, regions)
            hist_weather = weather_np[-self.lookback:, :]  # (lookback, weather_features)
            hist_price = price_np[-self.lookback:, :]  # (lookback, 1 or regions)
            
            # 判断模型类型
            if self._is_high_perf_model():
                # 高性能TFT：保留所有区域信息
                # 拼接特征：[occ(275), vol(275), weather(6), price(275)] = 831维
                features = np.concatenate([
                    hist_occ,       # (lookback, regions)
                    hist_vol,       # (lookback, regions)
                    hist_weather,   # (lookback, weather_features)
                    hist_price      # (lookback, regions)
                ], axis=-1)
                
                expected_dim = hist_occ.shape[1] * 2 + hist_weather.shape[1] + hist_price.shape[1]
                print(f"  ✓ 高性能TFT输入: (lookback={self.lookback}, features={features.shape[1]}, expected={expected_dim})")
            else:
                # 其他模型：单区域特征
                if region_index >= occ_np.shape[1]:
                    print(f"区域索引超出范围: {region_index} >= {occ_np.shape[1]}")
                    return None
                
                hist_occ_single = hist_occ[:, region_index:region_index+1]
                hist_vol_single = hist_vol[:, region_index:region_index+1]
                
                # 电价处理
                if hist_price.shape[1] == 1:
                    hist_price_single = hist_price
                else:
                    hist_price_single = hist_price[:, region_index:region_index+1]
                
                # 拼接特征：occ(1) + vol(1) + price(1) + weather(6) = 9维
                features = np.concatenate([
                    hist_occ_single,
                    hist_vol_single,
                    hist_price_single,
                    hist_weather
                ], axis=-1)
                
                expected_dim = 1 + 1 + 1 + hist_weather.shape[1]
            
            # 验证维度
            if features.shape[1] != expected_dim:
                print(f"特征维度不匹配: {features.shape[1]}, 期望: {expected_dim}")
                return None
            
            # 张量化
            x = torch.from_numpy(features.astype(np.float32)).unsqueeze(0)  # (1, lookback, input_size)
            return x
        except Exception as e:
            print(f"构建输入序列失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def predict_region(self, region_id: int, predict_hours: int = 24) -> Dict:
        """
        预测单个区域未来24小时的占用率和电量负荷（使用已训练模型）
        """
        try:
            # 检查数据是否已加载
            if not self.data_loaded:
                raise RuntimeError("数据未加载，请先上传训练数据")

            # 检查模型是否已加载
            if self.model is None:
                raise RuntimeError("模型未加载，请先训练模型")

            # 区域索引（列索引）
            occ_cols = [c for c in self.occupancy_data.columns if c != 'time']
            
            region_index = None
            
            # 首先尝试直接匹配 region_id（字符串形式，如 '102'）
            if str(region_id) in occ_cols:
                region_index = occ_cols.index(str(region_id))
            # 然后尝试 region_ 前缀格式（如 'region_102'）
            elif f"region_{region_id}" in occ_cols:
                region_index = occ_cols.index(f"region_{region_id}")
            else:
                raise RuntimeError(f"区域 {region_id} 找不到对应的列（可用列: {len(occ_cols)}个）")
            
            if region_index is None:
                raise RuntimeError(f"区域 {region_id} 找不到对应的列")

            x = self._build_input_sequence(region_index)
            if x is None:
                raise RuntimeError("历史窗口不足，无法预测")

            self.model.to(self.device)
            x = x.to(self.device)

            # ⭐ 模型一次性预测24小时
            with torch.no_grad():
                pred_occ, pred_vol = self.model(x)
            
            # 模型输出: (batch, horizon) -> (1, 24)
            # 转换为numpy数组
            pred_occ_arr = pred_occ.squeeze(0).cpu().numpy()  # (24,)
            pred_vol_arr = pred_vol.squeeze(0).cpu().numpy()  # (24,)
            
            # 反标准化所有24小时的预测
            occ_np_original, vol_np_original, _, _, _ = self._get_numeric_arrays()
            occ_preds = []
            vol_preds = []
            
            for hour_idx in range(min(predict_hours, len(pred_occ_arr))):
                pred_occ_val = float(pred_occ_arr[hour_idx])
                pred_vol_val = float(pred_vol_arr[hour_idx])
                
                # 反标准化
                if self.scalers is not None and isinstance(self.scalers, dict):
                    try:
                        occ_scaler = self.scalers.get('occ')  # ⭐ 注意：训练时用的key是'occ'不是'occupancy'
                        vol_scaler = self.scalers.get('vol')
                        if occ_scaler is not None:
                            pred_occ_val = self._inverse_scale_single(pred_occ_val, occ_scaler, region_index, occ_np_original)
                        else:
                            pred_occ_val = self._inverse_scale_single(pred_occ_val, None, region_index, occ_np_original)
                        if vol_scaler is not None:
                            pred_vol_val = self._inverse_scale_single(pred_vol_val, vol_scaler, region_index, vol_np_original)
                        else:
                            pred_vol_val = self._inverse_scale_single(pred_vol_val, None, region_index, vol_np_original)
                    except Exception as e:
                        print(f"反标准化失败: {e}")
                        pred_occ_val = self._inverse_scale_single(pred_occ_val, None, region_index, occ_np_original)
                        pred_vol_val = self._inverse_scale_single(pred_vol_val, None, region_index, vol_np_original)
                else:
                    # 无scaler，使用数据统计量反标准化
                    pred_occ_val = self._inverse_scale_single(pred_occ_val, None, region_index, occ_np_original)
                    pred_vol_val = self._inverse_scale_single(pred_vol_val, None, region_index, vol_np_original)
                
                # 将占用率限制到[0,100]
                pred_occ_val = max(0.0, min(100.0, pred_occ_val))
                pred_vol_val = max(0.0, pred_vol_val)
                
                occ_preds.append(round(pred_occ_val, 2))
                vol_preds.append(round(pred_vol_val, 2))

            current_time = datetime.now()
            future_times = [current_time + timedelta(hours=i) for i in range(predict_hours)]
            timestamps = [t.strftime('%Y-%m-%d %H:%M:%S') for t in future_times]

            return {
                'region_id': region_id,
                'predict_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'predictions': {
                    'occupancy': occ_preds,
                    'volume': vol_preds,
                    'timestamps': timestamps
                }
            }

        except Exception as e:
            print(f"预测区域{region_id}失败: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"预测失败: {e}")
    
    def _predict_with_model(self, region_id: int, predict_hours: int, current_time: datetime) -> Dict:
        # 已由 predict_region 实现滚动预测，此函数保留兼容性
        return self.predict_region(region_id, predict_hours)
    

    def predict_all_regions(self) -> List[Dict]:
        """
        使用已训练模型预测所有275个区域的下一时刻占用率
        """
        print(f"\n开始预测所有区域...")

        if not self.data_loaded:
            print("数据未加载，无法进行预测")
            raise RuntimeError("数据未加载，请先上传训练数据")

        if self.model is None:
            print("模型未加载，无法进行预测")
            raise RuntimeError("模型未加载，请先训练模型")

        start_time = time.time()
        predictions = []
        total_regions = 275

        print("使用已加载的数据和模型进行预测...")

        # 列索引映射
        occ_cols = [c for c in self.occupancy_data.columns if c != 'time']

        for i in range(total_regions):
            region_id = 1000 + i

            try:
                # 找到列索引 - 修复列名映射问题
                region_index = None
                
                # 首先尝试直接匹配 region_id
                if str(region_id) in occ_cols:
                    region_index = occ_cols.index(str(region_id))
                # 然后尝试 region_ 前缀格式
                elif f"region_{region_id}" in occ_cols:
                    region_index = occ_cols.index(f"region_{region_id}")
                # 最后尝试按顺序映射（因为数据中的列名是102, 104, 105等）
                else:
                    # 数据中的列名是102, 104, 105等，需要找到对应的索引
                    if i < len(occ_cols):
                        region_index = i
                    else:
                        print(f"区域 {region_id} 超出数据范围，跳过")
                        continue
                
                if region_index is None:
                    print(f"区域 {region_id} 找不到对应的列，跳过")
                    continue

                x = self._build_input_sequence(region_index)
                if x is None:
                    raise RuntimeError("历史窗口不足")
                self.model.to(self.device)
                import torch
                with torch.no_grad():
                    pred_occ, pred_vol = self.model(x.to(self.device))
                
                # ⭐ 模型输出 (1, 24)，取第一个时间步作为当前预测
                pred_occ_val = float(pred_occ.squeeze(0)[0].cpu().numpy())
                pred_vol_val = float(pred_vol.squeeze(0)[0].cpu().numpy())
                
                # 反标准化
                occ_np_original, vol_np_original, _, _, _ = self._get_numeric_arrays()
                if self.scalers is not None and isinstance(self.scalers, dict):
                    if 'occ' in self.scalers:
                        pred_occ_val = self._inverse_scale_single(pred_occ_val, self.scalers['occ'], region_index, occ_np_original)
                    else:
                        pred_occ_val = self._inverse_scale_single(pred_occ_val, None, region_index, occ_np_original)
                    if 'vol' in self.scalers:
                        pred_vol_val = self._inverse_scale_single(pred_vol_val, self.scalers['vol'], region_index, vol_np_original)
                    else:
                        pred_vol_val = self._inverse_scale_single(pred_vol_val, None, region_index, vol_np_original)
                else:
                    pred_occ_val = self._inverse_scale_single(pred_occ_val, None, region_index, occ_np_original)
                    pred_vol_val = self._inverse_scale_single(pred_vol_val, None, region_index, vol_np_original)
                
                pred_occ_val = max(0.0, min(100.0, pred_occ_val))
                pred_vol_val = max(0.0, pred_vol_val)

                predictions.append({
                    'region_id': region_id,
                    'current_occupancy': round(pred_occ_val, 2),
                    'current_volume': round(pred_vol_val, 2),
                    'prediction_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

            except Exception as e:
                print(f"预测区域 {region_id} 失败: {e}")
                # 容错：继续其他区域，避免整体失败
                continue

            if (i + 1) % 50 == 0:
                print(f"  已预测 {i + 1}/{total_regions} 个区域...")

        elapsed = time.time() - start_time
        print(f"完成所有区域预测，耗时 {elapsed:.2f} 秒\n")

        return predictions


# ============================================
# 测试代码
# ============================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("测试区域预测器")
    print("="*60)
    
    # 初始化预测器
    predictor = RegionPredictor()
    
    # 尝试加载数据
    predictor.load_data()
    
    # 测试单个区域预测
    print("\n📊 测试单个区域预测...")
    result = predictor.predict_region(region_id=1066)
    print(f"区域ID: {result['region_id']}")
    print(f"占用率范围: {min(result['predictions']['occupancy'])}% - {max(result['predictions']['occupancy'])}%")
    
    # 测试所有区域预测
    print("\n📊 测试所有区域预测...")
    all_predictions = predictor.predict_all_regions()
    occupancies = [p['current_occupancy'] for p in all_predictions]
    print(f"占用率范围: {min(occupancies):.2f}% - {max(occupancies):.2f}%")
    
    print("\n" + "="*60)