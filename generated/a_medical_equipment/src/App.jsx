import React from 'react';
import HeroSection from './components/HeroSection';
import AboutSection from './components/AboutSection';
import ProductsSection from './components/ProductsSection';
import TestimonialsSection from './components/TestimonialsSection';
import ContactSection from './components/ContactSection';

export default function App() {
  return (
    <div className="app">
      <header className="site-header">
        <div className="site-container nav-wrap">
          <div className="brand">A Medical Equipment Business</div>
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
        <HeroSection businessTitle="A Medical Equipment Business" />
        <AboutSection />
        <ProductsSection />
        <TestimonialsSection />
        <ContactSection />
      </main>

      <footer className="site-footer">
        <div className="site-container footer-wrap">
          <p>© {new Date().getFullYear()} A Medical Equipment Business. All rights reserved.</p>
          <p>Reliable equipment. Trusted care.</p>
        </div>
      </footer>
    </div>
  );
}
