type HunkHeader = {
  oldStart: number;
  oldCount: number;
  newStart: number;
  newCount: number;
};

const normalizeNewlines = (text: string): string => (text ?? '').replace(/\r\n/g, '\n');

const parseHunkHeader = (line: string): HunkHeader | null => {
  // @@ -10,7 +10,9 @@ optional heading
  const m = /^@@\s+\-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@/.exec(line);
  if (!m) return null;
  return {
    oldStart: Number(m[1]),
    oldCount: m[2] ? Number(m[2]) : 1,
    newStart: Number(m[3]),
    newCount: m[4] ? Number(m[4]) : 1,
  };
};

export class UnifiedDiffApplyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'UnifiedDiffApplyError';
  }
}

export function applyUnifiedDiff(originalText: string, unifiedDiff: string): string {
  const original = normalizeNewlines(originalText);
  const diff = normalizeNewlines(unifiedDiff);

  const originalLines = original.split('\n');
  const diffLines = diff.split('\n');

  let out: string[] = [];
  let oldIndex = 0; // 0-based into originalLines

  let i = 0;
  while (i < diffLines.length) {
    const line = diffLines[i];

    // Skip file headers and other metadata
    if (line.startsWith('--- ') || line.startsWith('+++ ') || line.startsWith('diff ') || line.startsWith('index ') || line.startsWith('@@@')) {
      i++;
      continue;
    }

    if (line.startsWith('@@')) {
      const header = parseHunkHeader(line);
      if (!header) {
        throw new UnifiedDiffApplyError(`Invalid hunk header: ${line}`);
      }

      const hunkOldStartIndex = Math.max(0, header.oldStart - 1);

      // Emit unchanged lines before hunk
      while (oldIndex < hunkOldStartIndex && oldIndex < originalLines.length) {
        out.push(originalLines[oldIndex]);
        oldIndex++;
      }

      i++;
      while (i < diffLines.length) {
        const hunkLine = diffLines[i];
        if (hunkLine.startsWith('@@')) break;
        if (hunkLine.startsWith('--- ') || hunkLine.startsWith('+++ ')) {
          i++;
          continue;
        }
        if (hunkLine.startsWith('\\ No newline at end of file')) {
          i++;
          continue;
        }

        const prefix = hunkLine.slice(0, 1);
        const content = hunkLine.slice(1);

        if (prefix === ' ') {
          const expected = originalLines[oldIndex] ?? '';
          if (expected !== content) {
            throw new UnifiedDiffApplyError(
              `Context mismatch while applying diff. Expected '${expected}' but saw '${content}'.`
            );
          }
          out.push(content);
          oldIndex++;
        } else if (prefix === '-') {
          const expected = originalLines[oldIndex] ?? '';
          if (expected !== content) {
            throw new UnifiedDiffApplyError(
              `Removal mismatch while applying diff. Expected '${expected}' but saw '${content}'.`
            );
          }
          oldIndex++;
        } else if (prefix === '+') {
          out.push(content);
        } else {
          // Unknown line prefix — treat as metadata and ignore
        }

        i++;
      }

      continue;
    }

    i++;
  }

  // Emit remaining unchanged lines
  while (oldIndex < originalLines.length) {
    out.push(originalLines[oldIndex]);
    oldIndex++;
  }

  return out.join('\n');
}

export function extractChangedLineNumbers(unifiedDiff: string): number[] {
  const diff = normalizeNewlines(unifiedDiff);
  const diffLines = diff.split('\n');

  let i = 0;
  const changed = new Set<number>();

  while (i < diffLines.length) {
    const line = diffLines[i];
    if (!line.startsWith('@@')) {
      i++;
      continue;
    }

    const header = parseHunkHeader(line);
    if (!header) {
      i++;
      continue;
    }

    let newLineNo = header.newStart; // 1-based
    i++;

    while (i < diffLines.length) {
      const hunkLine = diffLines[i];
      if (hunkLine.startsWith('@@')) break;
      if (hunkLine.startsWith('\\ No newline at end of file') || hunkLine.startsWith('--- ') || hunkLine.startsWith('+++ ')) {
        i++;
        continue;
      }

      const prefix = hunkLine.slice(0, 1);
      if (prefix === '+') {
        changed.add(newLineNo);
        newLineNo++;
      } else if (prefix === '-') {
        // deletion: doesn't advance new line
      } else if (prefix === ' ') {
        newLineNo++;
      }

      i++;
    }
  }

  return Array.from(changed).sort((a, b) => a - b);
}
