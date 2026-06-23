import pandas as pd
import os
cwd = os.getcwd()
path = os.path.join(cwd, "sample_energy_prices.csv")
path1 = os.path.join(cwd, "data/sample_energy_prices.csv")
SAMPLE_ROWS = pd.read_csv(path1).to_records(index=False).tolist()

print(SAMPLE_ROWS)