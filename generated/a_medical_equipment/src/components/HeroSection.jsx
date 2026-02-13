import React from 'react';

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
