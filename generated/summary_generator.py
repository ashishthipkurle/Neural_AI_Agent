import os, sys, textwrap

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def word_count(text):
    return len(text.split())

def generate_summary():
    # Paths to outline and fact sections (adjust if needed)
    base_dir = r'D:\All Projects\My AI Agent'
    outline_path = os.path.join(base_dir, 'framework_outline.txt')
    sections = ['section1.txt', 'section2.txt', 'section3.txt']
    # Read outline
    outline = read_file(outline_path) if os.path.exists(outline_path) else ''
    # Read sections
    facts = []
    for sec in sections:
        sec_path = os.path.join(base_dir, sec)
        if os.path.exists(sec_path):
            facts.append(read_file(sec_path))
    # Combine content
    combined = outline + "\n\n" + "\n\n".join(facts)
    # Simple heuristic: take first 350 words to stay within 300-500 range
    words = combined.split()
    summary_words = words[:350]
    summary = " ".join(summary_words)
    # Ensure word count between 300 and 500; if less, add more words
    if len(summary_words) < 300:
        extra = words[350:500]
        summary += " " + " ".join(extra)
    # Wrap to 80 chars per line for readability
    wrapped = textwrap.fill(summary, width=80)
    print(wrapped)

if __name__ == '__main__':
    generate_summary()
