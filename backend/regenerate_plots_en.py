#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenerate High-Performance TFT Model Evaluation Plots
- Training history (4-panel plot)
- Prediction scatter plots
- English version (no Chinese font issues)
"""

import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

import torch
from torch.utils.data import Dataset, DataLoader

# Use default font (no Chinese)
plt.rcParams['axes.unicode_minus'] = False
sns.set_style('whitegrid')

print("="*80)
print("Regenerate High-Performance TFT Model Evaluation Plots")
print("="*80)


# ============================================================================
# Dataset Class
# ============================================================================

class ChargingStationDataset(Dataset):
    """Charging Station Dataset - Keep full region information"""
    
    def __init__(self, occupancy_data, volume_data, weather_data, price_data, 
                 lookback=48, horizon=24):
        self.occupancy = torch.FloatTensor(occupancy_data)
        self.volume = torch.FloatTensor(volume_data)
        self.weather = torch.FloatTensor(weather_data)
        self.price = torch.FloatTensor(price_data)
        
        self.lookback = lookback
        self.horizon = horizon
        self.n_regions = occupancy_data.shape[1]
        
        self.n_samples = len(occupancy_data) - lookback - horizon + 1
        
    def __len__(self):
        return self.n_samples
    
    def __getitem__(self, idx):
        hist_occ = self.occupancy[idx:idx+self.lookback]
        hist_vol = self.volume[idx:idx+self.lookback]
        hist_weather = self.weather[idx:idx+self.lookback]
        hist_price = self.price[idx:idx+self.lookback]
        
        future_occ = self.occupancy[idx+self.lookback:idx+self.lookback+self.horizon]
        future_vol = self.volume[idx+self.lookback:idx+self.lookback+self.horizon]
        
        hist_features = torch.cat([
            hist_occ,
            hist_vol,
            hist_weather,
            hist_price
        ], dim=-1)
        
        return {
            'history': hist_features,
            'target_occ': future_occ,
            'target_vol': future_vol
        }


# ============================================================================
# Load Model and Data
# ============================================================================

def load_model_and_data():
    """Load trained model and data"""
    
    print("\n[1/4] Loading model and training history...")
    
    # Load model package
    model_path = 'models/tft_high_performance.pkl'
    if not os.path.exists(model_path):
        print(f"Error: Model file not found: {model_path}")
        print("Please run train_tft_high_performance.py first")
        return None
    
    with open(model_path, 'rb') as f:
        model_package = pickle.load(f)
    
    config = model_package['config']
    scalers = model_package['scalers']
    training_history = model_package['training_history']
    
    print(f"  Model loaded successfully")
    print(f"  Best Epoch: {training_history['best_epoch']}")
    print(f"  Best Val Loss: {training_history['best_val_loss']:.6f}")
    
    # Load data
    print("\n[2/4] Loading data...")
    
    from sklearn.preprocessing import RobustScaler, StandardScaler
    
    occupancy_df = pd.read_csv('data/occupancy.csv', index_col=0)
    volume_df = pd.read_csv('data/volume.csv', index_col=0)
    weather_df = pd.read_csv('data/weather_central.csv', index_col=0)
    price_df = pd.read_csv('data/e_price.csv', index_col=0)
    
    occupancy_data = occupancy_df.values
    volume_data = volume_df.values
    weather_data = weather_df.values
    price_data = price_df.values
    
    # Scale data
    occupancy_scaled = scalers['occ'].transform(occupancy_data)
    volume_scaled = scalers['vol'].transform(volume_data)
    weather_scaled = scalers['weather'].transform(weather_data)
    price_scaled = scalers['price'].transform(price_data)
    
    occupancy_scaled = np.clip(occupancy_scaled, 0, 1)
    volume_scaled = np.maximum(volume_scaled, 0)
    
    # ⚠️ CRITICAL: Create full dataset first, then split (must match training logic!)
    # This ensures we get 642 test samples (15,408 points), not 582 samples (13,968 points)
    full_dataset = ChargingStationDataset(
        occupancy_scaled, volume_scaled, weather_scaled, price_scaled,
        lookback=config['lookback'],
        horizon=config['horizon']
    )
    
    # Split dataset (same as training script)
    train_size = int(config['train_ratio'] * len(full_dataset))
    val_size = int(config['val_ratio'] * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size
    
    # Extract test dataset using random_split with SAME seed as training
    import torch.utils.data
    _, _, test_dataset = torch.utils.data.random_split(
        full_dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(config['seed'])
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=config['batch_size'],
        shuffle=False,
        num_workers=0
    )
    
    print(f"  Data loaded successfully")
    print(f"  Test samples: {len(test_dataset)}")
    
    # Reload model
    from train_tft_high_performance import HighPerformanceTFT
    
    n_regions = occupancy_data.shape[1]
    input_size = n_regions * 2 + weather_data.shape[1] + price_data.shape[1]
    
    model = HighPerformanceTFT(
        input_size=input_size,
        hidden_size=config['hidden_size'],
        lstm_layers=config['lstm_layers'],
        num_heads=config['num_heads'],
        dropout=config['dropout'],
        horizon=config['horizon']
    )
    
    model.load_state_dict(model_package['model_state_dict'])
    model.eval()
    
    device = torch.device('cpu')
    model = model.to(device)
    
    return {
        'model': model,
        'device': device,
        'test_loader': test_loader,
        'training_history': training_history,
        'config': config
    }


# ============================================================================
# Evaluate Model
# ============================================================================

def evaluate_model(data_dict):
    """Evaluate model on test set"""
    
    print("\n[3/4] Evaluating model...")
    
    model = data_dict['model']
    device = data_dict['device']
    test_loader = data_dict['test_loader']
    
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
    
    # Calculate metrics
    r2_occ = r2_score(all_true_occ, all_pred_occ)
    r2_vol = r2_score(all_true_vol, all_pred_vol)
    mae_occ = mean_absolute_error(all_true_occ, all_pred_occ)
    mae_vol = mean_absolute_error(all_true_vol, all_pred_vol)
    rmse_occ = np.sqrt(mean_squared_error(all_true_occ, all_pred_occ))
    rmse_vol = np.sqrt(mean_squared_error(all_true_vol, all_pred_vol))
    
    print(f"  Evaluation completed")
    print(f"\n  [Occupancy] R2={r2_occ:.4f}, MAE={mae_occ:.4f}, RMSE={rmse_occ:.4f}")
    print(f"  [Volume]    R2={r2_vol:.4f}, MAE={mae_vol:.4f}, RMSE={rmse_vol:.4f}")
    
    return {
        'occ': {
            'r2': r2_occ,
            'mae': mae_occ,
            'rmse': rmse_occ,
            'predictions': all_pred_occ,
            'targets': all_true_occ
        },
        'vol': {
            'r2': r2_vol,
            'mae': mae_vol,
            'rmse': rmse_vol,
            'predictions': all_pred_vol,
            'targets': all_true_vol
        }
    }


# ============================================================================
# Generate Plots
# ============================================================================

def plot_training_history(training_history, save_path='models/training_progress_hp.png'):
    """Plot training history (4-panel)"""
    
    print("\n[4/4] Generating plots...")
    print("  - Training history (4-panel)...")
    
    train_losses = np.array(training_history['train_loss']).flatten()
    val_losses = np.array(training_history['val_loss']).flatten()
    train_maes = np.array(training_history['train_mae']).flatten()
    val_maes = np.array(training_history['val_mae']).flatten()
    learning_rates = training_history['learning_rates']
    best_epoch = training_history['best_epoch']
    
    epochs = np.arange(1, len(train_losses) + 1)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('TFT Model Training History', fontsize=16, fontweight='bold')
    
    # (a) Training and Validation Loss
    ax = axes[0, 0]
    ax.plot(epochs, train_losses, label='Train', color='#1f77b4', linewidth=2)
    ax.plot(epochs, val_losses, label='Validation', color='#ff7f0e', linewidth=2)
    ax.axvline(best_epoch, color='red', linestyle='--', label=f'Best={best_epoch}')
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('Loss/MSE', fontsize=12)
    ax.set_title('(a) Training and Validation Loss', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (b) Mean Absolute Error
    ax = axes[0, 1]
    ax.plot(epochs, train_maes, label='Train', color='#1f77b4', linewidth=2)
    ax.plot(epochs, val_maes, label='Validation', color='#ff7f0e', linewidth=2)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('MAE', fontsize=12)
    ax.set_title('(b) Mean Absolute Error', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (c) Loss Improvement
    ax = axes[1, 0]
    initial_val_loss = float(val_losses[0])
    improvement = np.array([(initial_val_loss - float(loss)) / initial_val_loss * 100 
                           for loss in val_losses])
    ax.plot(epochs, improvement, color='#2ca02c', linewidth=2, label='Improvement Rate')
    ax.bar(epochs, improvement, alpha=0.2, color='purple', width=1.0)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('Improvement (%)', fontsize=12)
    ax.set_title('(c) Loss Improvement Rate', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (d) Learning Rate Schedule
    ax = axes[1, 1]
    ax.plot(epochs, learning_rates, color='purple', linewidth=2)
    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('Learning Rate', fontsize=12)
    ax.set_title('(d) Learning Rate Schedule', fontsize=13, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"    Saved: {save_path}")
    plt.close()


def plot_scatter(results, save_path='models/scatter_plots_hp.png'):
    """Plot prediction scatter plots"""
    
    print("  - Prediction scatter plots...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Occupancy scatter plot
    occ_targets = np.array(results['occ']['targets'])
    occ_preds = np.array(results['occ']['predictions'])
    occ_r2 = results['occ']['r2']
    occ_mae = results['occ']['mae']
    occ_rmse = results['occ']['rmse']
    
    # Sample if too many points
    n_samples = len(occ_targets)
    if n_samples > 20000:
        indices = np.random.choice(n_samples, 20000, replace=False)
        occ_targets_plot = occ_targets[indices]
        occ_preds_plot = occ_preds[indices]
    else:
        occ_targets_plot = occ_targets
        occ_preds_plot = occ_preds
    
    axes[0].scatter(occ_targets_plot, occ_preds_plot, alpha=0.3, s=10, color='#1f77b4', label='Test samples')
    
    # Fit line
    z = np.polyfit(occ_targets, occ_preds, 1)
    p = np.poly1d(z)
    x_line = np.linspace(occ_targets.min(), occ_targets.max(), 100)
    axes[0].plot(x_line, p(x_line), 'r--', linewidth=2, label=f'Fit: y={z[0]:.2f}x+{z[1]:.3f}')
    
    # Ideal line (adjusted range)
    min_val = min(occ_targets.min(), occ_preds.min())
    max_val = max(occ_targets.max(), occ_preds.max())
    axes[0].plot([min_val, max_val], [min_val, max_val], 'g-', linewidth=1.5, alpha=0.7, label='Ideal prediction')
    
    # Auto-adjust axis limits with padding
    padding = (max_val - min_val) * 0.05
    axes[0].set_xlim(min_val - padding, max_val + padding)
    axes[0].set_ylim(min_val - padding, max_val + padding)
    
    axes[0].set_xlabel('True Occupancy Rate', fontsize=12)
    axes[0].set_ylabel('Predicted Occupancy Rate', fontsize=12)
    axes[0].set_title('Occupancy Rate Prediction', fontsize=14, fontweight='bold')
    axes[0].legend(loc='upper left', fontsize=10)
    axes[0].grid(True, alpha=0.3)
    
    # Metrics box (with sample count)
    textstr = f'R² = {occ_r2:.4f}\nMAE = {occ_mae:.4f}\nRMSE = {occ_rmse:.4f}\nN = {n_samples:,}'
    props = dict(boxstyle='round', facecolor='lightgreen', alpha=0.8)
    axes[0].text(0.95, 0.05, textstr, transform=axes[0].transAxes, fontsize=11,
                verticalalignment='bottom', horizontalalignment='right', bbox=props)
    
    # Volume scatter plot
    vol_targets = np.array(results['vol']['targets'])
    vol_preds = np.array(results['vol']['predictions'])
    vol_r2 = results['vol']['r2']
    vol_mae = results['vol']['mae']
    vol_rmse = results['vol']['rmse']
    
    if n_samples > 20000:
        vol_targets_plot = vol_targets[indices]
        vol_preds_plot = vol_preds[indices]
    else:
        vol_targets_plot = vol_targets
        vol_preds_plot = vol_preds
    
    axes[1].scatter(vol_targets_plot, vol_preds_plot, alpha=0.3, s=10, color='#ff7f0e', label='Test samples')
    
    # Fit line
    z = np.polyfit(vol_targets, vol_preds, 1)
    p = np.poly1d(z)
    x_line = np.linspace(vol_targets.min(), vol_targets.max(), 100)
    axes[1].plot(x_line, p(x_line), 'r--', linewidth=2, label=f'Fit: y={z[0]:.2f}x+{z[1]:.2f}')
    
    # Ideal line (adjusted range)
    min_val_v = min(vol_targets.min(), vol_preds.min())
    max_val_v = max(vol_targets.max(), vol_preds.max())
    axes[1].plot([min_val_v, max_val_v], [min_val_v, max_val_v], 'g-', linewidth=1.5, alpha=0.7, label='Ideal prediction')
    
    # Auto-adjust axis limits with padding
    padding_v = (max_val_v - min_val_v) * 0.05
    axes[1].set_xlim(min_val_v - padding_v, max_val_v + padding_v)
    axes[1].set_ylim(min_val_v - padding_v, max_val_v + padding_v)
    
    axes[1].set_xlabel('True Volume Load (kWh)', fontsize=12)
    axes[1].set_ylabel('Predicted Volume Load (kWh)', fontsize=12)
    axes[1].set_title('Volume Load Prediction', fontsize=14, fontweight='bold')
    axes[1].legend(loc='upper left', fontsize=10)
    axes[1].grid(True, alpha=0.3)
    
    # Metrics box (with sample count)
    textstr = f'R² = {vol_r2:.4f}\nMAE = {vol_mae:.4f}\nRMSE = {vol_rmse:.4f}\nN = {n_samples:,}'
    props = dict(boxstyle='round', facecolor='lightyellow', alpha=0.8)
    axes[1].text(0.95, 0.05, textstr, transform=axes[1].transAxes, fontsize=11,
                verticalalignment='bottom', horizontalalignment='right', bbox=props)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"    Saved: {save_path}")
    plt.close()


# ============================================================================
# Main Function
# ============================================================================

def main():
    """Main process"""
    
    # Load model and data
    data_dict = load_model_and_data()
    if data_dict is None:
        return
    
    # Evaluate model
    results = evaluate_model(data_dict)
    
    # Generate plots
    plot_training_history(data_dict['training_history'])
    plot_scatter(results)
    
    print("\n" + "="*80)
    print("Plot generation completed!")
    print("="*80)
    print("\nGenerated files:")
    print("  - models/training_progress_hp.png  (Training history)")
    print("  - models/scatter_plots_hp.png      (Prediction scatter plots)")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()

