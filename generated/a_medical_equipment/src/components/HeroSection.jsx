import React from 'react';

export default function HeroSection({ businessTitle }) {
  return (
    <section id="home" className="hero-section">
      <div className="site-container hero-grid">
        <div>
          <p className="eyebrow">Healthcare Solutions Partner</p>
          <h1>{businessTitle}</h1>
          <p>
            Professional-grade devices and services for hospitals, clinics, and care providers. A Medical Equipment delivers quality you can trust.
          </p>
          <div className="hero-actions">
            <a href="#products" className="btn btn-primary">Browse Products</a>
            <a href="#contact" className="btn btn-secondary">Request a Quote</a>
          </div>
        </div>
        <div className="hero-card">
          <h3>Why teams choose us</h3>
          <ul>
            <li>Production-ready from day one</li>
            <li>Responsive support and documentation</li>
            <li>Trusted by leading organizations</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
