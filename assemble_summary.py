import os
import sys

def read_section(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return ""

def write_summary(content, out_path):
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Summary written to {out_path}")
    except Exception as e:
        print(f"Error writing summary: {e}")

def truncate_to_word_limit(text, min_words=150, max_words=250):
    words = text.split()
    if len(words) < min_words:
        return text  # not enough words, return as is
    # truncate to max_words
    truncated = words[:max_words]
    return ' '.join(truncated)

def main():
    base_dir = r"D:\All Projects\My AI Agent"
    sections = [os.path.join(base_dir, f"section{i}.txt") for i in range(1, 4)]
    contents = [read_section(p) for p in sections]
    combined = " ".join(contents)
    summary = truncate_to_word_limit(combined)
    out_path = os.path.join(base_dir, "summary.txt")
    write_summary(summary, out_path)

if __name__ == "__main__":
    main()
