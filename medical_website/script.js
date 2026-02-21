// Sample product data
const products = [
    {
        id: 1,
        name: "Digital Surgical Kit",
        category: "surgical",
        brand: "meditech",
        price: 2499.99,
        description: "Complete set of precision surgical instruments with digital tracking.",
        rating: 4.8,
        reviews: 124
    },
    {
        id: 2,
        name: "MRI Scanner Pro",
        category: "imaging",
        brand: "healthpro",
        price: 14999.99,
        description: "High-resolution MRI scanner with advanced imaging capabilities.",
        rating: 4.9,
        reviews: 89
    },
    {
        id: 3,
        name: "Lab Centrifuge X100",
        category: "laboratory",
        brand: "bioadvance",
        price: 3299.50,
        description: "High-speed centrifuge for laboratory sample processing.",
        rating: 4.6,
        reviews: 67
    },
    {
        id: 4,
        name: "Ultrasound Diagnostic System",
        category: "diagnostic",
        brand: "precision",
        price: 8999.00,
        description: "Portable ultrasound system with real-time imaging.",
        rating: 4.7,
        reviews: 142
    },
    {
        id: 5,
        name: "Laser Surgery Tool",
        category: "surgical",
        brand: "meditech",
        price: 5499.99,
        description: "Precision laser tool for minimally invasive procedures.",
        rating: 4.5,
        reviews: 93
    },
    {
        id: 6,
        name: "Blood Analysis Machine",
        category: "diagnostic",
        brand: "healthpro",
        price: 7200.00,
        description: "Automated blood analysis system with rapid results.",
        rating: 4.8,
        reviews: 112
    },
    {
        id: 7,
        name: "Microscope Lab Station",
        category: "laboratory",
        brand: "bioadvance",
        price: 4500.75,
        description: "Professional microscope station with digital capture.",
        rating: 4.4,
        reviews: 78
    },
    {
        id: 8,
        name: "CT Scan Elite",
        category: "imaging",
        brand: "precision",
        price: 18999.99,
        description: "Advanced CT scanning system with 3D reconstruction.",
        rating: 4.9,
        reviews: 56
    },
    {
        id: 9,
        name: "Endoscopy System",
        category: "diagnostic",
        brand: "meditech",
        price: 12500.00,
        description: "High-definition endoscopy system for internal examinations.",
        rating: 4.7,
        reviews: 95
    },
    {
        id: 10,
        name: "Autoclave Sterilizer",
        category: "surgical",
        brand: "healthpro",
        price: 3800.25,
        description: "Medical-grade autoclave for instrument sterilization.",
        rating: 4.6,
        reviews: 82
    },
    {
        id: 11,
        name: "Spectrophotometer",
        category: "laboratory",
        brand: "precision",
        price: 2999.99,
        description: "UV-VIS spectrophotometer for chemical analysis.",
        rating: 4.3,
        reviews: 45
    },
    {
        id: 12,
        name: "X-Ray Imaging System",
        category: "imaging",
        brand: "bioadvance",
        price: 15500.50,
        description: "Digital X-ray system with instant image processing.",
        rating: 4.8,
        reviews: 103
    }
];

// DOM elements
const productGrid = document.getElementById('product-grid');
const categoryFilter = document.getElementById('category');
const brandFilter = document.getElementById('brand');
const priceRangeFilter = document.getElementById('price-range');
const resetButton = document.getElementById('reset-filters');

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    renderProducts(products);
    
    // Add event listeners
    categoryFilter.addEventListener('change', filterProducts);
    brandFilter.addEventListener('change', filterProducts);
    priceRangeFilter.addEventListener('change', filterProducts);
    resetButton.addEventListener('click', resetFilters);
});

// Render products to the grid
function renderProducts(productsToRender) {
    if (productsToRender.length === 0) {
        productGrid.innerHTML = '<div class="no-products">No products match the selected filters.</div>';
        return;
    }
    
    productGrid.innerHTML = productsToRender.map(product => `
        <div class="product-card">
            <div class="product-image">🔧</div>
            <div class="product-info">
                <span class="product-category">${getCategoryName(product.category)}</span>
                <h3 class="product-name">${product.name}</h3>
                <p class="product-description">${product.description}</p>
                <div class="product-price">$${product.price.toFixed(2)}</div>
                <div class="product-meta">
                    <span>★ ${product.rating}</span>
                    <span>${product.reviews} reviews</span>
                </div>
            </div>
        </div>
    `).join('');
}

// Get category display name
function getCategoryName(category) {
    const categories = {
        'surgical': 'Surgical',
        'diagnostic': 'Diagnostic',
        'laboratory': 'Laboratory',
        'imaging': 'Imaging'
    };
    return categories[category] || category;
}

// Filter products based on selected filters
function filterProducts() {
    const category = categoryFilter.value;
    const brand = brandFilter.value;
    const priceRange = priceRangeFilter.value;
    
    let filteredProducts = [...products];
    
    // Apply category filter
    if (category !== 'all') {
        filteredProducts = filteredProducts.filter(product => product.category === category);
    }
    
    // Apply brand filter
    if (brand !== 'all') {
        filteredProducts = filteredProducts.filter(product => product.brand === brand);
    }
    
    // Apply price range filter
    if (priceRange !== 'all') {
        filteredProducts = filteredProducts.filter(product => {
            switch(priceRange) {
                case '0-1000':
                    return product.price >= 0 && product.price <= 1000;
                case '1000-5000':
                    return product.price > 1000 && product.price <= 5000;
                case '5000-10000':
                    return product.price > 5000 && product.price <= 10000;
                case '10000+':
                    return product.price > 10000;
                default:
                    return true;
            }
        });
    }
    
    renderProducts(filteredProducts);
}

// Reset all filters
function resetFilters() {
    categoryFilter.value = 'all';
    brandFilter.value = 'all';
    priceRangeFilter.value = 'all';
    renderProducts(products);
}