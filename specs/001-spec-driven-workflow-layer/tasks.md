# 001 — Tasks

- [ ] **TASK-1** [P] Add `IDeliveryWorkflow` ABC and SDD value objects — file: `src/ooagent/core/protocols.py` — implements REQ-1/AC-1
  - **TEST-1**: `tests/core/test_protocols.py::test_idelivery_workflow_cannot_be_instantiated_directly`

- [ ] **TASK-2** [P] Add the 8-Article constitution — file: `src/ooagent/workflow/constitution.py` — implements REQ-2/AC-2
  - **TEST-2**: `tests/workflow/test_constitution.py::test_constitution_has_exactly_eight_articles`

- [ ] **TASK-3** [P] Add the 19-target gate catalog — file: `src/ooagent/workflow/gate_catalog.py` — implements REQ-3/AC-3
  - **TEST-3**: `tests/workflow/test_gate_catalog.py::test_gate_catalog_has_exactly_nineteen_targets`

- [ ] **TASK-4** [P] Add traceability orphan detection — file: `src/ooagent/workflow/traceability.py` — implements REQ-4/AC-4
  - **TEST-4**: `tests/workflow/test_traceability.py::test_verify_traceability_flags_entry_missing_task_id_as_failing`

- [ ] **TASK-5** Add the runnable gate Makefile — file: `.specify/gates/Makefile` — implements REQ-5/AC-5
  - **TEST-5**: `tests/workflow/test_gate_makefile.py::test_makefile_required_gates_have_non_optional_recipes`

- [ ] **TASK-6** Add the verify-spec traceability checker — file: `scripts/sdd-verify-spec.sh` — implements REQ-6/AC-6
  - **TEST-6**: `tests/workflow/test_sdd_verify_spec.py::test_script_passes_on_this_repos_own_specs_directory`
