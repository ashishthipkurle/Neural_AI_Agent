import React from 'react';

export default function ContactSection() {
  return (
    <section id="contact" className="section section-soft">
      <div className="site-container section-grid">
        <div>
          <h2>Get In Touch</h2>
          <p>
            Tell us what equipment you need and the A Medical Equipment team will respond with options.
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
