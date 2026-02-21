import datetime

summary = """Final User-Facing Summary\n\nThis document provides a concise overview of the project outcomes, key findings, and actionable recommendations.\n\n1. Project Objectives\n- Summarize the goals and scope.\n\n2. Methodology\n- Outline the approach and tools used.\n\n3. Results\n- Highlight the main results and insights.\n\n4. Recommendations\n- Provide next steps and suggestions for implementation.\n\nGenerated on: {}\n""".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

output_path = r"D:\All Projects\My AI Agent\final_user_summary.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(summary)
print(f"Summary written to {output_path}")
