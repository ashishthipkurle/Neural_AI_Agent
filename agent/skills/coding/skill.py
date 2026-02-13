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

    async def _scaffold_react_website(self, params: Dict[str, Any]) -> SkillResult:
        try:
            goal = params.get("goal", "")
            project_name = params.get("project_name") or "react_business_site"
            safe_project_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", project_name).strip("_") or "react_business_site"

            install_dependencies = params.get("install_dependencies", True)
            run_dev_server = params.get("run_dev_server", True)
            open_in_editor = params.get("open_in_editor", False)

            workspace_root = os.getcwd()
            output_root = params.get("output_root") or os.path.join(workspace_root, "generated")
            project_dir = os.path.join(output_root, safe_project_name)
            src_dir = os.path.join(project_dir, "src")
            components_dir = os.path.join(src_dir, "components")

            os.makedirs(components_dir, exist_ok=True)

            business_title = "Medical Equipment Business"
            business_match = re.search(r"for\s+(?:my\s+)?([A-Za-z0-9\s&-]+?)\s+(?:business|company|store)", goal, re.IGNORECASE)
            if business_match:
                business_title = business_match.group(1).strip().title() + " Business"

            files = {
                os.path.join(project_dir, "package.json"): """{
  "name": "react-medical-equipment-site",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.10"
  }
}
""",
                os.path.join(project_dir, "index.html"): f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{business_title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
                os.path.join(project_dir, "vite.config.js"): """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
});
""",
                os.path.join(src_dir, "main.jsx"): """import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
""",
                os.path.join(src_dir, "App.jsx"): f"""import React from 'react';
import HeroSection from './components/HeroSection';
import AboutSection from './components/AboutSection';
import ProductsSection from './components/ProductsSection';
import TestimonialsSection from './components/TestimonialsSection';
import ContactSection from './components/ContactSection';

export default function App() {{
  return (
    <div className="app">
      <header className="site-header">
        <div className="site-container nav-wrap">
          <div className="brand">{business_title}</div>
          <nav>
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#products">Products</a>
            <a href="#testimonials">Testimonials</a>
            <a href="#contact">Contact</a>
          </nav>
        </div>
      </header>

      <main>
        <HeroSection businessTitle="{business_title}" />
        <AboutSection />
        <ProductsSection />
        <TestimonialsSection />
        <ContactSection />
      </main>

      <footer className="site-footer">
        <div className="site-container footer-wrap">
          <p>© {{new Date().getFullYear()}} {business_title}. All rights reserved.</p>
          <p>Reliable equipment. Trusted care.</p>
        </div>
      </footer>
    </div>
  );
}}
""",
                os.path.join(components_dir, "HeroSection.jsx"): """import React from 'react';

export default function HeroSection({ businessTitle }) {
  return (
    <section id="home" className="hero-section">
      <div className="site-container hero-grid">
        <div>
          <p className="eyebrow">Medical Equipment Partner</p>
          <h1>{businessTitle}</h1>
          <p>
            Professional-grade devices for hospitals, clinics, and home care providers.
            Fast delivery, verified quality, and responsive technical support.
          </p>
          <div className="hero-actions">
            <a href="#products" className="btn btn-primary">Browse Products</a>
            <a href="#contact" className="btn btn-secondary">Request a Quote</a>
          </div>
        </div>
        <div className="hero-card">
          <h3>Why teams choose us</h3>
          <ul>
            <li>Certified product sourcing</li>
            <li>On-time delivery across regions</li>
            <li>Post-sales support and guidance</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
""",
                os.path.join(components_dir, "AboutSection.jsx"): """import React from 'react';

export default function AboutSection() {
  return (
    <section id="about" className="section">
      <div className="site-container section-grid">
        <div>
          <h2>About Us</h2>
          <p>
            We help healthcare providers equip their facilities with dependable devices
            and transparent service. Our team works with trusted manufacturers and
            provides assistance from selection to post-installation support.
          </p>
        </div>
        <div className="highlight-box">
          <h4>Our Focus</h4>
          <p>Patient safety, compliance, product reliability, and long-term value.</p>
        </div>
      </div>
    </section>
  );
}
""",
                os.path.join(components_dir, "ProductsSection.jsx"): """import React from 'react';

const products = [
  { name: 'Digital BP Monitor', category: 'Diagnostics', desc: 'Accurate home and clinical blood pressure tracking.' },
  { name: 'Pulse Oximeter', category: 'Monitoring', desc: 'Reliable oxygen saturation and pulse monitoring.' },
  { name: 'Portable ECG Device', category: 'Cardiology', desc: 'Quick ECG checks with easy report export.' },
  { name: 'Nebulizer Kit', category: 'Respiratory', desc: 'Efficient aerosol therapy solution for all ages.' },
  { name: 'Suction Unit', category: 'Critical Care', desc: 'Compact and durable suction support system.' },
  { name: 'Infusion Pump', category: 'Therapy', desc: 'Controlled medication and fluid delivery.' },
];

export default function ProductsSection() {
  return (
    <section id="products" className="section section-soft">
      <div className="site-container">
        <h2>Products & Services</h2>
        <p className="section-lead">
          Quality equipment and support services tailored for modern healthcare workflows.
        </p>
        <div className="cards-grid">
          {products.map((item) => (
            <article key={item.name} className="service-card">
              <p className="chip">{item.category}</p>
              <h3>{item.name}</h3>
              <p>{item.desc}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
""",
                os.path.join(components_dir, "TestimonialsSection.jsx"): """import React from 'react';

const testimonials = [
  {
    name: 'Dr. L. Carter',
    org: 'Northside Clinic',
    quote: 'Excellent support and equipment quality. Delivery timelines were exactly as committed.'
  },
  {
    name: 'A. Thompson',
    org: 'CityCare Hospital',
    quote: 'Their team helped us choose the right devices and handled onboarding smoothly.'
  },
  {
    name: 'M. Singh',
    org: 'HomeCare Plus',
    quote: 'Dependable products and responsive post-sales service every time.'
  }
];

export default function TestimonialsSection() {
  return (
    <section id="testimonials" className="section">
      <div className="site-container">
        <h2>Testimonials</h2>
        <div className="cards-grid">
          {testimonials.map((item) => (
            <article key={item.name} className="testimonial-card">
              <p>“{item.quote}”</p>
              <h4>{item.name}</h4>
              <span>{item.org}</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
""",
                os.path.join(components_dir, "ContactSection.jsx"): """import React from 'react';

export default function ContactSection() {
  return (
    <section id="contact" className="section section-soft">
      <div className="site-container section-grid">
        <div>
          <h2>Contact Form</h2>
          <p>
            Tell us what equipment you need and our team will get back with options,
            pricing, and delivery details.
          </p>
        </div>
        <form className="contact-form" onSubmit={(event) => event.preventDefault()}>
          <input type="text" placeholder="Your Name" required />
          <input type="email" placeholder="Email Address" required />
          <input type="text" placeholder="Organization" />
          <textarea placeholder="What equipment are you looking for?" rows={5} required />
          <button type="submit" className="btn btn-primary">Send Inquiry</button>
        </form>
      </div>
    </section>
  );
}
""",
                os.path.join(src_dir, "styles.css"): """:root {
  font-family: Inter, Segoe UI, Roboto, Arial, sans-serif;
  color: #0f172a;
  background: #f5fbff;
}

* {
  box-sizing: border-box;
}

html, body, #root {
  margin: 0;
  min-height: 100%;
}

body {
  background: #f5fbff;
  color: #0f172a;
}

a {
  color: inherit;
}

.site-container {
  width: min(1120px, 92%);
  margin: 0 auto;
}

.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(6px);
  border-bottom: 1px solid #d6e6ef;
}

.nav-wrap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 72px;
}

.brand {
  font-weight: 800;
  color: #0d4f8a;
}

nav {
  display: flex;
  gap: 1rem;
}

nav a {
  text-decoration: none;
  font-weight: 600;
  color: #1e293b;
}

nav a:hover {
  color: #0d4f8a;
}

.hero-section {
  padding: 4.2rem 0 3.2rem;
  background: linear-gradient(135deg, #0d4f8a, #1591d1 60%, #22a67c);
  color: #ffffff;
}

.hero-grid {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 1.5rem;
  align-items: start;
}

.eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
  opacity: 0.88;
}

.hero-grid h1 {
  margin: 0.5rem 0 1rem;
  font-size: clamp(1.8rem, 3vw, 2.8rem);
}

.hero-grid p {
  margin: 0;
  line-height: 1.7;
}

.hero-actions {
  margin-top: 1.25rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.hero-card {
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.38);
  border-radius: 14px;
  padding: 1rem 1.1rem;
}

.hero-card h3 {
  margin: 0 0 0.7rem;
}

.hero-card ul {
  margin: 0;
  padding-left: 1rem;
  line-height: 1.7;
}

.section {
  padding: 3.3rem 0;
}

.section-soft {
  background: #ecf7ff;
}

.section-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 1.2rem;
  align-items: start;
}

.section h2 {
  margin-top: 0;
  color: #0f2f4a;
}

.section-lead {
  margin-top: -0.2rem;
  color: #35516a;
}

.highlight-box {
  background: #ffffff;
  border: 1px solid #d6e6ef;
  border-radius: 12px;
  padding: 1rem;
}

.cards-grid {
  margin-top: 1rem;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.service-card,
.testimonial-card {
  background: #ffffff;
  border: 1px solid #d6e6ef;
  border-radius: 12px;
  padding: 1rem;
}

.service-card h3,
.testimonial-card h4 {
  margin: 0.25rem 0 0.45rem;
}

.chip {
  display: inline-block;
  margin: 0;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 700;
  background: #dff3ff;
  color: #0d4f8a;
}

.testimonial-card span {
  color: #4b647a;
  font-size: 0.92rem;
}

.contact-form {
  background: #ffffff;
  border: 1px solid #d6e6ef;
  border-radius: 12px;
  padding: 1rem;
  display: grid;
  gap: 0.8rem;
}

.contact-form input,
.contact-form textarea {
  width: 100%;
  border: 1px solid #c6dae8;
  border-radius: 8px;
  padding: 0.72rem 0.78rem;
  font: inherit;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  padding: 0.72rem 1rem;
  font-weight: 700;
  text-decoration: none;
  border: 1px solid transparent;
  cursor: pointer;
}

.btn-primary {
  background: #0d4f8a;
  color: #ffffff;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.22);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.5);
}

.site-footer {
  border-top: 1px solid #d6e6ef;
  background: #ffffff;
}

.footer-wrap {
  min-height: 72px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  color: #4a6479;
}

@media (max-width: 900px) {
  .hero-grid,
  .section-grid {
    grid-template-columns: 1fr;
  }

  .cards-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .nav-wrap {
    flex-direction: column;
    align-items: flex-start;
    padding: 0.75rem 0;
  }

  nav {
    flex-wrap: wrap;
    gap: 0.65rem;
  }
}

@media (max-width: 620px) {
  .cards-grid {
    grid-template-columns: 1fr;
  }

  .footer-wrap {
    flex-direction: column;
    align-items: flex-start;
    padding: 0.8rem 0;
  }
}
""",
                os.path.join(project_dir, "README.md"): f"""# {business_title}

Generated by Mission Coding automation.

## Run

1. `cd {safe_project_name}`
2. `npm install`
3. `npm run dev`
""",
            }

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
        try:
            subprocess.Popen(["code", project_dir], shell=False)
            return True
        except Exception:
            try:
                # Windows fallback when `code` is not on PATH.
                subprocess.Popen(
                    ["cmd", "/c", "start", "", "code", project_dir],
                    shell=False,
                )
                return True
            except Exception:
                return False

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
