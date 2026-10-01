import os
import pandas as pd
import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

def generate_factory_data():
    real_now = pd.Timestamp.now().floor('s')
    start_time = real_now - pd.Timedelta(days=7)
    
    line_types = {1: "MIXING", 2: "PACKAGING", 3: "FILLING", 4: "SEALING", 5: "PALLETIZING"}
    skus = ["SKU-100", "SKU-500", "SKU-899"]
    
    it_records = []
    ot_dfs = []
    
    for line_num in range(1, 6):
        equipment_id = f"LINE-{line_num}-{line_types[line_num]}"
        current_time = start_time
        i = 0
        
        line_it_records = []
        while current_time < real_now:
            duration = pd.Timedelta(hours=np.random.randint(2, 6))
            end_time = min(current_time + duration, real_now)
            sku = np.random.choice(skus)
            
            line_it_records.append({
                "BATCH_ID": f"B-{1000+i}-{line_num}",
                "SKU_ID": sku,
                "EQUIPMENT_ID": equipment_id,
                "START_TIME": current_time,
                "END_TIME": end_time
            })
            current_time = end_time + pd.Timedelta(minutes=30)
            i += 1
            
        it_records.extend(line_it_records)
        line_it_df = pd.DataFrame(line_it_records)
        
        ot_times = pd.date_range(start=start_time, end=real_now, freq='min')
        ot_df = pd.DataFrame({'TIMESTAMP': ot_times})
        ot_df['EQUIPMENT_ID'] = equipment_id
        
        line_it_df = line_it_df.sort_values('START_TIME')
        ot_df = pd.merge_asof(
            ot_df, 
            line_it_df[['START_TIME', 'END_TIME', 'SKU_ID']], 
            left_on='TIMESTAMP', 
            right_on='START_TIME', 
            direction='backward'
        )
        
        is_active = (ot_df['TIMESTAMP'] >= ot_df['START_TIME']) & (ot_df['TIMESTAMP'] <= ot_df['END_TIME'])
        ot_df.loc[~is_active, 'SKU_ID'] = None
        
        base_temp = 75.0
        base_vib = 2.0
        
        n = len(ot_df)
        temps = base_temp + np.random.normal(0, 1.0, n)
        vibs = base_vib + np.random.normal(0, 0.15, n)
        
        is_sku_899 = ot_df['SKU_ID'] == 'SKU-899'
        temps = np.where(is_sku_899, base_temp * 1.15 + np.random.normal(0, 1.0, n), temps)
        vibs = np.where(is_sku_899, base_vib * 1.20 + np.random.normal(0, 0.15, n), vibs)
        
        hours_from_end = (real_now - ot_df['TIMESTAMP']).dt.total_seconds() / 3600.0
        degradation_window = 120.0
        in_window = hours_from_end < degradation_window
        
        progress = 1.0 - (hours_from_end[in_window] / degradation_window)
        
        if line_num == 1:
            temps[in_window] += progress * 14.4
            vibs[in_window] += progress * 0.288
        elif line_num == 2:
            temps[in_window] += progress * 13.0
            vibs[in_window] += progress * 0.260
        elif line_num == 3:
            temps[in_window] += progress * 11.6
            vibs[in_window] += progress * 0.232
            
        ot_df['TEMPERATURE_C'] = np.round(temps, 2)
        ot_df['VIBRATION_RMS'] = np.round(vibs, 2)
        
        ot_dfs.append(ot_df[['TIMESTAMP', 'EQUIPMENT_ID', 'TEMPERATURE_C', 'VIBRATION_RMS']])
        
    it_df = pd.DataFrame(it_records)
    ot_df = pd.concat(ot_dfs, ignore_index=True)
    
    it_path = os.path.join(PROJECT_ROOT, "it_batch_schedule.csv")
    ot_path = os.path.join(PROJECT_ROOT, "ot_telemetry_stream.csv")
    
    it_df.to_csv(it_path, index=False)
    ot_df.to_csv(ot_path, index=False)
    print(f"Generated {len(it_df)} IT records and {len(ot_df)} OT records.")
    print(f"  IT  -> {it_path}")
    print(f"  OT  -> {ot_path}")
    return it_path, ot_path

if __name__ == "__main__":
    generate_factory_data()
