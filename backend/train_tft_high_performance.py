#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能TFT模型训练 - 结合成功的数据处理方式与真TFT架构
- 保留完整区域矩阵（不按区域分离）
- 使用RobustScaler + HuberLoss
- 包含LSTM、GRN、变量选择、自注意力等TFT核心组件
- 目标：达到R²>0.90的性能
"""

import os
import json
import time
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style('whitegrid')

print("="*80)
print("高性能TFT模型训练 - 充电桩占用率与电量负荷双目标预测")
print("="*80)


# ============================================================================
# 1. 配置参数
# ============================================================================

CONFIG = {
    # 数据参数
    'lookback': 48,
    'horizon': 24,
    'train_ratio': 0.7,
    'val_ratio': 0.15,
    'test_ratio': 0.15,
    
    # TFT模型参数（优化版）
    'hidden_size': 256,
    'lstm_layers': 3,
    'num_heads': 8,
    'dropout': 0.15,
    
    # 训练参数（延长到200轮）
    'batch_size': 64,
    'learning_rate': 0.0005,
    'n_epochs': 200,          # 150 -> 200，更充分训练
    'patience': 25,           # 20 -> 25，给更多收敛时间
    'min_delta': 5e-5,
    'weight_decay': 5e-5,
    'grad_clip': 1.0,
    
    # 学习率调度
    'use_scheduler': True,
    'scheduler_patience': 10,  # 8 -> 10，更平缓的学习率衰减
    'scheduler_factor': 0.5,
    
    # 损失权重
    'loss_weight_occ': 1.0,
    'loss_weight_vol': 1.0,
    
    # 其他
    'seed': 42,
    'device': 'cuda' if torch.cuda.is_available() else 'cpu',
    'save_interval': 20,
}


# ============================================================================
# 2. 数据集类（保留完整区域矩阵）
# ============================================================================

class ChargingStationDataset(Dataset):
    """充电站数据集 - 保留完整区域信息"""
    
    def __init__(self, occupancy_data, volume_data, weather_data, price_data, 
                 lookback=48, horizon=24):
        """
        Args:
            occupancy_data: 占用率数据 (timesteps, regions)
            volume_data: 电量负荷数据 (timesteps, regions)
            weather_data: 天气数据 (timesteps, weather_features)
            price_data: 电价数据 (timesteps, 1)
        """
        self.occupancy = torch.FloatTensor(occupancy_data)
        self.volume = torch.FloatTensor(volume_data)
        self.weather = torch.FloatTensor(weather_data)
        self.price = torch.FloatTensor(price_data)
        
        self.lookback = lookback
        self.horizon = horizon
        self.n_regions = occupancy_data.shape[1]
        
        self.n_samples = len(occupancy_data) - lookback - horizon + 1
        
        if self.n_samples <= 0:
            raise ValueError(f"数据不足: 需要至少 {lookback + horizon} 个时间步")
        
    def __len__(self):
        return self.n_samples
    
    def __getitem__(self, idx):
        # 历史数据（保留所有区域）
        hist_occ = self.occupancy[idx:idx+self.lookback]      # (lookback, regions)
        hist_vol = self.volume[idx:idx+self.lookback]          # (lookback, regions)
        hist_weather = self.weather[idx:idx+self.lookback]    # (lookback, weather_features)
        hist_price = self.price[idx:idx+self.lookback]        # (lookback, 1)
        
        # 未来目标（保留所有区域）
        future_occ = self.occupancy[idx+self.lookback:idx+self.lookback+self.horizon]
        future_vol = self.volume[idx+self.lookback:idx+self.lookback+self.horizon]
        
        # 拼接特征: [occ, vol, weather, price]
        hist_features = torch.cat([
            hist_occ,       # (lookback, regions)
            hist_vol,       # (lookback, regions)
            hist_weather,   # (lookback, weather_features)
            hist_price      # (lookback, 1)
        ], dim=-1)
        
        return {
            'history': hist_features,
            'target_occ': future_occ,
            'target_vol': future_vol
        }


# ============================================================================
# 3. TFT核心组件
# ============================================================================

class GatedResidualNetwork(nn.Module):
    """门控残差网络"""
    
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
        # 残差连接
        if self.skip_fc is not None:
            residual = self.skip_fc(x)
        else:
            residual = x
        
        # 主要路径
        x = self.fc1(x)
        x = self.elu(x)
        x = self.fc2(x)
        x = self.dropout(x)
        
        # 投影到输出维度
        x_out = self.output_fc(x)
        
        # 门控机制
        gate = torch.sigmoid(self.gate_fc(x))
        
        # GLU + 残差
        x = x_out * gate
        x = self.gate_norm(x + residual)
        
        return x


class PositionalEncoding(nn.Module):
    """位置编码"""
    
    def __init__(self, d_model, max_len=5000):
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


# ============================================================================
# 4. 高性能TFT模型
# ============================================================================

class HighPerformanceTFT(nn.Module):
    """高性能TFT模型 - 结合成功经验与TFT架构"""
    
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
        
        # 权重初始化
        self._init_weights()
    
    def _init_weights(self):
        """Xavier初始化"""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
    
    def forward(self, x):
        """
        Args:
            x: (batch, lookback, input_size)
        Returns:
            occ_pred: (batch, horizon)
            vol_pred: (batch, horizon)
        """
        # 1. 输入投影 + GRN
        embedded = self.input_grn(x)  # (batch, lookback, hidden_size)
        
        # 2. 位置编码
        embedded = self.pos_encoder(embedded)
        
        # 3. LSTM编码
        lstm_out, (h_n, c_n) = self.lstm(embedded)  # (batch, lookback, hidden_size)
        
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
        context = context.squeeze(1)  # (batch, hidden_size)
        
        # 8. 双头预测
        occ_pred = self.occ_head(context)  # (batch, horizon)
        vol_pred = self.vol_head(context)  # (batch, horizon)
        
        return occ_pred, vol_pred


# ============================================================================
# 5. 训练器
# ============================================================================

class TFTTrainer:
    """TFT训练器"""
    
    def __init__(self, model, device, config):
        self.model = model
        self.device = device
        self.config = config
        
        # 优化器
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=config['learning_rate'],
            weight_decay=config['weight_decay']
        )
        
        # 学习率调度器
        if config['use_scheduler']:
            self.scheduler = ReduceLROnPlateau(
                self.optimizer,
                mode='min',
                factor=config['scheduler_factor'],
                patience=config['scheduler_patience'],
                verbose=True
            )
        else:
            self.scheduler = None
        
        # 损失函数（使用Huber Loss对异常值鲁棒）
        self.huber_loss = nn.SmoothL1Loss()
        self.mae_loss = nn.L1Loss()
        
        # 记录
        self.train_losses = []
        self.val_losses = []
        self.train_maes = []
        self.val_maes = []
        self.learning_rates = []
        
        self.best_val_loss = float('inf')
        self.best_epoch = 0
        self.epochs_no_improve = 0
    
    def train_epoch(self, train_loader):
        """训练一个epoch"""
        self.model.train()
        total_loss = 0
        total_mae_occ = 0
        total_mae_vol = 0
        n_batches = 0
        
        for batch in train_loader:
            history = batch['history'].to(self.device)
            target_occ = batch['target_occ'].to(self.device)
            target_vol = batch['target_vol'].to(self.device)
            
            # 前向传播
            pred_occ, pred_vol = self.model(history)
            
            # 计算损失（对所有区域求均值）
            target_occ_mean = target_occ.mean(dim=-1)  # (batch, horizon)
            target_vol_mean = target_vol.mean(dim=-1)
            
            # 使用Huber损失
            loss_occ = self.huber_loss(pred_occ, target_occ_mean) * self.config['loss_weight_occ']
            loss_vol = self.huber_loss(pred_vol, target_vol_mean) * self.config['loss_weight_vol']
            loss = loss_occ + loss_vol
            
            # 反向传播
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config['grad_clip'])
            self.optimizer.step()
            
            # 计算MAE
            with torch.no_grad():
                mae_occ = self.mae_loss(pred_occ, target_occ_mean)
                mae_vol = self.mae_loss(pred_vol, target_vol_mean)
            
            total_loss += loss.item()
            total_mae_occ += mae_occ.item()
            total_mae_vol += mae_vol.item()
            n_batches += 1
        
        avg_loss = total_loss / n_batches
        avg_mae = (total_mae_occ + total_mae_vol) / (2 * n_batches)
        
        return avg_loss, avg_mae
    
    def validate(self, val_loader):
        """验证"""
        self.model.eval()
        total_loss = 0
        total_mae_occ = 0
        total_mae_vol = 0
        n_batches = 0
        
        with torch.no_grad():
            for batch in val_loader:
                history = batch['history'].to(self.device)
                target_occ = batch['target_occ'].to(self.device)
                target_vol = batch['target_vol'].to(self.device)
                
                pred_occ, pred_vol = self.model(history)
                
                target_occ_mean = target_occ.mean(dim=-1)
                target_vol_mean = target_vol.mean(dim=-1)
                
                loss_occ = self.huber_loss(pred_occ, target_occ_mean) * self.config['loss_weight_occ']
                loss_vol = self.huber_loss(pred_vol, target_vol_mean) * self.config['loss_weight_vol']
                loss = loss_occ + loss_vol
                
                mae_occ = self.mae_loss(pred_occ, target_occ_mean)
                mae_vol = self.mae_loss(pred_vol, target_vol_mean)
                
                total_loss += loss.item()
                total_mae_occ += mae_occ.item()
                total_mae_vol += mae_vol.item()
                n_batches += 1
        
        avg_loss = total_loss / n_batches
        avg_mae = (total_mae_occ + total_mae_vol) / (2 * n_batches)
        
        return avg_loss, avg_mae
    
    def train(self, train_loader, val_loader, save_dir='models'):
        """完整训练流程"""
        os.makedirs(save_dir, exist_ok=True)
        
        print(f"\n{'='*80}")
        print(f"开始训练 - 共 {self.config['n_epochs']} 轮")
        print(f"早停耐心值: {self.config['patience']}")
        print(f"{'='*80}\n")
        
        start_time = time.time()
        
        for epoch in range(1, self.config['n_epochs'] + 1):
            epoch_start = time.time()
            
            # 训练
            train_loss, train_mae = self.train_epoch(train_loader)
            
            # 验证
            val_loss, val_mae = self.validate(val_loader)
            
            # 记录
            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.train_maes.append(train_mae)
            self.val_maes.append(val_mae)
            
            current_lr = self.optimizer.param_groups[0]['lr']
            self.learning_rates.append(current_lr)
            
            # 学习率调度
            if self.scheduler is not None:
                self.scheduler.step(val_loss)
            
            epoch_time = time.time() - epoch_start
            
            # 打印进度
            print(f"Epoch {epoch:3d}/{self.config['n_epochs']} | "
                  f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
                  f"Train MAE: {train_mae:.4f} | Val MAE: {val_mae:.4f} | "
                  f"LR: {current_lr:.6f} | Time: {epoch_time:.1f}s")
            
            # 保存最佳模型
            if val_loss < self.best_val_loss - self.config['min_delta']:
                self.best_val_loss = val_loss
                self.best_epoch = epoch
                self.epochs_no_improve = 0
                torch.save(self.model.state_dict(), os.path.join(save_dir, 'best_tft_hp.pth'))
                print(f"  >> 保存最佳模型 (Epoch {epoch}, val_loss: {val_loss:.4f})")
            else:
                self.epochs_no_improve += 1
            
            # 早停检查
            if self.epochs_no_improve >= self.config['patience']:
                print(f"\n早停触发！已连续 {self.config['patience']} 轮无改进")
                print(f"最佳模型来自 Epoch {self.best_epoch} (val_loss: {self.best_val_loss:.4f})")
                break
            
            # 定期保存检查点
            if epoch % self.config['save_interval'] == 0:
                torch.save(self.model.state_dict(), 
                          os.path.join(save_dir, f'checkpoint_hp_epoch_{epoch}.pth'))
                print(f"  >> 保存检查点 (Epoch {epoch})")
        
        total_time = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"训练完成！总用时: {total_time/60:.1f} 分钟")
        print(f"最佳验证损失: {self.best_val_loss:.4f} (Epoch {self.best_epoch})")
        print(f"{'='*80}\n")


# ============================================================================
# 6. 数据加载与预处理
# ============================================================================

def load_and_prepare_data(config):
    """加载并预处理数据"""
    print("\n[1/7] 加载数据...")
    
    occupancy_df = pd.read_csv('data/occupancy.csv', index_col=0)
    volume_df = pd.read_csv('data/volume.csv', index_col=0)
    weather_df = pd.read_csv('data/weather_central.csv', index_col=0)
    price_df = pd.read_csv('data/e_price.csv', index_col=0)
    
    print(f"  >> 占用率: {occupancy_df.shape}")
    print(f"  >> 电量负荷: {volume_df.shape}")
    print(f"  >> 天气: {weather_df.shape}")
    print(f"  >> 电价: {price_df.shape}")
    
    occupancy_data = occupancy_df.values
    volume_data = volume_df.values
    weather_data = weather_df.values
    price_data = price_df.values
    
    # 使用RobustScaler（对异常值鲁棒）
    print("\n[2/7] 数据标准化（RobustScaler）...")
    
    occ_scaler = RobustScaler()
    vol_scaler = RobustScaler()
    weather_scaler = StandardScaler()
    price_scaler = StandardScaler()
    
    occupancy_scaled = occ_scaler.fit_transform(occupancy_data)
    volume_scaled = vol_scaler.fit_transform(volume_data)
    weather_scaled = weather_scaler.fit_transform(weather_data)
    price_scaled = price_scaler.fit_transform(price_data)
    
    # 占用率限制在[0,1]，负荷限制在[0,+∞)
    occupancy_scaled = np.clip(occupancy_scaled, 0, 1)
    volume_scaled = np.maximum(volume_scaled, 0)
    
    print(f"  >> 标准化完成")
    print(f"  >> 占用率范围: [{occupancy_scaled.min():.3f}, {occupancy_scaled.max():.3f}]")
    print(f"  >> 电量负荷范围: [{volume_scaled.min():.3f}, {volume_scaled.max():.3f}]")
    
    return {
        'occupancy': occupancy_scaled,
        'volume': volume_scaled,
        'weather': weather_scaled,
        'price': price_scaled,
        'scalers': {
            'occ': occ_scaler,
            'vol': vol_scaler,
            'weather': weather_scaler,
            'price': price_scaler
        },
        'n_regions': occupancy_data.shape[1]
    }


# ============================================================================
# 7. 评估与可视化
# ============================================================================

def evaluate_and_visualize(trainer, test_loader, model, device, save_dir='models'):
    """评估模型并生成可视化"""
    
    print("\n[7/7] 评估模型并生成可视化...")
    
    # 评估
    model.eval()
    all_pred_occ = []
    all_true_occ = []
    all_pred_vol = []
    all_true_vol = []
    
    with torch.no_grad():
        for batch in test_loader:
            history = batch['history'].to(device)
            target_occ = batch['target_occ'].cpu().numpy()
            target_vol = batch['target_vol'].cpu().numpy()
            
            pred_occ, pred_vol = model(history)
            pred_occ = pred_occ.cpu().numpy()
            pred_vol = pred_vol.cpu().numpy()
            
            all_pred_occ.extend(pred_occ.flatten())
            all_true_occ.extend(target_occ.mean(axis=-1).flatten())
            all_pred_vol.extend(pred_vol.flatten())
            all_true_vol.extend(target_vol.mean(axis=-1).flatten())
    
    # 计算R²等指标
    r2_occ = r2_score(all_true_occ, all_pred_occ)
    r2_vol = r2_score(all_true_vol, all_pred_vol)
    mae_occ = mean_absolute_error(all_true_occ, all_pred_occ)
    mae_vol = mean_absolute_error(all_true_vol, all_pred_vol)
    rmse_occ = np.sqrt(mean_squared_error(all_true_occ, all_pred_occ))
    rmse_vol = np.sqrt(mean_squared_error(all_true_vol, all_pred_vol))
    
    # 打印结果
    print("\n" + "="*80)
    print("测试集评估结果")
    print("="*80)
    print(f"\n【占用率预测】")
    print(f"  R² (决定系数):     {r2_occ:.4f}")
    print(f"  MAE (平均绝对误差): {mae_occ:.4f}")
    print(f"  RMSE (均方根误差):  {rmse_occ:.4f}")
    print(f"\n【电量负荷预测】")
    print(f"  R² (决定系数):     {r2_vol:.4f}")
    print(f"  MAE (平均绝对误差): {mae_vol:.4f}")
    print(f"  RMSE (均方根误差):  {rmse_vol:.4f}")
    print("="*80 + "\n")
    
    # 生成训练历史图（四联图）
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('TFT模型训练历史', fontsize=16, fontweight='bold')
    
    epochs = range(1, len(trainer.train_losses) + 1)
    
    # (a) 训练和验证损失
    ax = axes[0, 0]
    ax.plot(epochs, trainer.train_losses, label='训练', color='#1f77b4', linewidth=2)
    ax.plot(epochs, trainer.val_losses, label='验证', color='#ff7f0e', linewidth=2)
    ax.axvline(trainer.best_epoch, color='red', linestyle='--', label=f'最佳={trainer.best_epoch}')
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('Loss/MSE', fontsize=12)
    ax.set_title('(a) 训练和验证损失', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (b) 平均绝对误差
    ax = axes[0, 1]
    ax.plot(epochs, trainer.train_maes, label='训练', color='#1f77b4', linewidth=2)
    ax.plot(epochs, trainer.val_maes, label='验证', color='#ff7f0e', linewidth=2)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('MAE', fontsize=12)
    ax.set_title('(b) 平均绝对误差', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (c) 损失改善率
    ax = axes[1, 0]
    initial_val_loss = float(trainer.val_losses[0])
    improvement = np.array([(initial_val_loss - float(loss)) / initial_val_loss * 100 
                           for loss in trainer.val_losses])
    epochs_arr = np.array(list(epochs))
    ax.plot(epochs_arr, improvement, color='#2ca02c', linewidth=2, label='改善率')
    ax.bar(epochs_arr, improvement, alpha=0.2, color='purple', width=1.0)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('改善率 (%)', fontsize=12)
    ax.set_title('(c) 损失改善率', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (d) 学习率调度
    ax = axes[1, 1]
    ax.plot(epochs, trainer.learning_rates, color='purple', linewidth=2)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('学习率', fontsize=12)
    ax.set_title('(d) 学习率调度', fontsize=13, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{save_dir}/training_progress_hp.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ 训练历史图: {save_dir}/training_progress_hp.png")
    plt.close()
    
    # 生成散点图
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # 占用率散点图
    axes[0].scatter(all_true_occ, all_pred_occ, alpha=0.3, s=10, color='#1f77b4', label='测试样本')
    z = np.polyfit(all_true_occ, all_pred_occ, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(all_true_occ), max(all_true_occ), 100)
    axes[0].plot(x_line, p(x_line), 'r--', linewidth=2, label=f'拟合: y={z[0]:.2f}x+{z[1]:.3f}')
    axes[0].plot([0, 1], [0, 1], 'g-', linewidth=1.5, alpha=0.7, label='理想预测')
    axes[0].set_xlabel('真实占用率 (True Occupancy Rate)', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('预测占用率 (Predicted Occupancy Rate)', fontsize=12, fontweight='bold')
    axes[0].set_title('占用率预测效果', fontsize=14, fontweight='bold')
    axes[0].legend(loc='upper left', fontsize=10)
    axes[0].grid(True, alpha=0.3)
    # 修改文本框样式：更大字体、更明显的边框、白色背景
    textstr = f'R² = {r2_occ:.4f}\nMAE = {mae_occ:.4f}\nRMSE = {rmse_occ:.4f}'
    props = dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='green', linewidth=2, alpha=0.95)
    axes[0].text(0.95, 0.05, textstr, transform=axes[0].transAxes, fontsize=13, fontweight='bold',
                verticalalignment='bottom', horizontalalignment='right', bbox=props, color='darkgreen')
    
    # 电量负荷散点图
    axes[1].scatter(all_true_vol, all_pred_vol, alpha=0.3, s=10, color='#ff7f0e', label='测试样本')
    z = np.polyfit(all_true_vol, all_pred_vol, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(all_true_vol), max(all_true_vol), 100)
    axes[1].plot(x_line, p(x_line), 'r--', linewidth=2, label=f'拟合: y={z[0]:.2f}x+{z[1]:.2f}')
    max_val = max(max(all_true_vol), max(all_pred_vol))
    axes[1].plot([0, max_val], [0, max_val], 'g-', linewidth=1.5, alpha=0.7, label='理想预测')
    axes[1].set_xlabel('真实电量负荷 (True Volume Load) kWh', fontsize=12, fontweight='bold')
    axes[1].set_ylabel('预测电量负荷 (Predicted Volume Load) kWh', fontsize=12, fontweight='bold')
    axes[1].set_title('电量负荷预测效果', fontsize=14, fontweight='bold')
    axes[1].legend(loc='upper left', fontsize=10)
    axes[1].grid(True, alpha=0.3)
    # 修改文本框样式：更大字体、更明显的边框、白色背景
    textstr = f'R² = {r2_vol:.4f}\nMAE = {mae_vol:.4f}\nRMSE = {rmse_vol:.4f}'
    props = dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='orange', linewidth=2, alpha=0.95)
    axes[1].text(0.95, 0.05, textstr, transform=axes[1].transAxes, fontsize=13, fontweight='bold',
                verticalalignment='bottom', horizontalalignment='right', bbox=props, color='darkorange')
    
    plt.tight_layout()
    plt.savefig(f'{save_dir}/scatter_plots_hp.png', dpi=300, bbox_inches='tight')
    print(f"  ✅ 散点图: {save_dir}/scatter_plots_hp.png")
    plt.close()
    
    # 保存评估结果
    results = {
        'training': {
            'best_epoch': trainer.best_epoch,
            'best_val_loss': float(trainer.best_val_loss),
            'total_epochs': len(trainer.train_losses)
        },
        'occupancy': {
            'r2': float(r2_occ),
            'mae': float(mae_occ),
            'rmse': float(rmse_occ)
        },
        'volume': {
            'r2': float(r2_vol),
            'mae': float(mae_vol),
            'rmse': float(rmse_vol)
        }
    }
    
    with open(f'{save_dir}/eval_results_hp.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ 评估结果: {save_dir}/eval_results_hp.json\n")


# ============================================================================
# 8. 主训练流程
# ============================================================================

def main():
    """主训练流程"""
    
    # 设置随机种子
    np.random.seed(CONFIG['seed'])
    torch.manual_seed(CONFIG['seed'])
    if torch.cuda.is_available():
        torch.cuda.manual_seed(CONFIG['seed'])
        torch.backends.cudnn.deterministic = True
    
    print(f"\n训练配置:")
    print(json.dumps(CONFIG, indent=2, ensure_ascii=False))
    
    # 加载数据
    data = load_and_prepare_data(CONFIG)
    
    # 创建数据集
    print("\n[3/7] 创建数据集...")
    dataset = ChargingStationDataset(
        occupancy_data=data['occupancy'],
        volume_data=data['volume'],
        weather_data=data['weather'],
        price_data=data['price'],
        lookback=CONFIG['lookback'],
        horizon=CONFIG['horizon']
    )
    
    # 划分数据集
    train_size = int(CONFIG['train_ratio'] * len(dataset))
    val_size = int(CONFIG['val_ratio'] * len(dataset))
    test_size = len(dataset) - train_size - val_size
    
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        dataset, 
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(CONFIG['seed'])
    )
    
    train_loader = DataLoader(
        train_dataset, batch_size=CONFIG['batch_size'], shuffle=True,
        num_workers=0, pin_memory=True if CONFIG['device'] == 'cuda' else False
    )
    val_loader = DataLoader(
        val_dataset, batch_size=CONFIG['batch_size'], shuffle=False,
        num_workers=0, pin_memory=True if CONFIG['device'] == 'cuda' else False
    )
    test_loader = DataLoader(
        test_dataset, batch_size=CONFIG['batch_size'], shuffle=False,
        num_workers=0, pin_memory=True if CONFIG['device'] == 'cuda' else False
    )
    
    print(f"  >> 训练集: {len(train_dataset)} 样本")
    print(f"  >> 验证集: {len(val_dataset)} 样本")
    print(f"  >> 测试集: {len(test_dataset)} 样本")
    
    # 创建模型
    print("\n[4/7] 创建高性能TFT模型...")
    input_size = data['n_regions'] * 2 + data['weather'].shape[1] + data['price'].shape[1]
    
    model = HighPerformanceTFT(
        input_size=input_size,
        hidden_size=CONFIG['hidden_size'],
        lstm_layers=CONFIG['lstm_layers'],
        num_heads=CONFIG['num_heads'],
        dropout=CONFIG['dropout'],
        horizon=CONFIG['horizon']
    )
    
    device = torch.device(CONFIG['device'])
    model = model.to(device)
    
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  >> 输入维度: {input_size}")
    print(f"  >> 模型参数量: {total_params:,}")
    print(f"  >> 设备: {device}")
    if device.type == 'cuda':
        print(f"  >> GPU: {torch.cuda.get_device_name(0)}")
    
    # 训练模型
    print("\n[5/7] 训练模型...")
    trainer = TFTTrainer(model, device, CONFIG)
    trainer.train(train_loader, val_loader)
    
    # 加载最佳模型
    print("\n[6/7] 加载最佳模型...")
    model.load_state_dict(torch.load('models/best_tft_hp.pth'))
    
    # 保存完整模型包
    model_package = {
        'model_state_dict': model.state_dict(),
        'config': CONFIG,
        'scalers': data['scalers'],
        'n_regions': data['n_regions'],
        'training_history': {
            'train_loss': trainer.train_losses,
            'val_loss': trainer.val_losses,
            'train_mae': trainer.train_maes,
            'val_mae': trainer.val_maes,
            'learning_rates': trainer.learning_rates,
            'best_epoch': trainer.best_epoch,
            'best_val_loss': trainer.best_val_loss
        }
    }
    
    with open('models/tft_high_performance.pkl', 'wb') as f:
        pickle.dump(model_package, f)
    
    print(f"  ✅ 模型已保存: models/tft_high_performance.pkl")
    
    print(f"\n{'='*80}")
    print("✅ 高性能TFT训练完成！")
    print(f"{'='*80}\n")
    
    print("训练信息:")
    print(f"  - 最佳Epoch: {trainer.best_epoch}")
    print(f"  - 最佳验证损失: {trainer.best_val_loss:.6f}")
    print(f"  - 总训练轮数: {len(trainer.train_losses)}")
    print(f"\n提示: 运行以下命令生成评估图表:")
    print(f"  python regenerate_plots_en.py")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()

