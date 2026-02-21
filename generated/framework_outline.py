import textwrap

frameworks = [
    {
        "name": "TensorFlow",
        "description": "An open-source library for numerical computation and large-scale machine learning developed by Google.",
        "features": [
            "Static and eager execution",
            "Keras high-level API",
            "TensorBoard visualization",
            "Distributed training support",
            "Extensive model zoo"
        ],
        "strengths": [
            "Production-ready deployment",
            "Strong ecosystem for mobile/embedded (TensorFlow Lite)",
            "Robust tooling and community",
            "Excellent support for TPUs"
        ],
        "use_cases": [
            "Computer vision pipelines",
            "Natural language processing models",
            "Time-series forecasting",
            "Edge AI on mobile devices"
        ]
    },
    {
        "name": "PyTorch",
        "description": "A flexible deep-learning framework with dynamic computation graphs, favored in research and increasingly in production.",
        "features": [
            "Dynamic eager execution",
            "TorchScript for serialization",
            "Rich ecosystem (torchvision, torchaudio, torchtext)",
            "Native support for CUDA",
            "Strong autograd engine"
        ],
        "strengths": [
            "Intuitive Pythonic API",
            "Fast prototyping",
            "Strong community in academia",
            "Growing production tooling (TorchServe)"
        ],
        "use_cases": [
            "Research prototypes",
            "Generative models (GANs, Transformers)",
            "Reinforcement learning",
            "Medical imaging analysis"
        ]
    },
    {
        "name": "JAX",
        "description": "A high-performance library for numerical computing that combines NumPy-like API with automatic differentiation and XLA compilation.",
        "features": [
            "Just-in-time compilation with XLA",
            "Function transformations (jit, vmap, pmap)",
            "Pure functional programming style",
            "Seamless GPU/TPU acceleration"
        ],
        "strengths": [
            "Extreme speed for research workloads",
            "Elegant handling of vectorized operations",
            "Easy scaling across multiple accelerators",
            "Strong integration with Flax and Haiku libraries"
        ],
        "use_cases": [
            "Large-scale scientific computing",
            "Advanced research in deep learning (e.g., transformer scaling)",
            "Probabilistic programming",
            "Differentiable physics simulations"
        ]
    }
]

def print_outline(frames):
    for f in frames:
        print(f"\n=== {f['name']} ===")
        # Simple print without textwrap to avoid encoding issues
        print(f"Description: {f['description']}")
        print("Features:")
        for feat in f['features']:
            print(f"- {feat}")
        print("Strengths:")
        for s in f['strengths']:
            print(f"- {s}")
        print("Use Cases:")
        for uc in f['use_cases']:
            print(f"- {uc}")

if __name__ == "__main__":
    print_outline(frameworks)
