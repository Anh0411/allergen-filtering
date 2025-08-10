import spacy
from spacy.training.example import Example
import json
import random
import os

TRAIN_DATA_PATH = "feedback_training_data.json"
OUTPUT_DIR = "./output/spacy_ner_model"
N_ITER = 20
RANDOM_SEED = 42

# Load training data
with open(TRAIN_DATA_PATH, "r", encoding="utf-8") as f:
    TRAIN_DATA = json.load(f)

# TRAIN_DATA should be a list of (text, {"entities": [(start, end, label), ...]})
# Example: [("Add almond milk.", {"entities": [(4, 15, "ALLERGEN")]}), ...]

# Shuffle and split into train/test
random.seed(RANDOM_SEED)
random.shuffle(TRAIN_DATA)
split = int(0.8 * len(TRAIN_DATA))
train_data = TRAIN_DATA[:split]
test_data = TRAIN_DATA[split:]

# Create blank English model
nlp = spacy.blank("en")
if "ner" not in nlp.pipe_names:
    ner = nlp.add_pipe("ner")
else:
    ner = nlp.get_pipe("ner")

# Add labels
for _, annotations in train_data:
    for ent in annotations.get("entities", []):
        ner.add_label(ent[2])

# Disable other pipes for training
other_pipes = [pipe for pipe in nlp.pipe_names if pipe != "ner"]
with nlp.disable_pipes(*other_pipes):
    optimizer = nlp.begin_training()
    for itn in range(N_ITER):
        random.shuffle(train_data)
        losses = {}
        for text, annotations in train_data:
            example = Example.from_dict(nlp.make_doc(text), annotations)
            nlp.update([example], drop=0.2, losses=losses)
        print(f"Iteration {itn+1}/{N_ITER}, Losses: {losses}")

# Evaluate on test set
def evaluate(ner_model, data):
    scorer = spacy.scorer.Scorer()
    for text, annotations in data:
        doc = ner_model(text)
        example = Example.from_dict(doc, annotations)
        scorer.score(example)
    return scorer.scores

if test_data:
    scores = evaluate(nlp, test_data)
    print("Evaluation on test set:")
    print(scores)
else:
    print("No test data available for evaluation.")

# Save model
os.makedirs(OUTPUT_DIR, exist_ok=True)
nlp.to_disk(OUTPUT_DIR)
print(f"Model saved to {OUTPUT_DIR}") 