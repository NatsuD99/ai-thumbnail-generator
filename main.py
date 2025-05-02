from flask import Flask, render_template, request, url_for, jsonify, session
import os
from werkzeug.utils import secure_filename
import base64
import uuid
import requests
import json
from dotenv import load_dotenv
from openai import OpenAI
import io
from PIL import Image
import time
import stripe

# Load environment variables
load_dotenv()

# OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for session
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DRAWINGS_FOLDER'] = os.path.join('static', 'drawings')  # Add drawings subfolder
app.config['GENERATED_FOLDER'] = os.path.join('static', 'generated')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SUPABASE_URL'] = SUPABASE_URL
app.config['SUPABASE_KEY'] = SUPABASE_KEY

# Stripe plans
STRIPE_PLANS = {
    'starter': {
        'price_id': os.getenv('STRIPE_STARTER_PRICE_ID'),
        'name': 'Starter',
        'monthly_limit': 15
    },
    'growth': {
        'price_id': os.getenv('STRIPE_GROWTH_PRICE_ID'),
        'name': 'Growth', 
        'monthly_limit': 50
    },
    'scale': {
        'price_id': os.getenv('STRIPE_SCALE_PRICE_ID'),
        'name': 'Scale',
        'monthly_limit': 100
    }
}

# Ensure static folder is served correctly
app.static_folder = 'static'

# YouTube thumbnail dimensions
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Ensure required folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DRAWINGS_FOLDER'], exist_ok=True)  # Create drawings folder
os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')

def save_base64_image(base64_string, folder, filename):
    if base64_string:
        # Remove data URL prefix if present
        if 'base64,' in base64_string:
            base64_string = base64_string.split('base64,')[1]
        
        image_data = base64.b64decode(base64_string)
        filepath = os.path.join(folder, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_data)
        return filepath
    return None

def encode_image_to_base64(image_path):
    """Encode an image to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_image_dimensions(image_path):
    """Get dimensions of an image"""
    with Image.open(image_path) as img:
        return img.size

def generate_with_openai(sketch_path, prompt="", reference_images=None):
    """
    Generate a thumbnail using OpenAI's DALL-E 3 API
    
    Args:
        sketch_path (str): Path to the user's sketch
        prompt (str): User's text prompt
        reference_images (list): List of paths to reference images
    
    Returns:
        str: Path to the generated image
    """
    try:
        # Define default prompt if not provided
        if not prompt:
            prompt = "Create a professional, visually striking YouTube thumbnail using the provided sketch as the layout. Use the following as additional guidance:: Focus on bold colors, balanced composition, and saturated lighting unless otherwise specified. No Youtube logo unless explicitly mentioned."
        else:
            prompt = f"Create a professional, high-quality YouTube thumbnail using the provided sketch as the layout with the following specifications: {prompt}. Use the following as additional guidance:: Focus on bold colors, balanced composition, and saturated lighting unless otherwise specified. No Youtube logo unless explicitly mentioned."
            
        # if reference_images:
        #     prompt = f"Generate a high quality YouTube thumbnail that visually resembles the reference image(s) in style and color palette, while following the structure of the provided sketch. Focus on bold colors, balanced composition, and saturated lighting."
        # Add reference to dimensions
        prompt += f". The final image should be suitable for a YouTube thumbnail with a 16:9 aspect ratio."
        
        print(f"Using prompt: {prompt}")
        
        # Generate image using DALL-E 3 with supported dimensions
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",  # Use supported dimensions
            quality="standard",
            n=1,
        )
        
        # Get the image URL from the response
        image_url = image_response.data[0].url
        
        # Download the generated image
        image_data = requests.get(image_url).content
        
        # Create a unique filename for the generated image
        timestamp = int(time.time())
        generated_filename = f"thumbnail_{timestamp}.png"
        generated_path = os.path.join(app.config['GENERATED_FOLDER'], generated_filename)
        
        # Open the image and resize it to 1024x768
        image = Image.open(io.BytesIO(image_data))
        resized_image = image.resize((1024, 768), Image.Resampling.LANCZOS)
        
        # Save the resized image
        resized_image.save(generated_path, "PNG")
        
        return generated_path
        
    except Exception as e:
        print(f"Error generating image with OpenAI: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

@app.route('/generate', methods=['POST'])
def generate_thumbnail():
    try:
        session_id = str(uuid.uuid4())
        
        # Handle canvas drawing
        canvas_data = request.form.get('canvas_data')
        if not canvas_data or not canvas_data.startswith('data:image'):
            return jsonify({
                'success': False,
                'error': 'A sketch is required to generate a thumbnail.'
            }), 400
        
        # Try to get user ID from request form data first
        user_id = request.form.get('user_id')
        print(f"User ID from form data: {user_id}")
        
        # If not present, try to get it from Authorization header
        if not user_id:
            auth_header = request.headers.get('Authorization')
            print(f"Authorization header: {auth_header}")
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                user_id = get_user_from_token(token)
                print(f"User ID from token: {user_id}")
                
        # Check user's usage limit if authenticated
        if user_id:
            usage_check = check_user_usage_limit(user_id)
            print(f"Usage check result: {usage_check}")
            if not usage_check["allowed"]:
                return jsonify({
                    'success': False,
                    'error': usage_check["message"]
                }), 403
        else:
            # BLOCK anonymous requests
            return jsonify({
                'success': False,
                'error': 'You must be logged in to generate thumbnails.'
            }), 401
        
        # Get text prompt if provided
        prompt = request.form.get('prompt', '')
        
        # Save sketch to file
        canvas_filename = f"{session_id}_sketch.png"
        canvas_path = save_base64_image(
            canvas_data,
            app.config['DRAWINGS_FOLDER'],
            canvas_filename
        )
        print(f"Saved sketch to: {canvas_path}")
        
        # Removed reference image handling logic

        # Generate thumbnail using OpenAI
        generated_path = generate_with_openai(
            sketch_path=canvas_path,
            prompt=prompt
        )
        
        if not generated_path:
            return jsonify({
                'success': False,
                'error': 'Failed to generate thumbnail. Please try again.'
            }), 500
        
        # Convert file path to URL
        image_url = url_for('static', filename=f"generated/{os.path.basename(generated_path)}", _external=True)
        print(f"Generated image URL: {image_url}")
        
        # Record thumbnail usage in Supabase if user is authenticated
        if user_id:
            print(f"Attempting to record thumbnail usage for user: {user_id}")
            success = record_thumbnail_usage(user_id, image_url)
            print(f"Recording thumbnail usage result: {success}")
        else:
            print("No user ID found, skipping thumbnail usage recording")
        
        return jsonify({
            'success': True,
            'images': [image_url]
        })

    except Exception as e:
        print(f"Error in generate_thumbnail: {str(e)}")
        # Log the full error for debugging
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def record_thumbnail_usage(user_id, image_url):
    """
    Record thumbnail generation in Supabase
    
    Args:
        user_id (str): The user's UUID from Supabase Auth
        image_url (str): URL of the generated thumbnail
    
    Returns:
        bool: True if recorded successfully, False otherwise
    """
    try:
        print(f"Recording thumbnail usage - User ID: {user_id}, Image URL: {image_url}")
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            print(f"Supabase configuration missing - URL: {SUPABASE_URL}, Key: {'Present' if SUPABASE_KEY else 'Missing'}")
            return False
            
        # Ensure user_id is a valid UUID
        try:
            uuid_obj = uuid.UUID(user_id)
            user_id = str(uuid_obj)  # Normalize the UUID format
        except ValueError:
            print(f"Invalid UUID format for user_id: {user_id}")
            return False
            
        # Prepare the data
        data = {
            "user_id": user_id,
            "image_url": image_url
        }
        print(f"Data to be sent to Supabase: {data}")
        
        # Set up headers for Supabase API request
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        # Construct the full API URL
        api_url = f"{SUPABASE_URL}/rest/v1/thumbnail_usage"
        print(f"Making POST request to Supabase: {api_url}")
        
        # Make the API request to insert the record
        print(f"Sending POST request to {SUPABASE_URL}/rest/v1/thumbnail_usage")
        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10  # Add timeout to prevent hanging requests
        )
        
        print(f"Supabase API response - Status: {response.status_code}, Body: {response.text}")
        
        if response.status_code in [201, 200, 204]:
            print(f"Successfully recorded thumbnail usage for user {user_id}")
            return True
        else:
            print(f"Failed to record thumbnail usage: {response.status_code} - {response.text}")
            # Try to parse error response
            try:
                error_json = response.json()
                print(f"Error details: {error_json}")
            except:
                print("Could not parse error response as JSON")
            return False
            
    except Exception as e:
        print(f"Error recording thumbnail usage: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def get_user_from_token(jwt_token):
    """
    Verify and get user ID from Supabase JWT token
    
    Args:
        jwt_token (str): JWT token from Supabase Auth
        
    Returns:
        str: User ID if token is valid, None otherwise
    """
    try:
        if not jwt_token:
            return None
            
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        # Make a request to Supabase to get the user data
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                **headers,
                "Authorization": f"Bearer {jwt_token}"
            }
        )
        
        if response.status_code == 200:
            user_data = response.json()
            return user_data.get("id")
        else:
            print(f"Failed to get user from token: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error getting user from token: {str(e)}")
        return None

def check_user_usage_limit(user_id):
    """
    Check if the user has reached their usage limit for the current month
    
    Args:
        user_id (str): The user's UUID from Supabase Auth
        
    Returns:
        dict: With keys 'allowed' (bool) and 'message' (str) explaining the reason if not allowed
    """
    try:
        if not user_id or not SUPABASE_URL or not SUPABASE_KEY:
            # If there's no user ID or Supabase configuration, allow the request
            # This is for development purposes and should be updated in production
            return {"allowed": True, "message": "No user ID or Supabase configuration"}
            
        # Get the current month and year
        current_month = time.strftime("%m")
        current_year = time.strftime("%Y")
        
        # Set up headers for Supabase API request
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Query for the user's subscription status
        # Note: This assumes you have a 'subscriptions' table with user subscriptions
        # This is a placeholder and should be updated with your actual subscription logic
        try:
            sub_response = requests.get(
                f"{SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.{user_id}&select=plan,status",
                headers=headers
            )
            
            if sub_response.status_code == 200 and sub_response.json():
                subscription = sub_response.json()[0]
                plan = subscription.get("plan", "")
                status = subscription.get("status", "")
                
                # Check if subscription is active
                if status != "active":
                    return {"allowed": False, "message": "Your subscription is not active"}
                    
                # Set limits based on plan
                if plan == "starter":
                    monthly_limit = 15
                elif plan == "growth":
                    monthly_limit = 50
                elif plan == "scale":
                    monthly_limit = 100  # Unlimited in reality
                else:
                    monthly_limit = 3  # Free tier
            else:
                # No subscription found, use free tier limit
                monthly_limit = 3
        except Exception as e:
            print(f"Error checking subscription: {str(e)}")
            monthly_limit = 3  # Default to free tier on error
        
        # Query to count the user's thumbnail generations for the current month
        usage_query = f"user_id=eq.{user_id}&generated_at=gte.{current_year}-{current_month}-01"
        usage_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/thumbnail_usage?{usage_query}&select=id",
            headers={**headers, "Prefer": "count=exact"}
        )
        
        usage_count = int(usage_response.headers.get("Content-Range", "*/0").split("/")[1])
        
        if usage_count >= monthly_limit:
            return {
                "allowed": False, 
                "message": f"You have reached your monthly limit of {monthly_limit} thumbnails. Please upgrade your subscription."
            }
            
        return {"allowed": True, "message": ""}
        
    except Exception as e:
        print(f"Error checking user usage limit: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Allow the request in case of an error to avoid blocking users
        return {"allowed": True, "message": "Error checking usage limits"}

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.json
        user_id = data.get('user_id')
        plan = data.get('plan')

        if not user_id or not plan:
            return jsonify({
                'success': False,
                'error': 'User ID and plan are required.'
            }), 400

        if plan not in STRIPE_PLANS:
            return jsonify({
                'success': False,
                'error': f'Invalid plan selected. Available plans: {", ".join(STRIPE_PLANS.keys())}'
            }), 400

        price_id = STRIPE_PLANS[plan]['price_id']
        if not price_id:
            return jsonify({
                'success': False,
                'error': f'Price ID not configured for plan: {plan}'
            }), 500

        # Create a checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.host_url + 'payment/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'payment/cancel',
            client_reference_id=user_id,
            customer_email=data.get('email'),  # Optional: pre-fill customer email
            metadata={
                'user_id': user_id,
                'plan': plan
            }
        )

        return jsonify({
            'success': True,
            'checkout_url': checkout_session.url
        })

    except Exception as e:
        print(f"Error creating checkout session: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/payment/success')
def payment_success():
    session_id = request.args.get('session_id', '')
    
    if session_id:
        try:
            # Retrieve the checkout session to get details
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            # You can use the session details to display personalized message
            return render_template('payment_success.html', session=checkout_session)
        except Exception as e:
            print(f"Error retrieving checkout session: {str(e)}")
    
    # If no session_id or error retrieving session, show generic success page
    return render_template('payment_success.html')

@app.route('/payment/cancel')
def payment_cancel():
    return render_template('payment_cancel.html')

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = None
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        if webhook_secret:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, webhook_secret
                )
            except stripe.error.SignatureVerificationError as e:
                print(f"⚠️  Webhook signature verification failed: {str(e)}")
                return jsonify({'success': False}), 400
        else:
            print("⚠️ Webhook secret not configured. Skipping signature verification.")
            data = json.loads(payload)
            event = stripe.Event.construct_from(data, stripe.api_key)
        
        # Handle the event
        if event.type == 'checkout.session.completed':
            session = event.data.object
            handle_checkout_session_completed(session)
        elif event.type == 'customer.subscription.created':
            subscription = event.data.object
            handle_subscription_created(subscription)
        elif event.type == 'customer.subscription.updated':
            subscription = event.data.object
            handle_subscription_updated(subscription)
        elif event.type == 'customer.subscription.deleted':
            subscription = event.data.object
            handle_subscription_deleted(subscription)
        else:
            print(f'Unhandled event type {event.type}')
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f'Error handling webhook: {str(e)}')
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False}), 500

def handle_checkout_session_completed(session):
    """Process completed checkout session"""
    try:
        user_id = session.metadata.get('user_id')
        plan = session.metadata.get('plan')
        customer_id = session.customer
        subscription_id = session.subscription
        
        if not user_id or not plan or not subscription_id:
            print("Missing required metadata in checkout session")
            return
            
        print(f"Processing checkout session for User ID: {user_id}, Plan: {plan}, Subscription: {subscription_id}")
            
        # Update subscription in Supabase
        update_user_subscription(
            user_id=user_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            plan=plan,
            status='active'
        )
            
    except Exception as e:
        print(f"Error processing checkout session: {str(e)}")
        import traceback
        print(traceback.format_exc())

def handle_subscription_created(subscription):
    """Handle a new subscription"""
    try:
        # Extract the subscription details
        subscription_id = subscription.id
        customer_id = subscription.customer
        status = subscription.status
        
        print(f"New subscription created - ID: {subscription_id}, Customer: {customer_id}, Status: {status}")
        
        # Find the user_id from the customer_id in Supabase
        # This assumes you have a way to get the user_id from customer_id
        # If not, you should store this mapping when creating the checkout session
    except Exception as e:
        print(f"Error handling subscription created: {str(e)}")

def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        subscription_id = subscription.id
        status = subscription.status
        
        print(f"Subscription updated - ID: {subscription_id}, New status: {status}")
        
        # Update the subscription status in Supabase
        update_subscription_status(subscription_id, status)
    except Exception as e:
        print(f"Error handling subscription update: {str(e)}")

def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        subscription_id = subscription.id
        
        print(f"Subscription cancelled - ID: {subscription_id}")
        
        # Update the subscription status in Supabase
        update_subscription_status(subscription_id, 'canceled')
    except Exception as e:
        print(f"Error handling subscription cancellation: {str(e)}")

def update_user_subscription(user_id, customer_id, subscription_id, plan, status):
    """
    Update or create user subscription in Supabase
    
    Args:
        user_id (str): The user's UUID from Supabase Auth
        customer_id (str): Stripe customer ID
        subscription_id (str): Stripe subscription ID
        plan (str): Subscription plan name
        status (str): Subscription status
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("Supabase configuration missing")
            return False
            
        # Ensure user_id is a valid UUID
        try:
            uuid_obj = uuid.UUID(user_id)
            user_id = str(uuid_obj)  # Normalize the UUID format
        except ValueError:
            print(f"Invalid UUID format for user_id: {user_id}")
            return False
        
        # Get current timestamp
        current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Prepare the data
        data = {
            "user_id": user_id,
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "plan": plan,
            "status": status,
            "updated_at": current_time
        }
        
        # Set up headers for Supabase API request
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"  # Upsert - update if exists, insert if not
        }
        
        # First check if subscription exists
        check_url = f"{SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.{user_id}&select=id"
        check_response = requests.get(check_url, headers=headers)
        
        if check_response.status_code == 200 and check_response.json():
            # Subscription exists, update it
            api_url = f"{SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.{user_id}"
            response = requests.patch(api_url, headers=headers, json=data)
            print(f"Updating subscription - Status: {response.status_code}")
        else:
            # Create new subscription
            data["created_at"] = current_time  # Add created_at for new records
            api_url = f"{SUPABASE_URL}/rest/v1/subscriptions"
            response = requests.post(api_url, headers=headers, json=data)
            print(f"Creating subscription - Status: {response.status_code}")
        
        if response.status_code in [200, 201, 204]:
            print(f"Successfully updated subscription for user {user_id}")
            return True
        else:
            print(f"Failed to update subscription: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error updating subscription: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def update_subscription_status(subscription_id, status):
    """
    Update subscription status in Supabase
    
    Args:
        subscription_id (str): Stripe subscription ID
        status (str): New subscription status
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("Supabase configuration missing")
            return False
        
        # Get current timestamp
        current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Prepare the data
        data = {
            "status": status,
            "updated_at": current_time
        }
        
        # Set up headers for Supabase API request
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Update subscription
        api_url = f"{SUPABASE_URL}/rest/v1/subscriptions?subscription_id=eq.{subscription_id}"
        response = requests.patch(api_url, headers=headers, json=data)
        
        if response.status_code in [200, 201, 204]:
            print(f"Successfully updated subscription status for {subscription_id} to {status}")
            return True
        else:
            print(f"Failed to update subscription status: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error updating subscription status: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

@app.route('/subscription-status', methods=['GET'])
def get_subscription_status():
    """Get current user's subscription status"""
    try:
        # Get user ID from request
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID is required.'
            }), 400
            
        if not SUPABASE_URL or not SUPABASE_KEY:
            return jsonify({
                'success': False,
                'error': 'Supabase configuration missing.'
            }), 500
        
        # Set up headers for Supabase API request
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Query for the user's subscription
        api_url = f"{SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.{user_id}&select=*"
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            subscriptions = response.json()
            
            if not subscriptions:
                return jsonify({
                    'success': True,
                    'has_subscription': False,
                    'subscription': None
                })
                
            # Return the most recent subscription
            # Typically there should be only one active subscription per user
            latest_subscription = subscriptions[0]  # assuming sorted by creation date
            
            return jsonify({
                'success': True,
                'has_subscription': True,
                'subscription': {
                    'plan': latest_subscription.get('plan'),
                    'status': latest_subscription.get('status'),
                    'created_at': latest_subscription.get('created_at'),
                    'updated_at': latest_subscription.get('updated_at')
                }
            })
        else:
            print(f"Failed to get subscription: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'error': 'Failed to retrieve subscription status.'
            }), 500
            
    except Exception as e:
        print(f"Error getting subscription status: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/manage-subscription', methods=['GET'])
def manage_subscription():
    """Create a portal session for the user to manage their subscription"""
    try:
        # Get user ID from request
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID is required.'
            }), 400
            
        # Query for the user's subscription to get the customer ID
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        api_url = f"{SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.{user_id}&select=customer_id"
        response = requests.get(api_url, headers=headers)
        
        if response.status_code != 200 or not response.json():
            return jsonify({
                'success': False,
                'error': 'No active subscription found for this user.'
            }), 404
            
        customer_id = response.json()[0].get('customer_id')
        
        if not customer_id:
            return jsonify({
                'success': False,
                'error': 'Customer ID not found.'
            }), 404
            
        # Create a Stripe customer portal session
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=request.host_url
        )
        
        return jsonify({
            'success': True,
            'portal_url': session.url
        })
        
    except Exception as e:
        print(f"Error creating customer portal session: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Check environment variables
    print("\n=== Environment Variables Check ===")
    print(f"OPENAI_API_KEY: {'Present' if OPENAI_API_KEY else 'Missing'}")
    print(f"SUPABASE_URL: {'Present' if SUPABASE_URL else 'Missing'} - Value: {SUPABASE_URL}")
    print(f"SUPABASE_KEY: {'Present' if SUPABASE_KEY else 'Missing'}")
    print(f"STRIPE_SECRET_KEY: {'Present' if stripe.api_key else 'Missing'}")
    print(f"STRIPE_WEBHOOK_SECRET: {'Present' if os.getenv('STRIPE_WEBHOOK_SECRET') else 'Missing'}")
    print(f"STRIPE_STARTER_PRICE_ID: {'Present' if os.getenv('STRIPE_STARTER_PRICE_ID') else 'Missing'}")
    print(f"STRIPE_GROWTH_PRICE_ID: {'Present' if os.getenv('STRIPE_GROWTH_PRICE_ID') else 'Missing'}")
    print(f"STRIPE_SCALE_PRICE_ID: {'Present' if os.getenv('STRIPE_SCALE_PRICE_ID') else 'Missing'}")
    print("=================================\n")
    
    app.run(debug=True)
