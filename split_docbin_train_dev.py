import spacy
from spacy.tokens import DocBin
import random

INPUT_PATH = 'ner_training_data.spacy'
TRAIN_PATH = 'train.spacy'
DEV_PATH = 'dev.spacy'
SPLIT_RATIO = 0.8

nlp = spacy.blank('en')
doc_bin = DocBin().from_disk(INPUT_PATH)
docs = list(doc_bin.get_docs(nlp.vocab))

random.shuffle(docs)
split = int(len(docs) * SPLIT_RATIO)
train_docs = docs[:split]
dev_docs = docs[split:]

train_bin = DocBin()
for doc in train_docs:
    train_bin.add(doc)
train_bin.to_disk(TRAIN_PATH)

dev_bin = DocBin()
for doc in dev_docs:
    dev_bin.add(doc)
dev_bin.to_disk(DEV_PATH)

print(f"Split {len(docs)} docs: {len(train_docs)} for training, {len(dev_docs)} for dev. Output: {TRAIN_PATH}, {DEV_PATH}") 