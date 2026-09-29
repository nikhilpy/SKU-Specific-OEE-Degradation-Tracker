import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Always write CSVs to the project root, regardless of CWD.
# data_generator.py lives at <root>/code/misc/data_generator.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

def generate_factory_data():
    start_time = datetime.now() - timedelta(days=7)
    current_time = start_time
    line_types = {
        1: "MIXING",
        2: "PACKAGING",
        3: "FILLING",
        4: "SEALING",
        5: "PALLETIZING"
    }
    skus = ["SKU-100", "SKU-500", "SKU-899"]
    
    it_records = []
    ot_records = []
    
    # 1. Generate IT and OT Data for 5 Lines
    for line_num in range(1, 6):
        equipment_id = f"LINE-{line_num}-{line_types[line_num]}"
        current_time = start_time
        
        # IT Batch Schedule for this line
        line_it_records = []
        for i in range(50):
            duration = timedelta(hours=np.random.randint(2, 6))
            end_time = current_time + duration
            sku = np.random.choice(skus)
            
            line_it_records.append({
                "BATCH_ID": f"B-{1000+i}-{line_num}",
                "SKU_ID": sku,
                "EQUIPMENT_ID": equipment_id,
                "START_TIME": current_time,
                "END_TIME": end_time
            })
            current_time = end_time + timedelta(minutes=30) # Machine changeover time
        
        it_records.extend(line_it_records)
        line_it_df = pd.DataFrame(line_it_records)

        # OT Telemetry Stream for this line
        ot_time = start_time
        while ot_time < current_time:
            base_temp = 75.0
            base_vib = 2.0
            
            active_batch = line_it_df[(line_it_df['START_TIME'] <= ot_time) & (line_it_df['END_TIME'] >= ot_time)]
            
            if not active_batch.empty and active_batch.iloc[0]['SKU_ID'] == "SKU-899":
                temp = base_temp * 1.15 + np.random.normal(0, 1.0)
                vib = base_vib * 1.20 + np.random.normal(0, 0.15)
            else:
                temp = base_temp + np.random.normal(0, 1.0)
                vib = base_vib + np.random.normal(0, 0.15)

            ot_records.append({
                "TIMESTAMP": ot_time,
                "EQUIPMENT_ID": equipment_id,
                "TEMPERATURE_C": round(temp, 2),
                "VIBRATION_RMS": round(vib, 2)
            })
            ot_time += timedelta(minutes=1)

    it_df = pd.DataFrame(it_records)
    ot_df = pd.DataFrame(ot_records)

    # 3. Export to CSV at the project root (absolute path — CWD-independent)
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
