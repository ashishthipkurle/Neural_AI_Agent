"""
Workflow Engine — Core DAG executor.

Takes a workflow definition (nodes + edges), topologically sorts the DAG,
and executes each node using the appropriate executor. Broadcasts real-time
status updates via WebSocket.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable, Awaitable

from agent.workflow.workflow_executors import get_executor, EXECUTOR_REGISTRY
from agent.workflow.workflow_store import WorkflowStore

logger = logging.getLogger("WorkflowEngine")


class WorkflowEngine:
    """
    Executes workflow DAGs in topological order.

    Each node is dispatched to its registered executor.
    Results flow from one node to the next via the edge connections.
    """

    def __init__(self, store: WorkflowStore = None, broadcast_fn: Callable = None):
        """
        Args:
            store: WorkflowStore for persisting run state
            broadcast_fn: Async function to broadcast WebSocket events
                          signature: async (event: dict) -> None
        """
        self.store = store or WorkflowStore()
        self.broadcast_fn = broadcast_fn
        self._active_runs: Dict[str, bool] = {}  # run_id -> is_cancelled

    async def broadcast(self, event: dict):
        """Send event to WebSocket clients."""
        if self.broadcast_fn:
            try:
                if asyncio.iscoroutinefunction(self.broadcast_fn):
                    await self.broadcast_fn(event)
                else:
                    self.broadcast_fn(event)
            except Exception as e:
                logger.warning(f"Broadcast failed: {e}")

    async def execute_workflow(self, workflow_id: str, trigger_type: str = "manual",
                                trigger_data: Dict = None) -> Dict[str, Any]:
        """
        Execute a workflow end-to-end.

        Args:
            workflow_id: ID of the saved workflow
            trigger_type: "manual", "scheduled", "webhook"
            trigger_data: Optional data from the trigger source

        Returns:
            Run result dict with node outputs and status
        """
        # Load workflow
        workflow = self.store.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        nodes = workflow["nodes"]
        edges = workflow["edges"]
        config = workflow.get("config", {})

        if not nodes:
            raise ValueError("Workflow has no nodes")

        # Create run record
        run_id = self.store.create_run(workflow_id, trigger_type)
        self._active_runs[run_id] = False  # Not cancelled

        logger.info(f"▶ Starting workflow '{workflow['name']}' (run={run_id}, nodes={len(nodes)}, edges={len(edges)})")

        await self.broadcast({
            "type": "workflow_run_start",
            "workflow_id": workflow_id,
            "run_id": run_id,
            "node_count": len(nodes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Build adjacency + compute execution order
        node_map = {n["id"]: n for n in nodes}
        adj = defaultdict(list)  # from -> [to]
        in_degree = defaultdict(int)

        for node in nodes:
            in_degree[node["id"]] = in_degree.get(node["id"], 0)

        for edge in edges:
            adj[edge["from"]].append(edge["to"])
            in_degree[edge["to"]] = in_degree.get(edge["to"], 0) + 1

        # Topological sort (Kahn's algorithm)
        execution_order = []
        queue = deque()

        for node_id, degree in in_degree.items():
            if degree == 0:
                queue.append(node_id)

        while queue:
            node_id = queue.popleft()
            execution_order.append(node_id)
            for neighbor in adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for nodes not in the sorted order (disconnected nodes)
        ordered_ids = set(execution_order)
        for node in nodes:
            if node["id"] not in ordered_ids:
                execution_order.append(node["id"])

        logger.info(f"Execution order: {[node_map[nid].get('label', nid) for nid in execution_order]}")

        # Execute nodes in order
        node_outputs: Dict[str, Any] = {}
        node_results: Dict[str, Dict] = {}
        run_logs: List[Dict] = []
        overall_status = "completed"

        input_data = trigger_data or {}

        for node_id in execution_order:
            # Check cancellation
            if self._active_runs.get(run_id):
                logger.info(f"Run {run_id} cancelled")
                overall_status = "cancelled"
                break

            node = node_map.get(node_id)
            if not node:
                continue

            node_label = node.get("label", node_id)
            node_tool_id = node.get("tool_id", node.get("id", "").split("-")[0] if "-" in node.get("id", "") else "")

            # Determine the tool/executor ID
            # The node might have a tool_id from TOOL_CARDS, or we infer from type
            executor_id = node.get("tool_id", "")
            if not executor_id:
                # Try to infer from the node's original tool card ID
                # Nodes created from TOOL_CARDS have IDs like "auto-1234-0" but original tool_id is stored
                executor_id = node.get("original_tool_id", "")
            if not executor_id:
                # Fallback: map type to a default executor
                type_to_executor = {
                    "trigger": "trigger_event",
                    "action": "agent_general",
                    "agent": "agent_general",
                    "condition": "condition",
                }
                executor_id = type_to_executor.get(node.get("type", ""), "agent_general")

            executor = get_executor(executor_id)

            # Broadcast node starting
            await self.broadcast({
                "type": "workflow_node_status",
                "workflow_id": workflow_id,
                "run_id": run_id,
                "node_id": node_id,
                "status": "running",
                "label": node_label,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            log_entry = {
                "node_id": node_id,
                "label": node_label,
                "executor": executor_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }

            # Gather input from parent nodes
            parent_ids = [e["from"] for e in edges if e["to"] == node_id]
            if parent_ids:
                # Merge outputs from all parent nodes
                merged_input = {}
                for pid in parent_ids:
                    if pid in node_outputs:
                        merged_input.update(node_outputs[pid])
                input_data = merged_input
            # First node gets trigger_data, subsequent get parent outputs

            # Get node-specific config (user-set parameters)
            node_config = node.get("config", {})
            node_config["label"] = node_label

            try:
                if executor:
                    start_time = time.time()
                    output = await executor.execute(node_config, input_data, broadcast=self.broadcast_fn)
                    elapsed = round(time.time() - start_time, 2)

                    node_outputs[node_id] = output
                    node_status = "done" if output.get("success", True) else "error"
                    log_entry["output"] = output.get("message", str(output)[:200])
                    log_entry["elapsed_seconds"] = elapsed
                    log_entry["status"] = node_status

                    logger.info(f"  ✓ {node_label} ({executor_id}) → {node_status} in {elapsed}s")
                else:
                    node_status = "error"
                    output = {"success": False, "error": f"No executor for '{executor_id}'"}
                    node_outputs[node_id] = output
                    log_entry["status"] = "error"
                    log_entry["output"] = output["error"]
                    logger.warning(f"  ✗ {node_label}: no executor for {executor_id}")

                # Broadcast node completion
                await self.broadcast({
                    "type": "workflow_node_status",
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "status": node_status,
                    "output": output.get("message", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                node_results[node_id] = {
                    "status": node_status,
                    "output": output,
                }

                if node_status == "error":
                    # Check if workflow should stop on error
                    if config.get("stop_on_error", True):
                        overall_status = "failed"
                        self.store.update_run(run_id, status="failed",
                                              error_message=output.get("error", "Node execution failed"))
                        break

            except Exception as e:
                logger.error(f"  ✗ {node_label} exception: {e}")
                log_entry["status"] = "error"
                log_entry["output"] = str(e)

                await self.broadcast({
                    "type": "workflow_node_status",
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "status": "error",
                    "output": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                node_results[node_id] = {"status": "error", "output": {"error": str(e)}}

                if config.get("stop_on_error", True):
                    overall_status = "failed"
                    break

            finally:
                log_entry["finished_at"] = datetime.now(timezone.utc).isoformat()
                run_logs.append(log_entry)

        # Update run record
        self.store.update_run(run_id, status=overall_status, node_results=node_results, logs=run_logs)

        # Cleanup
        self._active_runs.pop(run_id, None)

        # Broadcast completion
        await self.broadcast({
            "type": "workflow_run_complete",
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": overall_status,
            "node_count": len(nodes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"■ Workflow '{workflow['name']}' {overall_status} (run={run_id})")

        return {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "status": overall_status,
            "node_results": node_results,
            "logs": run_logs,
        }

    def cancel_run(self, run_id: str):
        """Cancel an active workflow run."""
        if run_id in self._active_runs:
            self._active_runs[run_id] = True
            logger.info(f"Cancellation requested for run {run_id}")
            return True
        return False

    async def execute_workflow_inline(self, nodes: List[Dict], edges: List[Dict],
                                       config: Dict = None) -> Dict[str, Any]:
        """
        Execute a workflow directly from node/edge data without saving first.
        Useful for one-off runs from the UI before saving.
        """
        # Create a temporary workflow
        wf = self.store.create_workflow(
            name=f"Inline Run {datetime.now().strftime('%H:%M:%S')}",
            nodes=nodes,
            edges=edges,
            config=config or {}
        )
        try:
            return await self.execute_workflow(wf["id"], trigger_type="inline")
        finally:
            # Clean up temp workflow
            self.store.delete_workflow(wf["id"])
