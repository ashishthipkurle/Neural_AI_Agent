import type { ImplementationPlan, PendingPatchSet, PatchEntry } from './types';

export type Snapshot = {
  filePath: string;
  content: string;
  timestamp: number;
};

export type PatchHistoryItem = {
  filePath: string;
  originalContent: string;
  patchedContent: string;
  unifiedDiff: string;
  proposalId?: string;
  timestamp: number;
};

export class EditorStateManager {
  private snapshots = new Map<string, Snapshot[]>();
  private pendingPatchSet: PendingPatchSet | null = null;
  private appliedPatchHistory: PatchHistoryItem[] = [];

  getPendingPatchSet(): PendingPatchSet | null {
    return this.pendingPatchSet;
  }

  setPendingPatchSet(patchSet: PendingPatchSet | null) {
    this.pendingPatchSet = patchSet;
  }

  addSnapshot(filePath: string, content: string) {
    const stack = this.snapshots.get(filePath) ?? [];
    stack.push({ filePath, content, timestamp: Date.now() });
    this.snapshots.set(filePath, stack);
  }

  getLatestSnapshot(filePath: string): Snapshot | null {
    const stack = this.snapshots.get(filePath);
    if (!stack || stack.length === 0) return null;
    return stack[stack.length - 1];
  }

  clearSnapshots(filePath?: string) {
    if (!filePath) {
      this.snapshots.clear();
      return;
    }
    this.snapshots.delete(filePath);
  }

  recordAppliedPatch(entry: PatchEntry) {
    this.appliedPatchHistory.push({
      filePath: entry.filePath,
      originalContent: entry.originalContent,
      patchedContent: entry.patchedContent,
      unifiedDiff: entry.unifiedDiff,
      proposalId: entry.proposalId,
      timestamp: Date.now(),
    });
  }

  getAppliedHistory(): PatchHistoryItem[] {
    return [...this.appliedPatchHistory];
  }

  revertLastApplied(): PatchHistoryItem | null {
    if (this.appliedPatchHistory.length === 0) return null;
    return this.appliedPatchHistory.pop() ?? null;
  }

  createPendingPatchSet(plan: ImplementationPlan, patches: PatchEntry[]): PendingPatchSet {
    const patchSet: PendingPatchSet = {
      plan,
      patches,
      createdAt: Date.now(),
    };
    this.pendingPatchSet = patchSet;
    return patchSet;
  }
}
