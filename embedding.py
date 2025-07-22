from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from supabase import create_client
import uuid
import time
import os

from dotenv import load_dotenv
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "search_engine"
openai_api_key = os.getenv("OPENAI_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

def get_point_id(product_id_str):
    # Use UUID5 (namespace + name) to deterministically generate UUID from string ID
    namespace = uuid.NAMESPACE_OID
    return str(uuid.uuid5(namespace, product_id_str))


# Connect
openai_client = OpenAI(api_key=openai_api_key)
qdrant = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_api_key,
)
supabase = create_client(supabase_url, supabase_key)

# Create collection
VECTOR_DIM = 1536
COLLECTION_NAME = "products"

# Check if collection exists
if not qdrant.collection_exists(COLLECTION_NAME):
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
    )
else:
    print(f"Collection '{COLLECTION_NAME}' already exists. Skipping creation.")


# Generate vector
def get_embedding(text):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

# Load product data from Supabase
response = supabase.table("search_engine").select(
    "product_id, name, brand, description, keywords, categories, colors, sizes"
).execute()

products = response.data


# Upload to Qdrant
points = []
for product in products:
    text_parts = [
        product.get("name", ""),
        product.get("brand", ""),
        product.get("description", ""),
        ", ".join(product.get("keywords", []) or []),
        ", ".join(product.get("categories", []) or [])
    ]
    combined_text = " ".join(text_parts)
    # Generate embedding with OpenAI
    vector = get_embedding(combined_text)

    point = PointStruct(
        id=get_point_id(product["product_id"]),
        vector=vector,
        payload=product
    )

    # Upsert this single point to Qdrant
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[point]
    )
    print(f"Uploaded {len(points)} products to Qdrant.")
    # exit(1)
    time.sleep(0.5)
