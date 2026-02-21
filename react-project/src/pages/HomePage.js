import React from 'react';
import './HomePage.css';

const HomePage = () => {
  return (
    <div className="medical-homepage">
      {/* Header Section */}
      <header className="medical-header">
        <div className="container">
          <div className="header-content">
            <div className="logo">
              <h1>MediCare+</h1>
              <p>Advanced Healthcare Solutions</p>
            </div>
            <nav className="main-nav">
              <ul>
                <li><a href="#home">Home</a></li>
                <li><a href="#services">Services</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
              </ul>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="container">
          <div className="hero-content">
            <h1>Your Health is Our Priority</h1>
            <p>Providing exceptional medical care with compassion and cutting-edge technology</p>
            <div className="cta-buttons">
              <button className="btn primary-btn">Book Appointment</button>
              <button className="btn secondary-btn">Learn More</button>
            </div>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section className="services-section">
        <div className="container">
          <h2>Our Medical Services</h2>
          <div className="services-grid">
            <div className="service-card">
              <div className="icon">🩺</div>
              <h3>Primary Care</h3>
              <p>Comprehensive healthcare for all ages with focus on prevention and wellness.</p>
            </div>
            <div className="service-card">
              <div className="icon">❤️</div>
              <h3>Cardiology</h3>
              <p>Advanced cardiac care with state-of-the-art diagnostic and treatment options.</p>
            </div>
            <div className="service-card">
              <div className="icon">🧠</div>
              <h3>Neurology</h3>
              <p>Specialized care for disorders of the brain, spine, and nervous system.</p>
            </div>
            <div className="service-card">
              <div className="icon">👶</div>
              <h3>Pediatrics</h3>
              <p>Dedicated healthcare for infants, children, and adolescents.</p>
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="about-section">
        <div className="container">
          <div className="about-content">
            <div className="about-text">
              <h2>Why Choose MediCare+</h2>
              <p>With over 20 years of experience, our team of board-certified physicians provides personalized care tailored to each patient's unique needs.</p>
              <ul>
                <li>24/7 Emergency Services</li>
                <li>Board Certified Specialists</li>
                <li>Cutting-Edge Medical Technology</li>
                <li>Comprehensive Care Approach</li>
              </ul>
            </div>
            <div className="about-image">
              <div className="image-placeholder">Medical Facility Image</div>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="testimonials-section">
        <div className="container">
          <h2>Patient Testimonials</h2>
          <div className="testimonials-grid">
            <div className="testimonial-card">
              <p>"The care I received was exceptional. The staff was attentive and professional throughout my treatment."</p>
              <h4>- Sarah Johnson</h4>
            </div>
            <div className="testimonial-card">
              <p>"Dr. Smith took time to listen and provided a treatment plan that worked perfectly for my condition."</p>
              <h4>- Michael Thompson</h4>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="contact-section">
        <div className="container">
          <h2>Contact Us</h2>
          <div className="contact-content">
            <div className="contact-info">
              <div className="info-item">
                <h3>📍 Address</h3>
                <p>123 Medical Drive<br />Health City, HC 12345</p>
              </div>
              <div className="info-item">
                <h3>📞 Phone</h3>
                <p>(123) 456-7890</p>
              </div>
              <div className="info-item">
                <h3>✉️ Email</h3>
                <p>info@medicareplus.com</p>
              </div>
            </div>
            <div className="contact-form">
              <form>
                <input type="text" placeholder="Your Name" required />
                <input type="email" placeholder="Your Email" required />
                <textarea placeholder="Your Message" rows="5"></textarea>
                <button type="submit" className="btn primary-btn">Send Message</button>
              </form>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="medical-footer">
        <div className="container">
          <p>&copy; 2023 MediCare+. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;