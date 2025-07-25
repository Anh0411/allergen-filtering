import json

AUTO_PATH = 'auto_ner_training_data.json'
FEEDBACK_PATH = 'feedback_training_data.json'
OUTPUT_PATH = 'merged_ner_training_data.json'

with open(AUTO_PATH, 'r', encoding='utf-8') as f:
    auto_data = json.load(f)
with open(FEEDBACK_PATH, 'r', encoding='utf-8') as f:
    feedback_data = json.load(f)

# Merge and deduplicate
all_data = auto_data + feedback_data
# Use a set of (text, str(entities)) for deduplication
unique = {}
for text, ann in all_data:
    key = (text, str(ann['entities']))
    unique[key] = (text, ann)

merged_data = list(unique.values())

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(merged_data, f, indent=2, ensure_ascii=False)

print(f"Merged {len(auto_data)} auto-labeled and {len(feedback_data)} feedback examples into {len(merged_data)} unique NER training examples. Output: {OUTPUT_PATH}") 