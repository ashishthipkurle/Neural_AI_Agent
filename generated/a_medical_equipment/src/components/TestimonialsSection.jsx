import React from 'react';

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
