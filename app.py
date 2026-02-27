import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import pymysql
import pymysql.cursors
from werkzeug.utils import secure_filename
import requests
import qrcode
import io
import socket
import google.generativeai as genai
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = 'agri_setu_secret_key'
# This looks for Vercel environment variables, but defaults to your local setup for testing
# Cloud Database Configuration
app.config['MYSQL_HOST'] = os.getenv('DB_HOST', 'agrisetudb-agrisetudb.h.aivencloud.com')
app.config['MYSQL_USER'] = os.getenv('DB_USER', 'avnadmin')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD', 'AVNS_PUGOsGEP-oq6K6NtATL')
app.config['MYSQL_DB'] = os.getenv('DB_NAME', 'defaultdb')
app.config['MYSQL_PORT'] = int(os.getenv('DB_PORT', 13782)) 

# Cloudinary Configuration
cloudinary.config( 
  cloud_name = "dfmekdssr", 
  api_key = "727166167383219", 
  api_secret = "559J7DortNrxfb55W-HY88CJn4E",
  secure = True
)
# Image Upload Config
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# --- NEW PYMYSQL CONNECTION HELPER ---
def get_db_connection(dict_cursor=False):
    return pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB'],
        port=app.config['MYSQL_PORT'],
        ssl={"ca": "ca.pem"},
        cursorclass=pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
    )

# Setup Gemini AI 
GEMINI_API_KEY = "AIzaSyDLfS83DwbcCyP3o0O_m6tkHN8I8BE0ebM"
genai.configure(api_key=GEMINI_API_KEY)

# --- AUTO-DETECT WORKING MODEL ---
working_model_name = 'gemini-pro' # safe fallback
try:
    print("\n--- Connecting to Google AI Studio ---")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # Look for the best available text models
            if 'flash' in m.name or 'pro' in m.name:
                working_model_name = m.name.replace('models/', '')
                break
    print(f"SUCCESS! Attached to model: {working_model_name}\n")
except Exception as e:
    print(f"\nAPI KEY ERROR: Could not connect. Please check your API key.\nDetails: {e}\n")

# Initialize the model using the dynamically found name
model = genai.GenerativeModel(working_model_name)

# Initialize chat session for the Agri-Buddy chatbot
chat_session = model.start_chat(history=[])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- AUTH & PUBLIC ROUTES ---

@app.route('/')
def home():
    if 'loggedin' in session:
        return redirect(url_for('farmer_dashboard') if session['role'] == 'Farmer' else url_for('consumer_dashboard'))
    return redirect(url_for('consumer_dashboard')) 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        connection = get_db_connection(dict_cursor=True)
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        account = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role']
            return redirect(url_for('farmer_dashboard') if account['role'] == 'Farmer' else url_for('consumer_dashboard'))
        else:
            flash('Incorrect email or password!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
        if cursor.fetchone():
            flash('Account already exists!')
            cursor.close()
            connection.close()
        else:
            cursor.execute('INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)', (username, email, password, role))
            connection.commit()
            cursor.close()
            connection.close()
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- NEW HELPER FUNCTION ---
def get_ip_address():
    """Automatically finds the computer's WiFi IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect, just checks how it WOULD connect to the internet
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# --- FARMER DASHBOARD ---

@app.route('/farmer_dashboard')
def farmer_dashboard():
    if 'loggedin' in session and session['role'] == 'Farmer':
        connection = get_db_connection(dict_cursor=True)
        cursor = connection.cursor()
        
        cursor.execute('SELECT * FROM marketplace WHERE farmer_id = %s', (session['id'],))
        my_listings = cursor.fetchall() or []
        cursor.execute('SELECT * FROM orders WHERE farmer_id = %s ORDER BY order_date DESC LIMIT 5', (session['id'],))
        recent_sales = cursor.fetchall() or []
        cursor.execute('SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC', (session['id'],))
        notifications = cursor.fetchall() or []
        cursor.execute('SELECT SUM(total_price) as total FROM orders WHERE farmer_id = %s', (session['id'],))
        result = cursor.fetchone()
        total_earnings = result['total'] if result and result['total'] else 0
        
        cursor.close()
        connection.close()
        
        stats = {'earnings': total_earnings, 'weather': '28°C, Clear Sky', 'news': 'Govt announces subsidy for drip irrigation.'}
        return render_template('farmer_dashboard.html', username=session['username'], listings=my_listings, sales=recent_sales, stats=stats, notifications=notifications)
    return redirect(url_for('login'))

# --- UPDATE THIS ROUTE: Sell Crop (Now handles Unit & Location) ---
@app.route('/sell_crop', methods=['GET', 'POST'])
def sell_crop():
    if 'loggedin' in session and session['role'] == 'Farmer':
        if request.method == 'POST':
            # Handle Image Upload via Cloudinary
            image_filename = None
            if 'product_image' in request.files:
                file = request.files['product_image']
                if file and allowed_file(file.filename):
                    # 1. Send the file directly to Cloudinary
                    upload_result = cloudinary.uploader.upload(file)
                    
                    # 2. Grab the live URL and assign it to your existing variable
                    image_filename = upload_result["secure_url"]

            # Get New Fields
            unit = request.form.get('unit', 'kg')
            location = request.form.get('location', 'General')

            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute('''INSERT INTO marketplace (farmer_id, item_name, category, price, stock, description, image_file, unit, location) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''', 
                           (session['id'], request.form['item_name'], request.form['category'], request.form['price'], 
                            request.form['stock'], request.form.get('description'), image_filename, unit, location))
            connection.commit()
            cursor.close()
            connection.close()
            
            flash('Crop Listed Successfully!')
            return redirect(url_for('farmer_dashboard'))
        return render_template('sell_crop.html', username=session['username'])
    return redirect(url_for('login'))


# --- NEW API 1: Auto-Complete Suggestions ---
@app.route('/api/crop_suggestions', methods=['GET'])
def api_crop_suggestions():
    query = request.args.get('query', '')
    if not query: return jsonify([])
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    # Fetch distinct crop names that start with the query
    cursor.execute("SELECT DISTINCT item_name FROM marketplace WHERE item_name LIKE %s LIMIT 5", (f"{query}%",))
    suggestions = [row['item_name'] for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    
    return jsonify(suggestions)


# --- UPDATE THIS API ROUTE IN app.py ---

@app.route('/api/market_analysis', methods=['GET'])
def api_market_analysis():
    item_name = request.args.get('item_name', '')
    location_filter = request.args.get('location', '')
    unit_filter = request.args.get('unit', 'kg')  # <--- NEW PARAMETER
    
    if not item_name: return jsonify({'status': 'error'})
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    
    # 1. Base Query: NOW FILTERS BY UNIT ALSO
    query = "SELECT price, stock, location FROM marketplace WHERE item_name = %s AND unit = %s"
    params = [item_name, unit_filter]
    
    # Apply Location Filter if selected
    if location_filter and location_filter != 'All':
        query += " AND location = %s"
        params.append(location_filter)
        
    cursor.execute(query, tuple(params))
    listings = cursor.fetchall()
    
    # Get unique locations (ignoring unit for this one, to show all possibilities)
    cursor.execute("SELECT DISTINCT location FROM marketplace WHERE item_name = %s", (item_name,))
    locations = [row['location'] for row in cursor.fetchall()]
    
    cursor.close()
    connection.close()
    
    if not listings:
        return jsonify({
            'status': 'no_data',
            'locations': locations
        })

    # Calculate Stats
    prices = [float(l['price']) for l in listings]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = round(sum(prices) / len(prices), 2)
    competitors = len(listings)
    
    # Recommendation Logic
    recommended_price = avg_price
    if competitors > 5:
        recommended_price = round(avg_price * 0.95, 2)
    else:
        recommended_price = round(avg_price * 1.05, 2)

    return jsonify({
        'status': 'success',
        'min': min_price,
        'max': max_price,
        'avg': avg_price,
        'competitors': competitors,
        'recommended': recommended_price,
        'locations': locations,
        'graph_data': prices 
    })

@app.route('/generate_qr/<int:item_id>')
def generate_qr(item_id):
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM marketplace WHERE id = %s', (item_id,))
    item = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if not item: return "Item not found"

    # Create the link
    # request.url_root automatically gets the current domain (e.g., https://agri-setu.vercel.app/)
    qr_data = f"{request.url_root}farmer_profile/{item['farmer_id']}"
    
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


# --- CONSUMER & PRODUCT ROUTES ---

@app.route('/consumer_dashboard')
def consumer_dashboard():
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'newest')
    
    sql_query = """
        SELECT marketplace.*, users.username as farmer_name, users.id as farmer_id
        FROM marketplace 
        JOIN users ON marketplace.farmer_id = users.id 
        WHERE stock > 0
    """
    params = []
    if search_query:
        sql_query += " AND item_name LIKE %s"
        params.append(f"%{search_query}%")
    
    if sort_by == 'price_low': sql_query += " ORDER BY price ASC"
    elif sort_by == 'price_high': sql_query += " ORDER BY price DESC"
    elif sort_by == 'veg': sql_query += " AND category = 'Veg'"
    elif sort_by == 'fruit': sql_query += " AND category = 'Fruit'"
    else: sql_query += " ORDER BY id DESC"

    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    cursor.execute(sql_query, tuple(params))
    products = cursor.fetchall()
    cursor.close()
    connection.close()
    
    username = session.get('username', 'Guest')
    is_guest = 'loggedin' not in session
    return render_template('consumer_dashboard.html', username=username, products=products, is_guest=is_guest)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    
    # 1. Get Product Details with Farmer Info
    cursor.execute('''
        SELECT marketplace.*, users.username as farmer_name, users.phone as farmer_phone, users.about_me, users.email as farmer_email
        FROM marketplace 
        JOIN users ON marketplace.farmer_id = users.id 
        WHERE marketplace.id = %s
    ''', (product_id,))
    product = cursor.fetchone()
    
    if not product: 
        cursor.close()
        connection.close()
        return "Product not found"

    # 2. Get Reviews specific to this Product (via item_name matching or direct linking if structure allowed)
    cursor.execute('''
        SELECT reviews.*, users.username as buyer_name 
        FROM reviews 
        JOIN users ON reviews.buyer_id = users.id
        JOIN orders ON reviews.order_id = orders.id
        WHERE orders.farmer_id = %s AND orders.item_name = %s
        ORDER BY reviews.created_at DESC
    ''', (product['farmer_id'], product['item_name']))
    reviews = cursor.fetchall()

    # 3. Calculate Product Rating
    avg_rating = "New"
    if reviews:
        total = sum(r['rating'] for r in reviews)
        avg_rating = round(total / len(reviews), 1)

    cursor.close()
    connection.close()
    
    username = session.get('username', 'Guest')
    is_guest = 'loggedin' not in session
    
    return render_template('product_detail.html', product=product, reviews=reviews, rating=avg_rating, is_guest=is_guest, username=username)

# --- FARMER PROFILE (Enhanced) ---

@app.route('/farmer_profile/<int:farmer_id>')
def farmer_profile(farmer_id):
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    
    cursor.execute('SELECT id, username, email, phone, about_me FROM users WHERE id = %s', (farmer_id,))
    farmer = cursor.fetchone()
    
    cursor.execute('SELECT * FROM marketplace WHERE farmer_id = %s AND stock > 0', (farmer_id,))
    listings = cursor.fetchall()
    
    # Enhanced Reviews Query: Get Buyer Name AND Item Name
    cursor.execute('''
        SELECT reviews.*, users.username as buyer_name, orders.item_name
        FROM reviews
        JOIN users ON reviews.buyer_id = users.id
        JOIN orders ON reviews.order_id = orders.id
        WHERE reviews.farmer_id = %s
        ORDER BY reviews.created_at DESC
    ''', (farmer_id,))
    reviews = cursor.fetchall()
    
    cursor.execute('SELECT AVG(rating) as avg_rating FROM reviews WHERE farmer_id = %s', (farmer_id,))
    avg = cursor.fetchone()['avg_rating']
    avg_rating = round(avg, 1) if avg else "New"
    
    cursor.close()
    connection.close()
    
    is_guest = 'loggedin' not in session
    return render_template('farmer_profile.html', farmer=farmer, listings=listings, reviews=reviews, rating=avg_rating, is_guest=is_guest)

# --- CART & ORDER APIs ---

@app.route('/api/add_to_cart', methods=['POST'])
def api_add_to_cart():
    if 'loggedin' not in session: return jsonify({'status': 'error', 'message': 'Please login'})
    data = request.get_json()
    item_id = data.get('item_id')
    if 'cart' not in session: session['cart'] = []
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM marketplace WHERE id = %s', (item_id,))
    product = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if product:
        cart = session['cart']
        found = False
        current_qty = 0
        for item in cart:
            if item['id'] == product['id']:
                current_qty = item['qty']
                found = True
                break
        if current_qty + 1 > product['stock']: return jsonify({'status': 'error', 'message': f"Only {product['stock']}kg left!"})
        if found:
            for item in cart:
                if item['id'] == product['id']: item['qty'] += 1; break
        else:
            cart.append({'id': product['id'], 'name': product['item_name'], 'price': float(product['price']), 'farmer_id': product['farmer_id'], 'qty': 1})
        session['cart'] = cart
        return jsonify({'status': 'success', 'cart_count': len(cart)})
    return jsonify({'status': 'error', 'message': 'Item not found'})

@app.route('/api/update_cart', methods=['POST'])
def api_update_cart():
    if 'cart' not in session: return jsonify({'status': 'error'})
    data = request.get_json()
    item_id = data.get('item_id')
    action = data.get('action')
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    cursor.execute('SELECT stock FROM marketplace WHERE id = %s', (item_id,))
    db_item = cursor.fetchone()
    cursor.close()
    connection.close()
    
    real_stock = db_item['stock'] if db_item else 0
    cart = session['cart']
    for item in cart:
        if item['id'] == item_id:
            if action == 'increase':
                if item['qty'] < real_stock: item['qty'] += 1
                else: return jsonify({'status': 'error', 'message': 'Stock Limit Reached'})
            elif action == 'decrease':
                item['qty'] -= 1
                if item['qty'] < 1: item['qty'] = 1
            break
    session['cart'] = cart
    return jsonify({'status': 'success'})

@app.route('/api/remove_from_cart', methods=['POST'])
def api_remove_from_cart():
    if 'cart' not in session: return jsonify({'status': 'error'})
    data = request.get_json()
    item_id = data.get('item_id')
    session['cart'] = [item for item in session['cart'] if item['id'] != item_id]
    return jsonify({'status': 'success'})

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    total_price = sum(item['price'] * item['qty'] for item in cart_items)
    return render_template('cart.html', cart=cart_items, total=total_price)

@app.route('/checkout')
def checkout():
    if 'cart' not in session or not session['cart']: return redirect(url_for('consumer_dashboard'))
    cart = session['cart']
    buyer_id = session['id']
    buyer_name = session['username']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        for item in cart:
            cursor.execute("SELECT stock FROM marketplace WHERE id=%s", (item['id'],))
            res = cursor.fetchone()
            curr = res[0] if isinstance(res, tuple) else res['stock']
            if curr >= item['qty']:
                cursor.execute('UPDATE marketplace SET stock = stock - %s WHERE id = %s', (item['qty'], item['id']))
                total = item['price'] * item['qty']
                cursor.execute('INSERT INTO orders (buyer_id, farmer_id, item_name, quantity, total_price) VALUES (%s, %s, %s, %s, %s)', (buyer_id, item['farmer_id'], item['name'], item['qty'], total))
                msg = f"New Order! {buyer_name} bought {item['qty']}kg of {item['name']}."
                cursor.execute('INSERT INTO notifications (user_id, message) VALUES (%s, %s)', (item['farmer_id'], msg))
        connection.commit()
        session.pop('cart', None)
        return render_template('checkout_success.html')
    except Exception as e:
        connection.rollback()
        return f"Error: {str(e)}"
    finally: 
        cursor.close()
        connection.close()

@app.route('/my_orders')
def my_orders():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    cursor.execute('SELECT orders.*, users.username as farmer_name, users.phone as farmer_phone FROM orders JOIN users ON orders.farmer_id = users.id WHERE buyer_id = %s ORDER BY order_date DESC', (session['id'],))
    orders = cursor.fetchall()
    cursor.execute('SELECT order_id FROM reviews WHERE buyer_id = %s', (session['id'],))
    rated = [i['order_id'] for i in cursor.fetchall()]
    cursor.close()
    connection.close()
    
    return render_template('my_orders.html', orders=orders, rated_orders=rated)

@app.route('/rate_order', methods=['POST'])
def rate_order():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('INSERT INTO reviews (order_id, farmer_id, buyer_id, rating, review_text) VALUES (%s, %s, %s, %s, %s)', (request.form['order_id'], request.form['farmer_id'], session['id'], request.form['rating'], request.form['review_text']))
    connection.commit()
    cursor.close()
    connection.close()
    
    return redirect(url_for('my_orders'))

# --- EXTRAS ---
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('UPDATE users SET phone=%s, about_me=%s WHERE id=%s', (request.form['phone'], request.form['about_me'], session['id']))
    connection.commit()
    cursor.close()
    connection.close()
    
    return redirect(url_for('settings'))

@app.route('/ask_ai', methods=['POST'])
def ask_ai(): return jsonify({'response': "I am working!"})

@app.route('/tools/soil')
def tool_soil(): return render_template('tool_soil.html')
@app.route('/tools/pest')
def tool_pest(): return render_template('tool_pest.html')
@app.route('/tools/crop')
def tool_crop(): return render_template('tool_crop.html')
@app.route('/tools/water')
def tool_water(): return render_template('tool_water.html')
@app.route('/tool/weather', methods=['POST'])
def tool_weather(): return jsonify({'status': 'success', 'data': {'temp': 29, 'desc': 'Partly Cloudy', 'humidity': 62}})
@app.route('/settings')
def settings(): return render_template('settings.html', username=session.get('username'))

# Logic APIs for tools
@app.route('/tool/soil_test', methods=['POST'])
def tool_soil_test(): return jsonify({'ph': '7.0', 'advice': 'Good soil.'})
@app.route('/tool/pest_check', methods=['POST'])
def tool_pest_check(): return jsonify({'disease': 'Check leaves', 'remedy': 'Neem oil'})
@app.route('/tool/crop_recommend', methods=['POST'])
def tool_crop_recommend(): return jsonify({'crop': 'Rice'})
@app.route('/tool/water_schedule', methods=['POST'])
def tool_water_schedule(): return jsonify({'advice': 'Water now'})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.get_json()
        user_msg = data.get('message', '')
        page_context = data.get('page_context', 'General Dashboard')

        if not user_msg:
            return jsonify({'error': 'Message is required'}), 400

        system_instructions = """
        You are 'Agri-Buddy', an interactive visual guide for the Agri Setu app.
        You have a physical body on the screen. You can move to specific buttons to show the user where to click.
        
        If the user asks how to do something, explain it simply AND include one of these ACTION TAGS at the end of your sentence:
        
        1. IF ON 'SELL CROP' PAGE:
           - Explain they need to enter crop name, price, and upload a photo.
           - If they ask to submit/sell, reply with tag: {{POINT_SUBMIT}}
           - If they ask where to type name, reply with tag: {{POINT_NAME}}
           
        2. IF ON 'FARMER STUDIO' (Dashboard):
          - To sell crops: {{POINT_SELL}}
          - To check weather: {{POINT_WEATHER}}
          - To check earnings: {{POINT_FINANCE}}
          - To use tools: {{POINT_TOOLS}}
          - To settings: {{POINT_PROFILE}} 
        
        3. IF ON A TOOL PAGE (Soil/Pest):
           - Guide them to fill the form and click Calculate.
           - To go back -> {{POINT_BACK}}
        If a user asks how to do something in the app, tell them which tool to use. If they ask a general farming question, answer it.
        Keep your answers very simple, polite, and under 3-4 sentences.

        CRITICAL RULE: Always reply in the exact same language that the user used to ask the question. If they type in Hindi, reply in Hindi. If they type in Telugu, reply in Telugu.
               """
        
        full_prompt = f"{system_instructions}\nUser Question: {user_msg}"
        print(f"Sending to AI: {user_msg}")
        response = chat_session.send_message(full_prompt)
        print(f"AI Repled: {response.text}")
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"SERVER ERROR IN /api/chat: {e}") 
        return jsonify({'reply': "Sorry, I am having trouble connecting. Please check the terminal for errors."}), 500
    
# =========================================
# 7. CHAT SYSTEM (P2P)
# =========================================

@app.route('/inbox')
def chat_inbox():
    if 'loggedin' not in session: return redirect(url_for('login'))
    user_id = session['id']
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    
    query = """
        SELECT u.id, u.username, u.role, MAX(m.created_at) as last_interaction
        FROM users u
        JOIN messages m ON (u.id = m.sender_id AND m.receiver_id = %s) 
                        OR (u.id = m.receiver_id AND m.sender_id = %s)
        GROUP BY u.id, u.username, u.role
        ORDER BY last_interaction DESC
    """
    cursor.execute(query, (user_id, user_id))
    conversations = cursor.fetchall()
    
    for conv in conversations:
        cursor.execute("""
            SELECT message, created_at FROM messages 
            WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, conv['id'], conv['id'], user_id))
        last_msg = cursor.fetchone()
        conv['last_message'] = last_msg['message'] if last_msg else "Start chatting..."
        conv['time'] = last_msg['created_at'] if last_msg else ""
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM messages 
            WHERE sender_id = %s AND receiver_id = %s AND is_read = 0
        """, (conv['id'], user_id))
        conv['unread'] = cursor.fetchone()['count']

    cursor.close()
    connection.close()
    
    return render_template('chat_inbox.html', conversations=conversations, username=session['username'])

@app.route('/chat/<int:other_user_id>')
def chat_room(other_user_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    user_id = session['id']
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    
    cursor.execute('SELECT id, username, role FROM users WHERE id = %s', (other_user_id,))
    other_user = cursor.fetchone()
    
    query = """
        SELECT u.id, u.username, u.role, MAX(m.created_at) as last_interaction
        FROM users u
        JOIN messages m ON (u.id = m.sender_id AND m.receiver_id = %s) 
                        OR (u.id = m.receiver_id AND m.sender_id = %s)
        GROUP BY u.id, u.username, u.role
        ORDER BY last_interaction DESC
    """
    cursor.execute(query, (user_id, user_id))
    conversations = cursor.fetchall()

    for conv in conversations:
        cursor.execute("""
            SELECT message FROM messages 
            WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, conv['id'], conv['id'], user_id))
        last_msg = cursor.fetchone()
        conv['last_message'] = last_msg['message'] if last_msg else "..."

    cursor.close()
    connection.close()
    
    return render_template('chat_room.html', other_user=other_user, conversations=conversations, username=session['username'])

# API: Get Messages (For real-time polling)
@app.route('/api/get_messages/<int:other_user_id>')
def api_get_messages(other_user_id):
    if 'loggedin' not in session: return jsonify([])
    my_id = session['id']
    
    connection = get_db_connection(dict_cursor=True)
    cursor = connection.cursor()
    
    cursor.execute("UPDATE messages SET is_read = 1 WHERE sender_id = %s AND receiver_id = %s", (other_user_id, my_id))
    connection.commit()
    
    cursor.execute("""
        SELECT * FROM messages 
        WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
        ORDER BY created_at ASC
    """, (my_id, other_user_id, other_user_id, my_id))
    messages = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return jsonify(messages)

# API: Send Message
@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    if 'loggedin' not in session: return jsonify({'status': 'error'})
    data = request.get_json()
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO messages (sender_id, receiver_id, message) 
        VALUES (%s, %s, %s)
    """, (session['id'], data['receiver_id'], data['message']))
    connection.commit()
    
    cursor.close()
    connection.close()
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    ip = get_ip_address()
    print(f" --- APP RUNNING ON: http://{ip}:5000 --- ")
    app.run(debug=True, host='0.0.0.0')