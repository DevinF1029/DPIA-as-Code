## Summary

<!-- Describe what this PR changes and why. -->

## Related Issue

Closes #

## Change Type

- [ ] Bug fix (`fix`)
- [ ] New feature / enhancement (`feat`)
- [ ] Governance / Policy-as-Code rules (`rules/` or `governance/`)
- [ ] Web Workbench UI / API
- [ ] Documentation / Tests / CI

## Checklist

- [ ] Ran `pytest -v` (or `python -m unittest discover -s tests -v`) and all tests pass
- [ ] Ran `ruff check src tests` with zero errors
- [ ] Validated modified or new `dataflow.yaml` examples with `dpia validate`
- [ ] **If `src/dpia_as_code/models/` changed**: ran `python -m dpia_as_code.schema_export` and committed updated `schemas/dataflow.schema.json`
- [ ] **If rules/controls changed**: kept `governance/` docs, `rules/*.yaml`, and `tests/` synchronized
