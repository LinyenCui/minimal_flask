import re

with open("user_trips.txt", "r", encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]

db_fares = []
user_total = 0
db_records = []

# Using regex to split by tabs
for line in lines:
    cols = re.split(r'\t+', line)
    # the 10th col (index 9) is 實收
    if len(cols) >= 10:
        try:
            fare = int(cols[9])
            user_total += fare
            db_records.append({ 'id': cols[0], 'start': cols[3], 'end': cols[5], 'fare': fare })
        except ValueError:
            # maybe empty or not integer
            pass

print(f"Total lines parsed: {len(db_records)}")
print(f"User text total 實收 = {user_total}")

# Now calculate the total from what we inserted
total_inserted_fare = 0

from restore_all_photos import data as data1to3
from restore_batch_4 import data as data4

all_data = data1to3 + data4

inserted_total = 0
inserted_records = []
for row in all_data:
    fare = row[7] # actual_fare
    inserted_total += fare
    inserted_records.append({ 'start': row[1], 'end': row[3], 'fare': fare })

print(f"Total imported rows: {len(inserted_records)}")
print(f"Total imported 實收 = {inserted_total}")
print(f"Difference = {user_total - inserted_total}")

# Find missing ones by mapping
import collections
user_counts = collections.Counter([(r['start'], r['end'], r['fare']) for r in db_records])
inserted_counts = collections.Counter([(r['start'], r['end'], r['fare']) for r in inserted_records])

diff_missing_in_db = user_counts - inserted_counts
diff_missing_in_user = inserted_counts - user_counts

print("Missing in DB (but present in User text):", diff_missing_in_db)
print("Missing in User text (but present in DB):", diff_missing_in_user)

# Print out specific ids missing in DB
db_counts_mutable = collections.Counter([(r['start'], r['end'], r['fare']) for r in inserted_records])
missing_ids = []
for r in db_records:
    key = (r['start'], r['end'], r['fare'])
    if db_counts_mutable[key] > 0:
        db_counts_mutable[key] -= 1
    else:
        missing_ids.append(r)

if missing_ids:
    print("These specific rows from user's list were NOT successfully matched in DB imports:")
    for m in missing_ids:
        print(f"ID {m['id']} -> {m}")
