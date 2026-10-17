"""Unit tests for KrishiAI Field Evaluation Infrastructure.

Validates:
1. Synthetic deterministic metric calculation (Macro-F1, per-class, rejection rate,
   accepted error rate, expert-review rate, OOD rejection rate).
2. Paired guided vs. ordinary comparison on identical specimens.
3. Specimen leakage detection across calibration and locked-test partitions.
4. Fail-fast validation of manifest errors (missing fields, unknown class names,
   duplicate images, duplicate specimen conditions, invalid splits, empty partitions).
5. Dry-run safety and schema-only disclaimer.

NOTE: All tests in this file use deterministic synthetic fixtures for software contract
verification only. They do NOT represent real-world model accuracy.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from ml.src.evaluate_field_dataset import (
    audit_specimen_leakage,
    compute_evaluation_metrics,
    evaluate_field_manifest,
    resolve_true_label,
    validate_manifest_records,
)


class TestFieldEvaluationInfrastructure(unittest.TestCase):
    """Test suite validating field evaluation logic, metric computations, and input integrity checks."""

    def test_synthetic_fixture_metrics(self):
        """Verify metric engine with known deterministic ground-truth and prediction vectors."""
        # Synthetic test fixture with 10 deterministic records
        fixture_records = [
            # In-scope: 2x Corn Gray Leaf Spot (class 0)
            {"specimen_id": "SPEC_1", "condition": "guided", "true_idx": 0, "pred_idx": 0, "status": "ok", "requires_expert": False},
            {"specimen_id": "SPEC_1", "condition": "ordinary", "true_idx": 0, "pred_idx": 0, "status": "ok", "requires_expert": False},
            # In-scope: 2x Corn Common Rust (class 1)
            {"specimen_id": "SPEC_2", "condition": "guided", "true_idx": 1, "pred_idx": 1, "status": "ok", "requires_expert": False},
            {"specimen_id": "SPEC_2", "condition": "ordinary", "true_idx": 1, "pred_idx": 2, "status": "ok", "requires_expert": False},
            # In-scope: Potato Early Blight (class 4) - rejected / abstained
            {"specimen_id": "SPEC_3", "condition": "guided", "true_idx": 4, "pred_idx": 4, "status": "rejected", "requires_expert": True},
            # In-scope: Tomato Early Blight (class 8) - accepted but misclassified as class 7
            {"specimen_id": "SPEC_4", "condition": "guided", "true_idx": 8, "pred_idx": 7, "status": "ok", "requires_expert": False},
            # OOD: Unsupported plant (class 17) - correctly rejected
            {"specimen_id": "SPEC_5", "condition": "guided", "true_idx": 17, "pred_idx": 7, "status": "rejected", "requires_expert": True},
            # OOD: Unsupported plant (class 17) - falsely accepted as disease class 8 (OOD error!)
            {"specimen_id": "SPEC_6", "condition": "ordinary", "true_idx": 17, "pred_idx": 8, "status": "ok", "requires_expert": False},
            # OOD: Unusable image (class 18) - correctly rejected
            {"specimen_id": "SPEC_7", "condition": "guided", "true_idx": 18, "pred_idx": 0, "status": "rejected", "requires_expert": True},
            # OOD: Unusable image (class 18) - correctly rejected
            {"specimen_id": "SPEC_8", "condition": "guided", "true_idx": 18, "pred_idx": 0, "status": "rejected", "requires_expert": True},
        ]

        metrics = compute_evaluation_metrics(fixture_records)

        # 1. Operational safety metrics
        self.assertEqual(metrics["total_samples"], 10)
        self.assertAlmostEqual(metrics["rejection_rate"], 0.40, places=4, msg="4 out of 10 rejected = 40%")
        self.assertAlmostEqual(metrics["expert_review_rate"], 0.40, places=4, msg="4 out of 10 requires_expert = 40%")

        # 2. Accepted prediction error rate
        self.assertEqual(metrics["accepted_samples"], 6)
        # Accepted: records 1 (0==0), 2 (0==0), 3 (1==1) are correct. Records 4 (1!=2), 6 (8!=7), 8 (OOD accepted) are errors.
        self.assertAlmostEqual(metrics["accepted_prediction_accuracy"], 0.50, places=4)
        self.assertAlmostEqual(metrics["accepted_prediction_error_rate"], 0.50, places=4)

        # 3. OOD Rejection Evaluation (classes 17 and 18)
        ood = metrics["ood_evaluation"]
        self.assertEqual(ood["unsupported_plant_samples"], 2)
        self.assertEqual(ood["unsupported_plant_rejections"], 1)
        self.assertAlmostEqual(ood["unsupported_plant_rejection_rate"], 0.50, places=4)

        self.assertEqual(ood["unusable_image_samples"], 2)
        self.assertEqual(ood["unusable_image_rejections"], 2)
        self.assertAlmostEqual(ood["unusable_image_rejection_rate"], 1.00, places=4)

        self.assertEqual(ood["total_ood_samples"], 4)
        self.assertEqual(ood["total_ood_rejections"], 3)
        self.assertAlmostEqual(ood["total_ood_rejection_rate"], 0.75, places=4)
        self.assertAlmostEqual(ood["ood_false_acceptance_rate"], 0.25, places=4)

        # 4. Supported in-scope classification metrics (classes 0..16)
        # Supported samples: 6 total (records 1..6). Correct = 4 (records 1, 2, 3, 5). Accuracy = 4/6 = 66.67%
        self.assertAlmostEqual(metrics["supported_classes_accuracy"], 4 / 6, places=4)
        self.assertGreater(metrics["macro_f1"], 0.0)

        # 5. Open-set confusion matrix check
        cm = metrics["confusion_matrix_open_set"]
        self.assertEqual(len(cm), 19, "Confusion matrix must have 19 rows (17 supported + 2 OOD)")
        self.assertEqual(len(cm[0]), 18, "Confusion matrix must have 18 columns (17 classes + 1 abstained)")
        # Row 17 (unsupported plant): 1 rejected (col 17), 1 accepted as class 8 (col 8)
        self.assertEqual(cm[17][17], 1)
        self.assertEqual(cm[17][8], 1)
        # Row 18 (unusable image): 2 rejected (col 17)
        self.assertEqual(cm[18][17], 2)

    def test_paired_comparison_guided_vs_ordinary(self):
        """Test paired guided-vs-ordinary comparison on identical physical specimens."""
        paired_records = [
            # Specimen 1: Both correct
            {"specimen_id": "SP_1", "condition": "guided", "true_idx": 0, "pred_idx": 0, "status": "ok"},
            {"specimen_id": "SP_1", "condition": "ordinary", "true_idx": 0, "pred_idx": 0, "status": "ok"},
            # Specimen 2: Guided correct, Ordinary incorrect (Guided wins)
            {"specimen_id": "SP_2", "condition": "guided", "true_idx": 1, "pred_idx": 1, "status": "ok"},
            {"specimen_id": "SP_2", "condition": "ordinary", "true_idx": 1, "pred_idx": 2, "status": "ok"},
            # Specimen 3: Both incorrect
            {"specimen_id": "SP_3", "condition": "guided", "true_idx": 4, "pred_idx": 5, "status": "ok"},
            {"specimen_id": "SP_3", "condition": "ordinary", "true_idx": 4, "pred_idx": 6, "status": "ok"},
            # Specimen 4: Both correct
            {"specimen_id": "SP_4", "condition": "guided", "true_idx": 8, "pred_idx": 8, "status": "ok"},
            {"specimen_id": "SP_4", "condition": "ordinary", "true_idx": 8, "pred_idx": 8, "status": "ok"},
        ]

        metrics = compute_evaluation_metrics(paired_records)
        paired = metrics["paired_guided_vs_ordinary"]

        self.assertEqual(paired["num_paired_specimens"], 4)
        self.assertAlmostEqual(paired["guided_accuracy"], 3 / 4, places=4)  # SP_1, SP_2, SP_4 = 75%
        self.assertAlmostEqual(paired["ordinary_accuracy"], 2 / 4, places=4)  # SP_1, SP_4 = 50%
        self.assertAlmostEqual(paired["delta_accuracy_guided_vs_ordinary"], 0.25, places=4)  # +25% delta

        table = paired["contingency_table"]
        self.assertEqual(table["both_correct"], 2)
        self.assertEqual(table["guided_correct_ordinary_incorrect"], 1)
        self.assertEqual(table["ordinary_correct_guided_incorrect"], 0)
        self.assertEqual(table["neither_correct"], 1)

    def test_specimen_leakage_detection(self):
        """Duplicate photographs of the same specimen must not cross calibration and locked-test partitions."""
        leaking_rows = [
            {"image_path": "img1.jpg", "specimen_id": "SP_001", "condition": "guided", "true_label": "Tomato Early Blight", "split": "calibration"},
            {"image_path": "img2.jpg", "specimen_id": "SP_001", "condition": "ordinary", "true_label": "Tomato Early Blight", "split": "locked_test"},
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(leaking_rows, target_split="locked_test")
        self.assertIn("DATA LEAKAGE DETECTED", str(ctx.exception))
        self.assertIn("SP_001", str(ctx.exception))

    def test_missing_required_fields_fails_clearly(self):
        """Missing required fields in manifest must fail clearly with line number."""
        # Missing specimen_id
        bad_rows = [
            {"image_path": "img1.jpg", "specimen_id": "", "condition": "guided", "true_label": "Tomato Early Blight", "split": "locked_test"}
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(bad_rows, target_split="locked_test")
        self.assertIn("Missing required field 'specimen_id'", str(ctx.exception))

    def test_unknown_class_label_fails_clearly(self):
        """Unknown class name in manifest must fail with descriptive error."""
        bad_rows = [
            {"image_path": "img1.jpg", "specimen_id": "SP_1", "condition": "guided", "true_label": "Martian Blight", "split": "locked_test"}
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(bad_rows, target_split="locked_test")
        self.assertIn("Unknown ground-truth label", str(ctx.exception))

    def test_invalid_split_name_fails_clearly(self):
        """Split name outside {'calibration', 'locked_test'} must fail clearly."""
        bad_rows = [
            {"image_path": "img1.jpg", "specimen_id": "SP_1", "condition": "guided", "true_label": "Tomato Early Blight", "split": "training"}
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(bad_rows, target_split="locked_test")
        self.assertIn("Invalid split name 'training'", str(ctx.exception))

    def test_duplicate_image_path_fails_clearly(self):
        """Duplicate image path entries must fail clearly."""
        bad_rows = [
            {"image_path": "same_img.jpg", "specimen_id": "SP_1", "condition": "guided", "true_label": "Tomato Early Blight", "split": "locked_test"},
            {"image_path": "same_img.jpg", "specimen_id": "SP_2", "condition": "guided", "true_label": "Tomato Early Blight", "split": "locked_test"},
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(bad_rows, target_split="locked_test")
        self.assertIn("Duplicate image_path", str(ctx.exception))

    def test_duplicate_specimen_condition_fails_clearly(self):
        """Duplicate photographs of the same specimen under identical condition must fail clearly."""
        bad_rows = [
            {"image_path": "img1.jpg", "specimen_id": "SP_1", "condition": "guided", "true_label": "Tomato Early Blight", "split": "locked_test"},
            {"image_path": "img2.jpg", "specimen_id": "SP_1", "condition": "guided", "true_label": "Tomato Early Blight", "split": "locked_test"},
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(bad_rows, target_split="locked_test")
        self.assertIn("Duplicate specimen condition", str(ctx.exception))

    def test_empty_evaluation_partition_fails_clearly(self):
        """Evaluating on a split partition containing 0 records must fail clearly."""
        rows = [
            {"image_path": "img1.jpg", "specimen_id": "SP_1", "condition": "guided", "true_label": "Tomato Early Blight", "split": "calibration"}
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_records(rows, target_split="locked_test")
        self.assertIn("Empty evaluation partition", str(ctx.exception))

    def test_dry_run_disclaimer_scope(self):
        """Confirm dry-run mode returns schema validation only and disclaims model accuracy."""
        manifest_path = Path("ml/splits/field_manifest_template.csv")
        self.assertTrue(manifest_path.exists())
        dummy_model = Path("ml/models/elasticnet_plantdisease_best.joblib")

        res = evaluate_field_manifest(manifest_path, dummy_model, target_split="locked_test", dry_run=True)
        self.assertEqual(res["status"], "dry_run_success")
        self.assertIn("does not execute inference or prove real-world accuracy", res["disclaimer"])


if __name__ == "__main__":
    unittest.main()
