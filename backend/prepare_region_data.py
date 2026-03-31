# prepare_region_data.py
"""
生成深圳市275个交通区域数据
运行: python prepare_region_data.py
"""

import pandas as pd
import json
import os
import sys

def prepare_region_data():
    """从UrbanEV数据集准备275个区域数据"""
    
    print("="*60)
    print("🚀 开始准备区域数据")
    print("="*60)
    
    # 🎯 修改为你的数据路径
    DATA_PATH = r"C:\Users\27621\Desktop\competition\竞赛\大创\UrbanEV-main\UrbanEV-main\data"
    
    # 检查路径
    if not os.path.exists(DATA_PATH):
        print(f"❌ 数据路径不存在: {DATA_PATH}")
        print("请修改 DATA_PATH 为你的实际路径")
        return None
    
    # 1. 加载区域信息
    print("\n📂 加载区域信息...")
    inf_path = os.path.join(DATA_PATH, 'inf.csv')
    
    if not os.path.exists(inf_path):
        print(f"❌ 文件不存在: {inf_path}")
        return None
    
    inf_df = pd.read_csv(inf_path)
    print(f"✅ 加载了 {len(inf_df)} 个区域")
    print(f"   字段: {list(inf_df.columns)}")
    
    # 2. 加载占用率和负荷数据
    print("\n📂 加载占用率和负荷数据...")
    occupancy_df = pd.read_csv(os.path.join(DATA_PATH, 'occupancy.csv'))
    volume_df = pd.read_csv(os.path.join(DATA_PATH, 'volume.csv'))
    
    print(f"✅ 占用率数据: {occupancy_df.shape}")
    print(f"✅ 负荷数据: {volume_df.shape}")
    
    # 3. 构建区域数据
    print("\n🔨 构建区域数据...")
    regions = []
    
    for idx, row in inf_df.iterrows():
        region_id = int(row['TAZID'])
        region_id_str = str(region_id)
        
        # 检查该区域是否在占用率数据中
        if region_id_str in occupancy_df.columns:
            # 计算该区域的平均占用率和负荷
            avg_occupancy = occupancy_df[region_id_str].mean()
            avg_volume = volume_df[region_id_str].mean() if region_id_str in volume_df.columns else 0
            
            # 根据经纬度判断所属区域
            district = get_district_from_location(row['longitude'], row['latitude'])
            
            region = {
                'region_id': region_id,
                'name': f'深圳交通区域{region_id}',
                'longitude': float(row['longitude']),
                'latitude': float(row['latitude']),
                'charge_count': int(row['charge_count']),
                'area': float(row['area']),
                'perimeter': float(row['perimeter']),
                'district': district,
                'avg_occupancy': float(avg_occupancy),
                'avg_volume': float(avg_volume)
            }
            
            regions.append(region)
            
            # 显示前5个
            if len(regions) <= 5:
                print(f"   区域{region_id}: {district}, 位置({row['longitude']:.4f}, {row['latitude']:.4f})")
    
    print(f"\n✅ 成功构建 {len(regions)} 个区域数据")
    
    # 4. 保存为JSON
    output_file = 'shenzhen_regions_275.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(regions, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 数据已保存到: {output_file}")
    print(f"   文件大小: {os.path.getsize(output_file) / 1024:.2f} KB")
    
    # 5. 生成统计信息
    print("\n📊 数据统计:")
    print(f"   区域数量: {len(regions)}")
    print(f"   经度范围: {min(r['longitude'] for r in regions):.4f} ~ {max(r['longitude'] for r in regions):.4f}")
    print(f"   纬度范围: {min(r['latitude'] for r in regions):.4f} ~ {max(r['latitude'] for r in regions):.4f}")
    print(f"   总充电桩数: {sum(r['charge_count'] for r in regions)}")
    print(f"   平均占用率: {sum(r['avg_occupancy'] for r in regions) / len(regions):.2%}")
    
    # 6. 按区划统计
    district_count = {}
    for r in regions:
        district = r['district']
        district_count[district] = district_count.get(district, 0) + 1
    
    print(f"\n📍 各区域分布:")
    for district, count in sorted(district_count.items(), key=lambda x: x[1], reverse=True):
        print(f"   {district}: {count}个区域")
    
    print("\n" + "="*60)
    print("✅ 区域数据准备完成！")
    print("="*60)
    
    return regions

def get_district_from_location(lon, lat):
    """根据经纬度判断所属区域"""
    # 深圳市各区大致经纬度范围
    if lon < 113.88:
        return '宝安区'
    elif lon > 114.35:
        return '龙岗区'
    elif lon > 114.22 and lat > 22.7:
        return '龙华区'
    elif lon > 114.22 and lat < 22.52:
        return '盐田区'
    elif 114.05 < lon < 114.22 and lat > 22.6:
        return '福田区'
    elif 114.05 < lon < 114.22 and lat < 22.6:
        return '罗湖区'
    elif lon < 114.05 and lat > 22.52:
        return '南山区'
    elif lon > 114.35:
        return '坪山区'
    else:
        return '其他区域'

if __name__ == "__main__":
    try:
        regions = prepare_region_data()
        if regions:
            print("\n✅ 成功！可以继续后续步骤")
            print("   下一步：运行后端代码")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()