# Agents Audit

Generated: 2025-12-30T20:24:08+00:00 UTC

## Summary

- Total agents: 36
- High findings: 1
- Med findings: 21
- Low findings: 0
- Info findings: 14

## HIGH (1)

- **qwen3_32B** (`Codex/agents/qwen3_32B.yaml`)
  - hardcoded_infrastructure: Embedded URLs, IPs, or hostnames that may indicate hardcoded infrastructure. (HIGH)
    - Matches: match:127.0.0.1:11434, match:http://127.0.0.1:11434
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: match:model, match:temperature

## MED (21)

- **branch_condition** (`Codex/agents/branch_condition.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **cerberus_validator** (`Codex/agents/cerberus_validator.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:if

- **chat_agent** (`Codex/agents/chat_agent.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **classification_consolidator** (`Codex/agents/classification_consolidator.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:fallback, match:if

- **complex_task_handler** (`Codex/agents/complex_task_handler.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:when

- **execution_result_mapper** (`Codex/agents/execution_result_mapper.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **guard_before_finalize** (`Codex/agents/guard_before_finalize.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **json_extract** (`Codex/agents/json_extract.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **data_review** (`Codex/agents/data_review.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **llm_ollama** (`Codex/agents/llm_ollama.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **llm_plan_builder** (`Codex/agents/llm_plan_builder.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **llm_simple_answer_llm** (`Codex/agents/llm_simple_answer_llm.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **llm_summary** (`Codex/agents/llm_summary.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **plan_executor** (`Codex/agents/plan_executor.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **plan_normalizer** (`Codex/agents/plan_normalizer.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **task_classifier_llm** (`Codex/agents/task_classifier_llm.yaml`)
  - global_llm_config: Global or shared LLM configuration that may bypass per-call controls. (MED)
    - Matches: keyword:executor: llm, match:executor: llm

- **tuple_append** (`Codex/agents/tuple_append.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:else, match:if

- **workflow_demo** (`Codex/agents/workflow_demo.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:branch

- **workspace_list_files** (`Codex/agents/workspace_list_files.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:if

- **workspace_read_file** (`Codex/agents/workspace_read_file.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:if

- **workspace_write_file** (`Codex/agents/workspace_write_file.yaml`)
  - implicit_control_flow: Implicit branching or side-effect driven control flow cues. (MED)
    - Matches: match:if

## LOW (0)

- None

## INFO (14)

- **adaptive_task_agent** (`Codex/agents/adaptive_task_agent.yaml`)
  - No findings

- **clarification_context** (`Codex/agents/clarification_context.yaml`)
  - No findings

- **data_review_mapper** (`Codex/agents/data_review_mapper.yaml`)
  - No findings

- **echo_plan** (`Codex/agents/echo_plan.yaml`)
  - No findings

- **echo_simple** (`Codex/agents/echo_simple.yaml`)
  - No findings

- **final_message_selector** (`Codex/agents/final_message_selector.yaml`)
  - No findings

- **json_pack** (`Codex/agents/json_pack.yaml`)
  - No findings

- **llm_prompt_chain** (`Codex/agents/llm_prompt_chain.yaml`)
  - No findings

- **llm_simple_answer** (`Codex/agents/llm_simple_answer.yaml`)
  - No findings

- **output_collector** (`Codex/agents/output_collector.yaml`)
  - No findings

- **prompt_builder** (`Codex/agents/prompt_builder.yaml`)
  - No findings

- **python_eval_input** (`Codex/agents/python_eval_input.yaml`)
  - No findings

- **simple_answer_guard** (`Codex/agents/simple_answer_guard.yaml`)
  - No findings

- **task_classifier** (`Codex/agents/task_classifier.yaml`)
  - No findings
