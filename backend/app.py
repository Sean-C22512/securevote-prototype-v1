from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import datetime
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from utils.hash_utils import generate_vote_hash

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# SECRET_KEY for JWT encoding
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'securevote-prototype-secret-key')

# MongoDB Connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/securevote')
client = MongoClient(MONGO_URI)
db = client.get_database()
users_collection = db.users
votes_collection = db.votes

# Hardcoded candidates list (To be replaced by database query in future if needed)
candidates = [
    {"id": 1, "name": "Candidate A", "party": "Party Alpha"},
    {"id": 2, "name": "Candidate B", "party": "Party Beta"},
    {"id": 3, "name": "Candidate C", "party": "Party Gamma"}
]

@app.route('/auth/login', methods=['POST'])
def login():
    """
    Login route.
    Accepts { "student_id": "12345" }.
    If user does not exist, creates a new user record.
    Returns a signed JWT containing the student_id.
    """
    data = request.get_json()
    student_id = data.get('student_id')

    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400
    
    # FUTURE: Add password validation here
    
    # Check if user exists, if not create one
    user = users_collection.find_one({'student_id': student_id})
    if not user:
        users_collection.insert_one({
            'student_id': student_id,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })

    # Generate a token
    token = jwt.encode({
        'student_id': student_id,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token})

@app.route('/candidates', methods=['GET'])
def get_candidates():
    """
    Returns the list of candidates.
    """
    return jsonify(candidates)

@app.route('/vote', methods=['POST'])
def cast_vote():
    """
    Cast a vote.
    Requires JWT authentication.
    Enforces one vote per user.
    """
    token = request.headers.get('Authorization')
    
    if not token:
        return jsonify({'error': 'Token is missing'}), 401

    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token.split(" ")[1]
            
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        student_id = data['student_id']
    except:
        return jsonify({'error': 'Invalid token'}), 401

    vote_data = request.get_json()
    if not vote_data or 'candidate_id' not in vote_data:
        return jsonify({'error': 'Invalid vote data'}), 400
    
    candidate_id = vote_data['candidate_id']
    # Verify candidate exists (optional for prototype but good practice)
    candidate_name = next((c['name'] for c in candidates if c['id'] == candidate_id), None)
    if not candidate_name:
         return jsonify({'error': 'Invalid candidate'}), 400

    # Check if user has already voted
    if votes_collection.find_one({'student_id': student_id}):
        return jsonify({'error': 'User has already voted'}), 403

    # FUTURE: Add cryptography/hashing here (AES encrypt vote, SHA-256 hash)
    """
    SECURITY NOTE — PROTOTYPE VERSION:
    This placeholder SHA-256 hash simulates part of the hybrid cryptographic workflow.
    Future implementation will include:
    - AES encryption of ballot data
    - RSA encryption of the AES key
    - SHA-256 hash-chaining for tamper detection
    """
    
    vote_record = {
        'student_id': student_id,
        'candidate': candidate_name, # Storing name for easier results aggregation for now
        'candidate_id': candidate_id,
        'timestamp': datetime.datetime.now(datetime.timezone.utc)
    }
    
    vote_hash = generate_vote_hash(vote_record)

    votes_collection.insert_one({
        **vote_record,
        "hash": vote_hash
    })
    
    return jsonify({'message': 'Vote cast successfully'}), 201

@app.route('/results', methods=['GET'])
def get_results():
    """
    Returns aggregated vote counts.
    """
    # Aggregate votes
    pipeline = [
        {"$group": {"_id": "$candidate", "count": {"$sum": 1}}}
    ]
    results = list(votes_collection.aggregate(pipeline))
    
    # Format results as requested: { "Candidate A": 10, ... }
    formatted_results = {item['_id']: item['count'] for item in results}
    
    # Ensure all candidates are represented even with 0 votes
    for cand in candidates:
        if cand['name'] not in formatted_results:
            formatted_results[cand['name']] = 0

    return jsonify(formatted_results)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
