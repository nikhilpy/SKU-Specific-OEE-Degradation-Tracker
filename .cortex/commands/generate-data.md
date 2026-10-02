# Generate Data

Generate referentially consistent synthetic IT/OT manufacturing data and load it into Snowflake.

## Steps

1. **Generate synthetic CSVs**: Run the data generator to produce IT batch schedules and OT sensor telemetry:
   ```
   python code/misc/data_generator.py
   ```
   This creates two CSV files with:
   - `RAW_IT_BATCHES` — Batch schedules with SKU assignments per equipment per shift
   - `RAW_OT_TELEMETRY` — Sensor readings (temperature, vibration) at high frequency
   - SKU-899 (Heavy-Duty Cardboard) is hard-coded with a 15% temperature spike and 20% vibration spike

2. **Stage and load**: Upload CSVs to `@FACTORY_DATA_STAGE` and run `COPY INTO`:
   ```sql
   PUT file://path/to/ot_telemetry.csv @FACTORY_DATA_STAGE/ot/ AUTO_COMPRESS=TRUE;
   PUT file://path/to/it_batches.csv @FACTORY_DATA_STAGE/it/ AUTO_COMPRESS=TRUE;
   COPY INTO RAW_OT_TELEMETRY FROM @FACTORY_DATA_STAGE/ot/ FILE_FORMAT = CSV_FORMAT;
   COPY INTO RAW_IT_BATCHES FROM @FACTORY_DATA_STAGE/it/ FILE_FORMAT = CSV_FORMAT;
   ```

3. **Validate**: Confirm row counts and referential integrity:
   ```sql
   SELECT COUNT(*) AS ot_rows FROM RAW_OT_TELEMETRY;
   SELECT COUNT(*) AS it_rows FROM RAW_IT_BATCHES;
   SELECT COUNT(DISTINCT EQUIPMENT_ID) AS equipments FROM RAW_OT_TELEMETRY;
   SELECT COUNT(DISTINCT SKU_ID) AS skus FROM RAW_IT_BATCHES;
   ```

## Key Details

- The generator produces data with referential integrity: IT batch time windows align with OT timestamps.
- Equipment IDs and SKU IDs are consistent across both datasets.
- The Dynamic Table `IT_OT_CONVERGED` will auto-refresh within 1 minute of data landing.
