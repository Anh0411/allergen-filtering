import spacy
from spacy.tokens import DocBin
import json

JSON_PATH = 'merged_ner_training_data.json'
OUTPUT_PATH = 'ner_training_data.spacy'

nlp = spacy.blank('en')
doc_bin = DocBin()

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

skipped = 0
for text, ann in data:
    doc = nlp.make_doc(text)
    ents = []
    for start, end, label in ann["entities"]:
        span = doc.char_span(start, end, label=label)
        if span is not None:
            ents.append(span)
        else:
            skipped += 1
    doc.ents = ents
    doc_bin.add(doc)

doc_bin.to_disk(OUTPUT_PATH)
print(f"Converted {len(data)} examples to DocBin. Skipped {skipped} invalid spans. Output: {OUTPUT_PATH}") 