#!/usr/bin/env python
# coding: utf-8
import sys
sys.path.append('./models')
sys.path.append('./helpers')
import json
from fastapi import FastAPI ,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from rank_bm25 import BM25Okapi
from pymongo import MongoClient
from flask_cors import CORS
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse , JSONResponse
from fastapi.templating import Jinja2Templates
import traceback
from decimal import Decimal
import psycopg2
import numpy as np 
from models.bm25_base import BM25_json
from models.desm import DESM_json

from pydantic import BaseModel
from typing import Dict

from sklearn.metrics import ndcg_score

class FeedbackItem(BaseModel):
    rank: str
    doc_id: str
    score: str
    userScore: str
    query: str
    algorithm: str
    session_id: str

class Feedback(BaseModel):
    __root__: Dict[str, FeedbackItem]



# Connect to the PostgreSQL database
conn = psycopg2.connect(
    host="localhost",
    database="SearchEngine",
    user="postgres",
    password="2580"
)

# Create a cursor object
cursor = conn.cursor()




app = FastAPI()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

# Add the following lines to enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS(app, resources={r"/*": {"origins": "https://localhost:300"}, "methods": ["GET", "POST"]})

@app.get("/search")
async def search(query: str,algorithm: str):
    
    user_input = query
    

    if algorithm == 'BM25':
        out_data, raw_scores = BM25_json(user_input)
        json_data = json.dumps(out_data)

        return json_data
    
    elif algorithm == 'DESM':
        out_data, raw_scores = DESM_json(user_input)
        json_data = json.dumps(out_data)
        
        return json_data


@app.post("/feedback")
async def send_feedback(feedback: Feedback):
    try:
        # Your feedback handling logic here
        print(feedback)

        # Extract the feedback data
        items = feedback.__root__
        rawScores = []
        userScore = []

        for key, item in items.items():
            session_id = int(item.session_id)
            query = item.query
            algorithm = item.algorithm
            userScore.append(int(item.userScore))
            rawScores.append((float(item.score)))

            # Insert the feedback data into the session table
        
        true_relevance = np.array(userScore).reshape(1,-1)
        scores = np.array(rawScores).reshape(1,-1)
        ndcg_score_ = ndcg_score(true_relevance, scores)

        cursor.execute("""
            INSERT INTO sessions (number, query, algorithm, userScore, rawscore, finalscore)
            VALUES (%s, %s, %s, %s, %s,%s)
        """, (session_id, query, algorithm, [userScore], [rawScores],ndcg_score_))

        # Commit the changes and close the cursor
        conn.commit()

        return 'Feedback received'

    except Exception as e:
        if isinstance(e, HTTPException) and e.status_code == 422:
            return JSONResponse(content={'message': 'Error'}, status_code=422)
        else:
            raise e
    else:
        return 'good work buddy'




templates = Jinja2Templates(directory="templates")


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def format_value(value):
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, list):
        return ", ".join(map(str, value[0]))
    else:
        return value



@app.get("/results", response_class=HTMLResponse)
async def get_results(request: Request):
    try:
        # Execute the SELECT query
        cursor.execute("SELECT * FROM sessions where number <> 1")
        
        # Fetch all the rows
        rows = cursor.fetchall()

        # Get the column names
        column_names = [desc[0] for desc in cursor.description]

        # Convert rows into a list of dictionaries
        results = [dict(zip(column_names, [format_value(v) for v in row])) for row in rows]


        # Render the results.html template with the results data
        return templates.TemplateResponse("results.html", {"request": request, "results": results})

    except Exception as e:
        print("Error in /results endpoint:")
        print(traceback.format_exc())  # Print the full traceback
        return JSONResponse(content={'message': 'Error: ' + str(e)}, status_code=500)

test = False
if test:
    from fastapi.testclient import TestClient 

    client = TestClient(app)

    feedback_json = """
    {
        "1": {
            "rank": "100",
            "doc_id": "007",
            "score": "0.999",
            "userScore": "1",
            "query": "hello Paris",
            "algorithm": "DESM",
            "session_id": "12600"
        },
        "2": {
            "rank": "1",
            "doc_id": "356",
            "score": "0.125",
            "userScore": "00",       
            "query": "hello Paris",
            "algorithm": "DESM",
            "session_id": "12600"
        }
    } 
    """

    # Test the endpoint
    response = client.post("/feedback", json=json.loads(feedback_json))

    print(response.status_code)
    print(response.json())
