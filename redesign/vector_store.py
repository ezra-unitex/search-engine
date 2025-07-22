from openai import OpenAI
from qdrant_client import QdrantClient, models
from config import QDRANT_URL, QDRANT_API_KEY, COLLECTION_NAME, VECTOR_DIM
from qdrant_client.models import PointStruct, VectorParams, Distance
import os

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def generate_embedding(text: str):
    res = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return res.data[0].embedding

def upsert_to_qdrant(point_id, vector, payload):
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(id=point_id, vector=vector, payload=payload)
        ]
    )
