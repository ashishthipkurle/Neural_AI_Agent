from typing import Dict, Any, Optional
import asyncio
import os
import re
import socket
import subprocess
import time

from agent.skills.base_skill import BaseSkill, SkillResult


class CodingSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "coding"

    @property
    def manifest(self):
        from agent.skills.base_skill import SkillManifest

        return SkillManifest(
            name="coding",
            version="1.1.0",
            description="Handles code reading, writing, project scaffolding, and command execution.",
            actions=["read_file", "write_file", "list_files", "run_command", "scaffold_react_website"],
            permissions=["filesystem", "command_execution"],
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        intent = intent.lower()
        keywords = ["code", "script", "file", "run", "execute", "python", "debug", "react", "website", "web app"]
        return 0.9 if any(keyword in intent for keyword in keywords) else 0.0

    async def execute(self, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> SkillResult:
        if action == "read_file":
            return await self._read_file(params.get("path"))
        if action == "write_file":
            return await self._write_file(params.get("path"), params.get("content"))
        if action == "list_files":
            return await self._list_files(params.get("directory", "."))
        if action == "run_command":
            return await self._run_command(params.get("command"), params.get("cwd", "."))
        if action == "scaffold_react_website":
            return await self._scaffold_react_website(params)
        return SkillResult(success=False, error=f"Unknown action: {action}")

    # ==================== CONTENT GENERATION ====================

    def _detect_business_type(self, name: str) -> str:
        """Detect business type from name keywords."""
        n = name.lower()
        if any(k in n for k in ["ai", "artificial", "intelligence", "ml", "neural", "deep learning"]):
            return "ai"
        if any(k in n for k in ["tech", "software", "saas", "cloud", "data", "cyber", "digital"]):
            return "tech"
        if any(k in n for k in ["health", "medical", "pharma", "bio", "care", "clinic"]):
            return "health"
        if any(k in n for k in ["finance", "fin", "pay", "bank", "invest", "capital"]):
            return "finance"
        if any(k in n for k in ["edu", "learn", "academy", "school", "tutor"]):
            return "education"
        return "tech"

    def _get_content_preset(self, title: str, btype: str) -> Dict[str, Any]:
        """Return content sections based on detected business type."""
        _P = {
            "ai": {
                "eyebrow": "AI-Powered Innovation",
                "tagline": f"Intelligent solutions that transform how businesses operate. {title} brings cutting-edge AI to your workflow.",
                "cta1": "Explore Solutions", "cta2": "Book a Demo",
                "footer": "Smarter decisions. Faster results.",
                "about": f"{title} leverages advanced artificial intelligence and machine learning to help organizations automate processes, uncover insights, and scale intelligently.",
                "focus": "Innovation, accuracy, scalability, and responsible AI practices.",
                "contact_desc": f"Tell us about your use case and our team will show you how {title} can help.",
                "contact_ph": "Describe your AI/automation challenge...",
                "prod_title": "Products & Solutions",
                "prod_lead": "AI-powered tools built for real-world impact across industries.",
                "products": [
                    {"name": "Predictive Analytics Engine", "cat": "Analytics", "desc": "Forecast trends and outcomes with ML-powered prediction models."},
                    {"name": "NLP Document Processor", "cat": "Language AI", "desc": "Extract structured data from unstructured text at scale."},
                    {"name": "Computer Vision Suite", "cat": "Vision AI", "desc": "Real-time image and video analysis for quality and safety."},
                    {"name": "AI Copilot Platform", "cat": "Automation", "desc": "Intelligent assistant that automates repetitive workflows."},
                    {"name": "Model Training Studio", "cat": "MLOps", "desc": "End-to-end model development, training, and deployment."},
                    {"name": "Data Pipeline Orchestrator", "cat": "Infrastructure", "desc": "Scalable ETL and feature engineering for production ML."},
                ],
                "testimonials": [
                    {"name": "S. Rodriguez", "org": "DataFlow Inc.", "quote": "Their AI platform cut our data processing time by 80%."},
                    {"name": "J. Chen", "org": "Apex Logistics", "quote": "The predictive models helped us optimize inventory and reduce waste significantly."},
                    {"name": "R. Patel", "org": "FinBridge Capital", "quote": "Reliable, well-documented APIs and responsive engineering support throughout integration."},
                ],
            },
            "tech": {
                "eyebrow": "Modern Technology Solutions",
                "tagline": f"Build, ship, and scale with confidence. {title} provides the tools modern teams need.",
                "cta1": "Get Started", "cta2": "View Docs",
                "footer": "Build better. Ship faster.",
                "about": f"{title} builds developer-first infrastructure and tooling that helps engineering teams move faster without sacrificing reliability.",
                "focus": "Developer experience, reliability, performance, and security by default.",
                "contact_desc": f"Have a project in mind? Reach out to discuss how {title} can accelerate your team.",
                "contact_ph": "Tell us about your project or technical challenge...",
                "prod_title": "Products & Services",
                "prod_lead": "Modern tools and infrastructure built for high-velocity engineering teams.",
                "products": [
                    {"name": "Cloud Deploy Platform", "cat": "Infrastructure", "desc": "One-click deployments with auto-scaling and monitoring."},
                    {"name": "API Gateway Pro", "cat": "Networking", "desc": "Secure, rate-limited API management with real-time analytics."},
                    {"name": "CI/CD Pipeline Engine", "cat": "DevOps", "desc": "Automated build, test, and deploy workflows for any stack."},
                    {"name": "Monitoring Dashboard", "cat": "Observability", "desc": "Full-stack monitoring with alerting and incident management."},
                    {"name": "Auth & Identity Suite", "cat": "Security", "desc": "Enterprise-grade authentication with SSO and RBAC."},
                    {"name": "Database Service", "cat": "Storage", "desc": "Managed database with automatic backups and global replication."},
                ],
                "testimonials": [
                    {"name": "K. Williams", "org": "ScaleUp Labs", "quote": "Reduced our deployment time from hours to minutes."},
                    {"name": "M. Torres", "org": "Quantum SaaS", "quote": "Rock-solid infrastructure with excellent uptime."},
                    {"name": "A. Kim", "org": "DevForge Co.", "quote": "Best-in-class documentation and support."},
                ],
            },
            "health": {
                "eyebrow": "Healthcare Solutions Partner",
                "tagline": f"Professional-grade devices and services for hospitals, clinics, and care providers. {title} delivers quality you can trust.",
                "cta1": "Browse Products", "cta2": "Request a Quote",
                "footer": "Reliable equipment. Trusted care.",
                "about": f"{title} helps healthcare providers equip their facilities with dependable devices and transparent service.",
                "focus": "Patient safety, compliance, product reliability, and long-term value.",
                "contact_desc": f"Tell us what equipment you need and the {title} team will respond with options.",
                "contact_ph": "What equipment are you looking for?",
                "prod_title": "Products & Services",
                "prod_lead": "Quality equipment and support services tailored for modern healthcare workflows.",
                "products": [
                    {"name": "Digital BP Monitor", "cat": "Diagnostics", "desc": "Accurate home and clinical blood pressure tracking."},
                    {"name": "Pulse Oximeter", "cat": "Monitoring", "desc": "Reliable oxygen saturation and pulse monitoring."},
                    {"name": "Portable ECG Device", "cat": "Cardiology", "desc": "Quick ECG checks with easy report export."},
                    {"name": "Nebulizer Kit", "cat": "Respiratory", "desc": "Efficient aerosol therapy solution for all ages."},
                    {"name": "Suction Unit", "cat": "Critical Care", "desc": "Compact and durable suction support system."},
                    {"name": "Infusion Pump", "cat": "Therapy", "desc": "Controlled medication and fluid delivery."},
                ],
                "testimonials": [
                    {"name": "Dr. L. Carter", "org": "Northside Clinic", "quote": "Excellent support and equipment quality."},
                    {"name": "A. Thompson", "org": "CityCare Hospital", "quote": "Their team helped us choose the right devices smoothly."},
                    {"name": "M. Singh", "org": "HomeCare Plus", "quote": "Dependable products and responsive post-sales service."},
                ],
            },
            "finance": {
                "eyebrow": "Financial Technology Platform",
                "tagline": f"Secure, compliant, and intelligent financial tools. {title} powers your growth.",
                "cta1": "Start Free Trial", "cta2": "See Pricing",
                "footer": "Secure transactions. Clear insights.",
                "about": f"{title} provides fintech infrastructure for payments, compliance, and financial intelligence.",
                "focus": "Security, regulatory compliance, real-time processing, and transparency.",
                "contact_desc": f"Ready to modernize your financial stack? Talk to {title}.",
                "contact_ph": "Tell us about your financial technology needs...",
                "prod_title": "Products & Services",
                "prod_lead": "End-to-end financial infrastructure for compliant, scalable businesses.",
                "products": [
                    {"name": "Payment Gateway", "cat": "Payments", "desc": "Accept payments globally with fraud protection built in."},
                    {"name": "Compliance Engine", "cat": "RegTech", "desc": "Automated KYC/AML checks and regulatory reporting."},
                    {"name": "Invoice Manager", "cat": "Billing", "desc": "Automated invoicing, reminders, and reconciliation."},
                    {"name": "Analytics Dashboard", "cat": "Insights", "desc": "Real-time financial metrics and forecasting."},
                    {"name": "Risk Assessment API", "cat": "Risk", "desc": "ML-powered credit scoring and risk evaluation."},
                    {"name": "Ledger Service", "cat": "Accounting", "desc": "Double-entry ledger with audit trail and multi-currency."},
                ],
                "testimonials": [
                    {"name": "D. Okafor", "org": "PayStream Ltd.", "quote": "Reliable payment processing with excellent developer docs."},
                    {"name": "L. Zhang", "org": "GreenVault Finance", "quote": "Their compliance tools saved us months of manual work."},
                    {"name": "P. Anderson", "org": "TrustBridge Co.", "quote": "Real-time analytics dashboards give us visibility we never had."},
                ],
            },
            "education": {
                "eyebrow": "Education Technology",
                "tagline": f"Empower learners and educators with smart, accessible tools. {title} makes learning effective.",
                "cta1": "Explore Platform", "cta2": "For Educators",
                "footer": "Learn smarter. Grow faster.",
                "about": f"{title} builds learning platforms that adapt to individual needs for better outcomes.",
                "focus": "Accessibility, personalization, engagement, and measurable outcomes.",
                "contact_desc": f"Interested in bringing {title} to your institution? Let us know.",
                "contact_ph": "Tell us about your learning goals...",
                "prod_title": "Platform Features",
                "prod_lead": "Tools designed for modern education \u2014 from classrooms to corporate training.",
                "products": [
                    {"name": "Adaptive Learning Engine", "cat": "Core", "desc": "Personalized learning paths powered by AI."},
                    {"name": "Virtual Classroom", "cat": "Live", "desc": "Interactive video sessions with collaboration tools."},
                    {"name": "Assessment Builder", "cat": "Testing", "desc": "Create, deliver, and auto-grade assessments."},
                    {"name": "Content Library", "cat": "Resources", "desc": "Curated courses and materials across subjects."},
                    {"name": "Progress Tracker", "cat": "Analytics", "desc": "Student performance dashboards for educators."},
                    {"name": "Certification Platform", "cat": "Credentials", "desc": "Issue and verify digital certificates and badges."},
                ],
                "testimonials": [
                    {"name": "Prof. J. Whitfield", "org": "Elm University", "quote": "Student engagement increased 40% after adopting their platform."},
                    {"name": "S. Nakamura", "org": "CodePath Academy", "quote": "The assessment tools save our instructors hours every week."},
                    {"name": "T. Brooks", "org": "K-12 District 5", "quote": "Easy onboarding, great support, and measurable improvements."},
                ],
            },
        }
        return _P.get(btype, _P["tech"])

    def _build_template_files(self, business_title: str, content: Dict, project_dir: str, src_dir: str, components_dir: str, safe_project_name: str) -> Dict[str, str]:
        """Build all React template files using the content preset."""
        npm_name = re.sub(r"[^a-z0-9-]", "-", safe_project_name.lower()).strip("-")

        prods_js = ",\n  ".join(
            "{{ name: '{}', category: '{}', desc: '{}' }}".format(p["name"], p["cat"], p["desc"])
            for p in content["products"]
        )
        tests_js = ",\n  ".join(
            "{{ name: '{}', org: '{}', quote: '{}' }}".format(
                t["name"], t["org"], t["quote"].replace("'", "\\'")
            )
            for t in content["testimonials"]
        )

        bt = business_title  # shorthand

        return {
            os.path.join(project_dir, "package.json"): (
                '{\n  "name": "' + npm_name + '",\n  "private": true,\n  "version": "1.0.0",\n'
                '  "type": "module",\n  "scripts": {\n    "dev": "vite",\n    "build": "vite build",\n    "preview": "vite preview"\n  },\n'
                '  "dependencies": {\n    "react": "^18.3.1",\n    "react-dom": "^18.3.1"\n  },\n'
                '  "devDependencies": {\n    "@vitejs/plugin-react": "^4.3.1",\n    "vite": "^5.4.10"\n  }\n}\n'
            ),
            os.path.join(project_dir, "index.html"): (
                '<!doctype html>\n<html lang="en">\n  <head>\n    <meta charset="UTF-8" />\n'
                '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
                f'    <title>{bt}</title>\n  </head>\n  <body>\n    <div id="root"></div>\n'
                '    <script type="module" src="/src/main.jsx"></script>\n  </body>\n</html>\n'
            ),
            os.path.join(project_dir, "vite.config.js"): (
                "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\n\n"
                "export default defineConfig({\n  plugins: [react()],\n});\n"
            ),
            os.path.join(src_dir, "main.jsx"): (
                "import React from 'react';\nimport { createRoot } from 'react-dom/client';\n"
                "import App from './App';\nimport './styles.css';\n\n"
                "createRoot(document.getElementById('root')).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>\n);\n"
            ),
            os.path.join(src_dir, "App.jsx"): (
                "import React from 'react';\n"
                "import HeroSection from './components/HeroSection';\n"
                "import AboutSection from './components/AboutSection';\n"
                "import ProductsSection from './components/ProductsSection';\n"
                "import TestimonialsSection from './components/TestimonialsSection';\n"
                "import ContactSection from './components/ContactSection';\n\n"
                "export default function App() {\n  return (\n    <div className=\"app\">\n"
                "      <header className=\"site-header\">\n        <div className=\"site-container nav-wrap\">\n"
                f'          <div className="brand">{bt}</div>\n'
                '          <nav>\n            <a href="#home">Home</a>\n'
                '            <a href="#about">About</a>\n            <a href="#products">Products</a>\n'
                '            <a href="#testimonials">Testimonials</a>\n            <a href="#contact">Contact</a>\n'
                "          </nav>\n        </div>\n      </header>\n\n      <main>\n"
                f'        <HeroSection businessTitle="{bt}" />\n'
                "        <AboutSection />\n        <ProductsSection />\n"
                "        <TestimonialsSection />\n        <ContactSection />\n"
                "      </main>\n\n      <footer className=\"site-footer\">\n"
                "        <div className=\"site-container footer-wrap\">\n"
                f"          <p>&copy; {{new Date().getFullYear()}} {bt}. All rights reserved.</p>\n"
                f"          <p>{content['footer']}</p>\n"
                "        </div>\n      </footer>\n    </div>\n  );\n}\n"
            ),
            os.path.join(components_dir, "HeroSection.jsx"): (
                "import React from 'react';\n\n"
                "export default function HeroSection({ businessTitle }) {\n  return (\n"
                '    <section id="home" className="hero-section">\n      <div className="site-container hero-grid">\n        <div>\n'
                f'          <p className="eyebrow">{content["eyebrow"]}</p>\n'
                "          <h1>{businessTitle}</h1>\n          <p>\n"
                f'            {content["tagline"]}\n'
                "          </p>\n          <div className=\"hero-actions\">\n"
                f'            <a href="#products" className="btn btn-primary">{content["cta1"]}</a>\n'
                f'            <a href="#contact" className="btn btn-secondary">{content["cta2"]}</a>\n'
                "          </div>\n        </div>\n        <div className=\"hero-card\">\n"
                "          <h3>Why teams choose us</h3>\n          <ul>\n"
                "            <li>Production-ready from day one</li>\n"
                "            <li>Responsive support and documentation</li>\n"
                "            <li>Trusted by leading organizations</li>\n"
                "          </ul>\n        </div>\n      </div>\n    </section>\n  );\n}\n"
            ),
            os.path.join(components_dir, "AboutSection.jsx"): (
                "import React from 'react';\n\n"
                "export default function AboutSection() {\n  return (\n"
                '    <section id="about" className="section">\n      <div className="site-container section-grid">\n        <div>\n'
                f'          <h2>About Us</h2>\n          <p>\n            {content["about"]}\n          </p>\n'
                "        </div>\n        <div className=\"highlight-box\">\n"
                f'          <h4>Our Focus</h4>\n          <p>{content["focus"]}</p>\n'
                "        </div>\n      </div>\n    </section>\n  );\n}\n"
            ),
            os.path.join(components_dir, "ProductsSection.jsx"): (
                "import React from 'react';\n\nconst products = [\n  " + prods_js + "\n];\n\n"
                "export default function ProductsSection() {\n  return (\n"
                '    <section id="products" className="section section-soft">\n      <div className="site-container">\n'
                f'        <h2>{content["prod_title"]}</h2>\n        <p className="section-lead">\n'
                f'          {content["prod_lead"]}\n        </p>\n'
                "        <div className=\"cards-grid\">\n          {products.map((item) => (\n"
                "            <article key={item.name} className=\"service-card\">\n"
                "              <p className=\"chip\">{item.category}</p>\n"
                "              <h3>{item.name}</h3>\n              <p>{item.desc}</p>\n"
                "            </article>\n          ))}\n        </div>\n"
                "      </div>\n    </section>\n  );\n}\n"
            ),
            os.path.join(components_dir, "TestimonialsSection.jsx"): (
                "import React from 'react';\n\nconst testimonials = [\n  " + tests_js + "\n];\n\n"
                "export default function TestimonialsSection() {\n  return (\n"
                '    <section id="testimonials" className="section">\n      <div className="site-container">\n'
                "        <h2>Testimonials</h2>\n        <div className=\"cards-grid\">\n"
                "          {testimonials.map((item) => (\n"
                "            <article key={item.name} className=\"testimonial-card\">\n"
                '              <p>"{item.quote}"</p>\n              <h4>{item.name}</h4>\n'
                "              <span>{item.org}</span>\n            </article>\n          ))}\n"
                "        </div>\n      </div>\n    </section>\n  );\n}\n"
            ),
            os.path.join(components_dir, "ContactSection.jsx"): (
                "import React from 'react';\n\n"
                "export default function ContactSection() {\n  return (\n"
                '    <section id="contact" className="section section-soft">\n      <div className="site-container section-grid">\n        <div>\n'
                f'          <h2>Get In Touch</h2>\n          <p>\n            {content["contact_desc"]}\n          </p>\n'
                "        </div>\n        <form className=\"contact-form\" onSubmit={(event) => event.preventDefault()}>\n"
                '          <input type="text" placeholder="Your Name" required />\n'
                '          <input type="email" placeholder="Email Address" required />\n'
                '          <input type="text" placeholder="Organization" />\n'
                f'          <textarea placeholder="{content["contact_ph"]}" rows={{5}} required />\n'
                '          <button type="submit" className="btn btn-primary">Send Inquiry</button>\n'
                "        </form>\n      </div>\n    </section>\n  );\n}\n"
            ),
            os.path.join(src_dir, "styles.css"): self._get_styles_css(),
            os.path.join(project_dir, "README.md"): (
                f"# {bt}\n\nGenerated by Mission Coding automation.\n\n"
                f"## Run\n\n1. `cd {safe_project_name}`\n2. `npm install`\n3. `npm run dev`\n"
            ),
        }

    def _get_styles_css(self) -> str:
        """Return the CSS stylesheet for the generated site."""
        return """:root {
  font-family: Inter, Segoe UI, Roboto, Arial, sans-serif;
  color: #0f172a;
  background: #f5fbff;
}
* { box-sizing: border-box; }
html, body, #root { margin: 0; min-height: 100%; }
body { background: #f5fbff; color: #0f172a; }
a { color: inherit; }
.site-container { width: min(1120px, 92%); margin: 0 auto; }
.site-header { position: sticky; top: 0; z-index: 20; background: rgba(255,255,255,0.95); backdrop-filter: blur(6px); border-bottom: 1px solid #d6e6ef; }
.nav-wrap { display: flex; justify-content: space-between; align-items: center; min-height: 72px; }
.brand { font-weight: 800; color: #0d4f8a; }
nav { display: flex; gap: 1rem; }
nav a { text-decoration: none; font-weight: 600; color: #1e293b; }
nav a:hover { color: #0d4f8a; }
.hero-section { padding: 4.2rem 0 3.2rem; background: linear-gradient(135deg, #0d4f8a, #1591d1 60%, #22a67c); color: #ffffff; }
.hero-grid { display: grid; grid-template-columns: 1.3fr 1fr; gap: 1.5rem; align-items: start; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; opacity: 0.88; }
.hero-grid h1 { margin: 0.5rem 0 1rem; font-size: clamp(1.8rem, 3vw, 2.8rem); }
.hero-grid p { margin: 0; line-height: 1.7; }
.hero-actions { margin-top: 1.25rem; display: flex; flex-wrap: wrap; gap: 0.75rem; }
.hero-card { background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.38); border-radius: 14px; padding: 1rem 1.1rem; }
.hero-card h3 { margin: 0 0 0.7rem; }
.hero-card ul { margin: 0; padding-left: 1rem; line-height: 1.7; }
.section { padding: 3.3rem 0; }
.section-soft { background: #ecf7ff; }
.section-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 1.2rem; align-items: start; }
.section h2 { margin-top: 0; color: #0f2f4a; }
.section-lead { margin-top: -0.2rem; color: #35516a; }
.highlight-box { background: #ffffff; border: 1px solid #d6e6ef; border-radius: 12px; padding: 1rem; }
.cards-grid { margin-top: 1rem; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
.service-card, .testimonial-card { background: #ffffff; border: 1px solid #d6e6ef; border-radius: 12px; padding: 1rem; }
.service-card h3, .testimonial-card h4 { margin: 0.25rem 0 0.45rem; }
.chip { display: inline-block; margin: 0; border-radius: 999px; padding: 0.2rem 0.55rem; font-size: 0.72rem; font-weight: 700; background: #dff3ff; color: #0d4f8a; }
.testimonial-card span { color: #4b647a; font-size: 0.92rem; }
.contact-form { background: #ffffff; border: 1px solid #d6e6ef; border-radius: 12px; padding: 1rem; display: grid; gap: 0.8rem; }
.contact-form input, .contact-form textarea { width: 100%; border: 1px solid #c6dae8; border-radius: 8px; padding: 0.72rem 0.78rem; font: inherit; }
.btn { display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; padding: 0.72rem 1rem; font-weight: 700; text-decoration: none; border: 1px solid transparent; cursor: pointer; }
.btn-primary { background: #0d4f8a; color: #ffffff; }
.btn-secondary { background: rgba(255,255,255,0.22); color: #ffffff; border-color: rgba(255,255,255,0.5); }
.site-footer { border-top: 1px solid #d6e6ef; background: #ffffff; }
.footer-wrap { min-height: 72px; display: flex; justify-content: space-between; align-items: center; gap: 1rem; color: #4a6479; }
@media (max-width: 900px) {
  .hero-grid, .section-grid { grid-template-columns: 1fr; }
  .cards-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .nav-wrap { flex-direction: column; align-items: flex-start; padding: 0.75rem 0; }
  nav { flex-wrap: wrap; gap: 0.65rem; }
}
@media (max-width: 620px) {
  .cards-grid { grid-template-columns: 1fr; }
  .footer-wrap { flex-direction: column; align-items: flex-start; padding: 0.8rem 0; }
}
"""

    # ==================== SCAFFOLD ====================

    async def _scaffold_react_website(self, params: Dict[str, Any]) -> SkillResult:
        try:
            goal = params.get("goal", "")
            project_name = params.get("project_name") or "react_business_site"
            safe_project_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", project_name).strip("_") or "react_business_site"

            install_dependencies = params.get("install_dependencies", True)
            run_dev_server = params.get("run_dev_server", True)
            open_in_editor = params.get("open_in_editor", True)

            workspace_root = os.getcwd()
            output_root = params.get("output_root") or os.path.join(workspace_root, "generated")
            project_dir = os.path.join(output_root, safe_project_name)
            src_dir = os.path.join(project_dir, "src")
            components_dir = os.path.join(src_dir, "components")

            os.makedirs(components_dir, exist_ok=True)

            # ---------- Extract business name ----------
            business_title = "Tech Startup"
            business_match = re.search(r"for\s+(?:my\s+)?([A-Za-z0-9\s&-]+?)\s+(?:business|company|store)", goal, re.IGNORECASE)
            if business_match:
                business_title = business_match.group(1).strip().title()
            else:
                startup_called_match = re.search(r"startup\s+called\s+([A-Za-z0-9\s&._-]+)", goal, re.IGNORECASE)
                landing_for_match = re.search(r"landing\s+page\s+for\s+([A-Za-z0-9\s&._-]+?)(?:,|\.|\band\b|$)", goal, re.IGNORECASE)
                extracted_name = None
                if startup_called_match:
                    extracted_name = startup_called_match.group(1).strip().rstrip(".,")
                elif landing_for_match:
                    extracted_name = landing_for_match.group(1).strip().rstrip(".,")

                if extracted_name and extracted_name.lower() not in {"a startup", "startup", "the startup"}:
                    business_title = extracted_name

            # ---------- Detect type & generate content ----------
            btype = self._detect_business_type(business_title)
            content_preset = self._get_content_preset(business_title, btype)

            files = self._build_template_files(
                business_title, content_preset, project_dir, src_dir,
                components_dir, safe_project_name
            )


            created_files = []
            for path, content in files.items():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as file_obj:
                    file_obj.write(content)
                created_files.append(path)

            install_output = None
            if install_dependencies:
                install_output = await self._run_command_with_timeout("npm install", project_dir, timeout_seconds=1200)
                if not install_output["success"]:
                    return SkillResult(
                        success=False,
                        error=f"Project scaffolded but dependency installation failed: {install_output.get('stderr') or install_output.get('stdout')}",
                        data={
                            "project_path": project_dir,
                            "files_created": created_files,
                            "install_output": install_output,
                        },
                    )

            dev_server = None
            if run_dev_server:
                preferred_port = params.get("port")
                port = int(preferred_port) if isinstance(preferred_port, int) else self._find_free_port(5173)
                dev_server = self._start_vite_dev_server(project_dir, port)
                if not dev_server["success"]:
                    return SkillResult(
                        success=False,
                        error=f"Project created but failed to start dev server: {dev_server.get('error', 'unknown error')}",
                        data={
                            "project_path": project_dir,
                            "files_created": created_files,
                            "install_output": install_output,
                            "dev_server": dev_server,
                        },
                    )

            editor_opened = False
            if open_in_editor:
                editor_opened = self._open_in_vscode(project_dir)

            next_steps = [f"cd {project_dir}", "npm run dev"]
            if not install_dependencies:
                next_steps.insert(1, "npm install")

            return SkillResult(
                success=True,
                message=f"React website project scaffolded at {project_dir}",
                data={
                    "project_path": project_dir,
                    "files_created": created_files,
                    "editor_opened": editor_opened,
                    "install_output": install_output,
                    "dev_server": dev_server,
                    "local_url": dev_server.get("url") if isinstance(dev_server, dict) else None,
                    "next_steps": next_steps,
                },
            )
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    async def _run_command_with_timeout(self, command: str, cwd: str, timeout_seconds: int = 600) -> Dict[str, Any]:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
            return {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": stdout.decode(errors="ignore").strip(),
                "stderr": stderr.decode(errors="ignore").strip(),
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout_seconds} seconds",
            }
        except Exception as exc:
            return {
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": str(exc),
            }

    def _find_free_port(self, start_port: int = 5173, attempts: int = 30) -> int:
        for offset in range(attempts):
            candidate = start_port + offset
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.25)
                if sock.connect_ex(("127.0.0.1", candidate)) != 0:
                    return candidate
        return start_port

    def _start_vite_dev_server(self, project_dir: str, port: int) -> Dict[str, Any]:
        log_path = os.path.join(project_dir, "dev_server.log")
        default_url = f"http://127.0.0.1:{port}"
        command = f"npm run dev -- --host 127.0.0.1 --port {port}"

        try:
            log_file = open(log_path, "a", encoding="utf-8")
            process = subprocess.Popen(
                command,
                cwd=project_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=True,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except Exception as exc:
            return {"success": False, "error": str(exc), "url": None, "log_path": log_path}

        url_pattern = re.compile(r"https?://(?:localhost|127\.0\.0\.1):\d+")
        deadline = time.time() + 35
        while time.time() < deadline:
            if process.poll() is not None:
                return {
                    "success": False,
                    "error": f"Dev server exited early. {self._tail_file(log_path)}",
                    "url": None,
                    "pid": process.pid,
                    "log_path": log_path,
                }

            tail = self._tail_file(log_path)
            match = url_pattern.search(tail)
            if match:
                return {
                    "success": True,
                    "url": match.group(0).replace("localhost", "127.0.0.1"),
                    "pid": process.pid,
                    "log_path": log_path,
                }
            time.sleep(1)

        return {
            "success": True,
            "url": default_url,
            "pid": process.pid,
            "log_path": log_path,
        }

    def _tail_file(self, path: str, max_chars: int = 5000) -> str:
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file_obj:
                content = file_obj.read()
            return content[-max_chars:]
        except Exception:
            return ""

    def _open_in_vscode(self, project_dir: str) -> bool:
        # Intentionally do not launch external VS Code.
        # Electron renderer auto-opens the built-in code editor based on mission runtime signals.
        return os.path.isdir(project_dir)

    async def _read_file(self, path: str) -> SkillResult:
        try:
            if not path or not os.path.exists(path):
                return SkillResult(success=False, error="File not found")
            with open(path, "r", encoding="utf-8") as file_obj:
                content = file_obj.read()
            return SkillResult(success=True, message=content, data={"content": content})
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    async def _write_file(self, path: str, content: str) -> SkillResult:
        try:
            if not path:
                return SkillResult(success=False, error="Path is required")
            parent_dir = os.path.dirname(path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as file_obj:
                file_obj.write(content or "")
            return SkillResult(success=True, message=f"File written to {path}")
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    async def _list_files(self, directory: str) -> SkillResult:
        try:
            entries = [entry.name for entry in os.scandir(directory)]
            return SkillResult(success=True, message="\n".join(entries), data={"files": entries})
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    async def _run_command(self, command: str, cwd: str) -> SkillResult:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode(errors="ignore").strip()
            error_text = stderr.decode(errors="ignore").strip()

            if process.returncode == 0:
                return SkillResult(success=True, message=output, data={"stdout": output, "stderr": error_text})
            return SkillResult(success=False, error=f"Command failed: {error_text}", data={"stdout": output, "stderr": error_text})
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))
