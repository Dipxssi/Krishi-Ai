# KrishiAI Field-Data Evaluation Protocol and Standard Operating Procedure (SOP)

This document establishes the evaluation protocol and scientific constraints for evaluating plant disease models on expert-labeled field images.

---

## 1. Motivation and Context

During controlled external evaluation on PlantDoc, models trained on the studio-background PlantVillage dataset suffered a severe domain shift (87.54% PlantVillage test accuracy vs. 6.17% on unconstrained PlantDoc field images). 

Camera guidance instructions (photographing a single leaf on a plain neutral background under diffuse daylight) are designed to constrain this variance. However, **camera instructions cannot be assumed or claimed to improve real-world accuracy until verified on a genuinely held-out, expert-labeled field dataset**.

---

## 2. Field Data Acquisition Protocol

To conduct a scientifically valid evaluation:
1. **Target Physical Population**:
   - Collect leaves from smallholder farmer plots across representative agro-ecological zones (e.g. Maharashtra, Punjab, Uttar Pradesh).
   - Sample across 17 target classes (tomato, potato, maize) plus weed/non-target species (`unsupported_plant`) and unreadable leaves (`unusable_image`).
2. **Paired Capture Design**:
   - For a subset of leaves ($N \ge 100$), photograph the **identical physical leaf specimen** under two distinct conditions:
     1. **`ordinary` condition**: In-situ photography on the plant with complex background foliage, soil, and natural lighting.
     2. **`guided` condition**: Detached or turned leaf laid flat against a clean neutral background (white cardboard or grey card) in open shade / diffuse daylight.
3. **Specimen Metadata**:
   - Assign a unique `specimen_id` (e.g., `MH_NAS_TOM_20261014_001`) to each physical leaf.
   - Record phone camera model, GPS coordinates, plot ID, and lighting condition.
   - Dual independent diagnosis by certified agricultural extension agronomists or Krishi Vigyan Kendra (KVK) plant pathologists.

---

## 3. Split Isolation and Leakage Prevention

1. **Strict Specimen Grouping**:
   - All captures of the same physical specimen (both `guided` and `ordinary`) **must strictly reside in the same split**.
   - No view, crop, or lighting variation of any specimen in `locked_test` may ever appear in `calibration` or training.
2. **Exploratory Calibration Split vs. Locked Test Split**:
   - **`calibration` split**: Dedicated for exploratory analysis, setting quality score thresholds, and tuning uncertainty rejection safeguards.
   - **`locked_test` split**: Completely sealed until the final pipeline is frozen. Evaluated strictly **once** to produce the benchmark report.

---

## 4. Manifest Schema (`field_manifest.csv`)

| Column Name | Type | Allowed Values / Format | Description |
|---|---|---|---|
| `image_path` | string | Relative file path | Path to stored image |
| `specimen_id` | string | Unique alphanumeric identifier | Physical leaf identifier |
| `plant_id` | string | Alphanumeric identifier | Plant or plot identifier |
| `condition` | string | `'guided'` or `'ordinary'` | Photo acquisition condition |
| `true_label` | string | 17 target classes, or `unsupported_plant`, or `unusable_image` | Ground-truth disease or OOD category |
| `split` | string | `'calibration'` or `'locked_test'` | Dataset split |
| `expert_evaluator_id`| string | Extension officer / KVK badge | Authenticating expert |
| `crop` | string | Crop name | Crop species |
| `location` | string | District, State | Field location |
| `camera_model` | string | Smartphone model | Camera sensor specification |
| `notes` | string | Text | Contextual notes |

---

## 5. Metrics and Operational Safety Evaluation

The evaluation pipeline (`ml/src/evaluate_field_dataset.py`) computes:
1. **Classification Accuracy & Macro-F1**: Evaluated strictly across the 17 supported in-scope classes.
2. **Rejection / Abstention Targets for OOD Categories**:
   - `unsupported_plant` (class 17) and `unusable_image` (class 18) are **rejection targets**, not valid classification classes for the 17-class disease model.
   - The **only correct, safe outcome** for an unsupported plant or unusable image is **Rejection / Abstention** (`status != "ok"` or `requires_expert == True`).
   - Any acceptance of an OOD input as a disease class is recorded as a **False Acceptance (OOD failure)**.
   - Reports `unsupported_plant_rejection_rate`, `unusable_image_rejection_rate`, and `ood_false_acceptance_rate`.
3. **Open-Set Confusion Matrix (19 True Rows x 18 Predicted Columns)**:
   - Rows: 17 supported classes (0..16), `unsupported_plant` (17), `unusable_image` (18).
   - Columns: 17 accepted disease predictions (0..16), and Column 17 (`Abstained / Rejected`).
4. **Rejection Rate**: Percentage of total inputs where the system safely abstained:
   $$\text{Rejection Rate} = \frac{N_{\text{rejected}}}{N_{\text{total}}}$$
5. **Accepted-Prediction Error Rate**: Error rate calculated strictly among samples that the system accepted:
   $$\text{Accepted Error Rate} = \frac{N_{\text{incorrect\_accepted}}}{N_{\text{accepted}}}$$
   *(A reliable safety system must achieve a dramatically lower error rate on accepted samples than its raw accuracy would suggest).*
6. **Expert-Review Rate**: Percentage of cases routed to extension personnel.
7. **Paired Guided vs. Ordinary Contingency Analysis**: Comparison of `guided` vs. `ordinary` accuracy on identical physical specimens to isolate the empirical effect of the camera guidance protocol.

---

## 6. Execution Commands and Dry Run Constraints

Generate manifest template:
```bash
python ml/src/evaluate_field_dataset.py --generate-template ml/splits/field_manifest_template.csv
```

Validate manifest formatting, split isolation, and specimen leakage:
```bash
python ml/src/evaluate_field_dataset.py --manifest path/to/field_manifest.csv --dry-run
```
> [!NOTE]
> **Dry Run Scope**: `--dry-run` performs integrity validation of CSV column schema, required fields, allowed split names, and specimen grouping. **It is strictly a schema and leakage check and provides NO proof of real-world model accuracy.**

Execute full evaluation on the locked evaluation set:
```bash
python ml/src/evaluate_field_dataset.py --manifest path/to/field_manifest.csv --split locked_test --output-dir ml/artifacts
```
*(Evaluates strictly once on the locked partition. Model weights and decision thresholds must not be tuned on this partition).*
