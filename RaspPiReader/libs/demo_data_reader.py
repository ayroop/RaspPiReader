import csv
import os

data = []
demo_file_path = os.path.join(os.getcwd(), "demo.csv")

if os.path.exists(demo_file_path):
    with open(demo_file_path) as file_name:
        file_read = csv.reader(file_name)
        data = list(file_read)
else:
    print(f"Warning: {demo_file_path} not found. Demo data will be empty.")

data = data