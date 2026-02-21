import os

summary = """Final User-Facing Summary\n\nThis document provides a concise overview of the project outcomes, key findings, and actionable recommendations.\n\n1. Project Objectives\n   - Brief description of goals.\n\n2. Methodology\n   - Summary of approaches and tools used.\n\n3. Results\n   - Highlight major results and metrics.\n\n4. Conclusions\n   - Interpretation of results and implications.\n\n5. Recommendations\n   - Suggested next steps and improvements.\n\nThank you for reviewing this summary.\n"""

output_path = os.path.join(r'D:\All Projects\My AI Agent\generated', "final_user_facing_summary.txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(summary)
print(f"Summary written to {output_path}")
