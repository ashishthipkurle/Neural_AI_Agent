import json
from typing import List, Dict

def generate_descriptions(frameworks: List[str]) -> List[Dict[str, str]]:
    """Generate concise descriptions for each framework.

    For each framework name, the function returns a dictionary with:
    - 'framework': name of the framework
    - 'key_features': a short bullet list of core features
    - 'typical_use_cases': common scenarios where the framework shines
    - 'advantage': one notable benefit
    - 'limitation': one notable drawback

    The implementation uses a simple hard‑coded knowledge base. In a real
    system this could be replaced with LLM calls or a database lookup.
    """
    # Minimal knowledge base – extend as needed.
    knowledge = {
        "Django": {
            "key_features": "- Batteries‑included ORM, admin panel, authentication\n- Convention over configuration\n- Strong security features",
            "typical_use_cases": "Full‑stack web applications, content management systems, rapid MVPs",
            "advantage": "Rapid development with many built‑in components",
            "limitation": "Monolithic structure can be heavyweight for small services"
        },
        "React": {
            "key_features": "- Component‑based UI\n- Virtual DOM for efficient updates\n- Rich ecosystem (hooks, context)",
            "typical_use_cases": "Interactive single‑page applications, dynamic dashboards",
            "advantage": "Declarative UI makes state management intuitive",
            "limitation": "Steep learning curve around tooling and state libraries"
        },
        "TensorFlow": {
            "key_features": "- Scalable computation graphs\n- GPU/TPU acceleration\n- Extensive model zoo",
            "typical_use_cases": "Deep learning research, production‑grade ML pipelines",
            "advantage": "Optimized for large‑scale training and deployment",
            "limitation": "Verbose API; can be harder for beginners compared to PyTorch"
        },
        "Flask": {
            "key_features": "- Minimal core, extensible via extensions\n- Simple routing and request handling",
            "typical_use_cases": "Micro‑services, lightweight APIs, prototyping",
            "advantage": "Very lightweight and flexible",
            "limitation": "Requires manual addition of many features (ORM, auth, etc.)"
        }
    }
    results = []
    for fw in frameworks:
        info = knowledge.get(fw, None)
        if info is None:
            # Fallback generic template
            info = {
                "key_features": "Key features not available",
                "typical_use_cases": "Typical use cases not available",
                "advantage": "Advantage not available",
                "limitation": "Limitation not available"
            }
        entry = {
            "framework": fw,
            "key_features": info["key_features"],
            "typical_use_cases": info["typical_use_cases"],
            "advantage": info["advantage"],
            "limitation": info["limitation"]
        }
        results.append(entry)
    return results

if __name__ == "__main__":
    sample = ["Django", "React", "TensorFlow", "Flask", "FastAPI"]
    descriptions = generate_descriptions(sample)
    print(json.dumps(descriptions, indent=2, ensure_ascii=False))
