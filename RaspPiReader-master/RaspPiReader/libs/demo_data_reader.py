import csv
import os

with open(os.path.join(os.getcwd(), "demo.csv")) as file_name:
    file_read = csv.reader(file_name)
    data = list(file_read)

data = data

