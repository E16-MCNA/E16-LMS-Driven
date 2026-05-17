import csv
try:
    with open('datastudio_export.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            print(row)
            if i > 5: break
except Exception as e:
    print(f"Error: {e}")
