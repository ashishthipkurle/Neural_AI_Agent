from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Initialize database
def init_db():
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY,
                  name TEXT NOT NULL,
                  description TEXT,
                  price REAL,
                  category TEXT)''')
    conn.commit()
    conn.close()

# Product search endpoint
@app.route('/search', methods=['GET'])
def search_products():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    
    sql = "SELECT * FROM products WHERE name LIKE ?"
    params = [f'%{query}%']
    
    if category:
        sql += " AND category = ?"
        params.append(category)
        
    c.execute(sql, params)
    results = c.fetchall()
    
    conn.close()
    
    return jsonify(results)

# Product inquiry form endpoint
@app.route('/inquiry', methods=['POST'])
def submit_inquiry():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    product_id = data.get('product_id')
    message = data.get('message')
    
    # Store inquiry in database (implementation omitted for brevity)
    # In a real application, you would validate and store this data
    
    return jsonify({"status": "Inquiry submitted successfully"})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)