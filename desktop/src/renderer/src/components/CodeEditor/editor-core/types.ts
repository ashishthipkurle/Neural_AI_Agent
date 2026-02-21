export type EditorStage =
  | 'idle'
  | 'indexing'
  | 'planning'
  | 'waiting_for_plan_approval'
  | 'generating_patch'
  | 'validating'
  | 'waiting_for_patch_approval'
  | 'applying'
  | 'completed'
  | 'error';

export type RiskLevel = 'low' | 'medium' | 'high';

export interface ImplementationPlan {
  objective: string;
  files_to_modify: string[];
  new_files: string[];
  dependencies_affected: string[];
  risk_level: RiskLevel;
  test_plan: string;
  rollback_strategy: string;
}

export interface PatchEntry {
  filePath: string;
  originalContent: string;
  patchedContent: string;
  unifiedDiff: string;
  proposalId?: string; // optional: backed by /api/copilot/refactor
  changedLineNumbers: number[];
  isNewFile?: boolean;
}

export interface PendingPatchSet {
  plan: ImplementationPlan;
  patches: PatchEntry[];
  createdAt: number;
}

export interface EditorStatusEvent {
  type: 'status';
  stage: EditorStage;
  file?: string;
  message: string;
  confidence?: number;
}
