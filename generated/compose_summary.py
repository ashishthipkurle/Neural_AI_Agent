import os, re, sys, textwrap

def read_content(path):
    if not path or not os.path.isfile(path):
        return ''
    with open(path, 'r', encoding='utf-8') as fp:
        return fp.read()

def truncate_to_word_limit(text, min_words=300, max_words=500):
    words = re.findall(r"\S+", text)
    if len(words) < min_words:
        return text  # not enough words, return as is
    # truncate to max_words
    truncated = ' '.join(words[:max_words])
    return truncated

def compose_summary(step2_text, step3_text):
    # Create headings
    heading1 = "## Step 2 Data"
    heading2 = "## Step 3 Data"
    combined = f"{heading1}\n\n{step2_text}\n\n{heading2}\n\n{step3_text}"
    # Wrap lines for readability (80 chars)
    wrapped = '\n'.join(textwrap.fill(line, width=80) for line in combined.split('\n'))
    # Truncate to word limit
    final = truncate_to_word_limit(wrapped)
    return final

def main():
    # Assume step2 and step3 correspond to section2.txt and section3.txt in root
    base_dir = r'D:\All Projects\My AI Agent'
    step2_path = os.path.join(base_dir, 'section2.txt')
    step3_path = os.path.join(base_dir, 'section3.txt')
    step2_text = read_content(step2_path)
    step3_text = read_content(step3_path)
    if not step2_text or not step3_text:
        print('Could not locate step2 or step3 data files.')
        sys.exit(1)
    summary = compose_summary(step2_text, step3_text)
    out_dir = os.path.join(base_dir, 'generated')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'summary_from_steps.txt')
    with open(out_path, 'w', encoding='utf-8') as fp:
        fp.write(summary)
    print(f'Summary written to {out_path}')

if __name__ == "__main__":
    main()
