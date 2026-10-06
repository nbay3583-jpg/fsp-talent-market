# Validation

Reproducible matching + assessment validation lives in [`VALIDATION_METHOD.md`](VALIDATION_METHOD.md) (method, data, labels, baselines, metrics, limitations). Results are generated, not typed: `artifacts/validation/latest.{json,md,summary.md}` and the generated block in the root `README.md`. Run: `python -m fsp_market.validation` (`--check` to verify reproducibility).

This is MVP validation on our own dataset (the organisers provided none), not a psychometric calibration.
