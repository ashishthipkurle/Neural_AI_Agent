import React from 'react';

const products = [
  { name: 'Digital BP Monitor', category: 'Diagnostics', desc: 'Accurate home and clinical blood pressure tracking.' },
  { name: 'Pulse Oximeter', category: 'Monitoring', desc: 'Reliable oxygen saturation and pulse monitoring.' },
  { name: 'Portable ECG Device', category: 'Cardiology', desc: 'Quick ECG checks with easy report export.' },
  { name: 'Nebulizer Kit', category: 'Respiratory', desc: 'Efficient aerosol therapy solution for all ages.' },
  { name: 'Suction Unit', category: 'Critical Care', desc: 'Compact and durable suction support system.' },
  { name: 'Infusion Pump', category: 'Therapy', desc: 'Controlled medication and fluid delivery.' }
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
