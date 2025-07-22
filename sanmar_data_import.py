import requests
import xml.etree.ElementTree as ET
from supabase import create_client, Client
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
SOAP_URL = os.getenv("SOAP_URL")
SOAP_ID = os.getenv("SOAP_ID")
SOAP_PASSWORD = os.getenv("SOAP_PASSWORD")


# Setup Supabase
supabase_table = "search_engine"

# SOAP credentials

supabase: Client = create_client(supabase_url, supabase_key)



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

# Initial request to get sellable product IDs
url = SOAP_URL + "?WSDL"
payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
    xmlns:ns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" 
    xmlns:shar="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
    <soapenv:Header/>
    <soapenv:Body>
        <ns:GetProductSellableRequest>
            <shar:wsVersion>2.0.0</shar:wsVersion>
            <shar:id>{SOAP_ID}</shar:id>
            <shar:password>{SOAP_PASSWORD}</shar:password>
            <shar:isSellable>true</shar:isSellable>
        </ns:GetProductSellableRequest>
    </soapenv:Body>
</soapenv:Envelope>"""
headers = {'Content-Type': 'text/xml'}

response = requests.post(url, headers=headers, data=payload)
root = ET.fromstring(response.text)

namespaces = {
    'S': 'http://schemas.xmlsoap.org/soap/envelope/',
    'ns2': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/',
    '': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/'
}

product_sellables = root.findall('.//ns2:ProductSellable', namespaces)
unique_ids = set()
for item in product_sellables:
    product_id_el = item.find('.//{http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/}productId')
    if product_id_el is not None:
        unique_ids.add(product_id_el.text)
product_id_list = list(unique_ids)
print(f"Found {len(product_id_list)} unique product IDs")

# Function to fetch and parse detailed product data for each productId
def fetch_product_data(product_id: str) -> dict | None:
    payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
        xmlns:ns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" 
        xmlns:shar="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
        <soapenv:Header/>
        <soapenv:Body>
            <ns:GetProductRequest>
                <shar:wsVersion>2.0.0</shar:wsVersion>
                <shar:id>{SOAP_ID}</shar:id>
                <shar:password>{SOAP_PASSWORD}</shar:password>
                <shar:localizationCountry>US</shar:localizationCountry>
                <shar:localizationLanguage>en</shar:localizationLanguage>
                <shar:productId>{product_id}</shar:productId>
            </ns:GetProductRequest>
        </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {'Content-Type': 'text/xml'}

    try:
        resp = requests.post(SOAP_URL, headers=headers, data=payload)
        if resp.status_code != 200:
            print(f"[!] HTTP error for {product_id}: {resp.status_code}")
            return None

        xml_root = ET.fromstring(resp.text)

        # Namespaces for XML elements
        namespaces = {
            'ns2': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/',
            'def': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/'
        }

        product = xml_root.find('.//ns2:Product', namespaces)
        if product is None:
            print(f"[!] No product found in response for {product_id}")
            return None

        def get_text(elem, tag):
            e = elem.find(tag, namespaces)
            return e.text.strip() if e is not None and e.text else None

        product_id_val = get_text(product, 'def:productId')
        product_name = get_text(product, 'def:productName')
        product_brand = get_text(product, 'def:productBrand')
        image_url = get_text(product, 'def:primaryImageUrl')

        # Descriptions combined
        descriptions = [d.text.strip() for d in product.findall('def:description', namespaces) if d.text]
        combined_description = " ".join(descriptions)
        print(combined_description)


        # Keywords
        keywords = []
        keyword_array = product.find('ns2:ProductKeywordArray', namespaces)
        if keyword_array is not None:
            for kw in keyword_array.findall('def:ProductKeyword/def:keyword', namespaces):
                if kw.text:
                    keywords.append(kw.text.strip())


        # Categories and subcategories extraction
        categories = []
        product_categories = product.findall('ns2:ProductCategoryArray/def:ProductCategory', namespaces)
        for cat in product_categories:
            cat_name_el = cat.find('def:category', namespaces)
            sub_cat_el = cat.find('def:subCategory', namespaces)
            if cat_name_el is not None and cat_name_el.text:
                categories.append(cat_name_el.text.strip())
            if sub_cat_el is not None and sub_cat_el.text:
                # split comma separated subcategories and add individually
                categories.extend([s.strip() for s in sub_cat_el.text.split(',')])


        # Product parts info
        colors = set()
        sizes = set()
        gtin = None
        flags = {}

        product_parts = product.findall('ns2:ProductPartArray/ns2:ProductPart', namespaces)
        for part in product_parts:
            primary_color = part.find('ns2:primaryColor/def:Color/def:standardColorName', namespaces)
            if primary_color is not None and primary_color.text:
                colors.add(primary_color.text.strip())

            color_array = part.findall('ns2:ColorArray/def:Color/def:standardColorName', namespaces)
            for c in color_array:
                if c.text:
                    colors.add(c.text.strip())

            apparel_size = part.find('def:ApparelSize', namespaces)
            if apparel_size is not None:
                label_size = apparel_size.find('def:labelSize', namespaces)
                if label_size is not None and label_size.text:
                    sizes.add(label_size.text.strip())

            gtin_el = part.find('def:gtin', namespaces)
            if gtin_el is not None and gtin_el.text:
                gtin = gtin_el.text.strip()

            for flag_name in ['isRushService', 'isCloseout', 'isCaution', 'isOnDemand', 'isHazmat']:
                flag_el = part.find(f'def:{flag_name}', namespaces)
                if flag_el is not None and flag_el.text:
                    flags[flag_name] = flag_el.text.strip().lower() == 'true'

        product_data = {
            "product_id": product_id_val,
            "name": product_name,
            "brand": product_brand,
            "image_url": image_url,
            "description": combined_description,
            "keywords": keywords,
            "categories": categories,
            "colors": list(colors),
            "sizes": list(sizes),
            "gtin": gtin,
            "flags": flags
        }
        return product_data

    except Exception as e:
        print(f"[!] Exception for {product_id}: {e}")
        return None


def get_point_id(product_id_str):
    # Use UUID5 (namespace + name) to deterministically generate UUID from string ID
    namespace = uuid.NAMESPACE_OID
    return str(uuid.uuid5(namespace, product_id_str))

# Generate vector
def get_embedding(text):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

for pid in product_id_list:
    data = fetch_product_data(pid)
    if data:
        # Check if product already exists in Supabase
        existing = (
            supabase
            .table(supabase_table)
            .select("product_id")
            .eq("product_id", data["product_id"])
            .execute()
        )
        if existing.data:
            print(f"[i] Skipped {pid} — already exists in Supabase")
            continue
        print(f"Inserting data for {pid}")
        supabase.table(supabase_table).upsert(data).execute()
        # Upload to Qdrant
        points = []
        text_parts = [
            data["name"],
            data["brand"],
            data["description"],
            ", ".join(data["keywords"]),
            ", ".join(data["categories"])
        ]
        combined_text = " ".join(text_parts)
        # Generate embedding with OpenAI
        vector = get_embedding(combined_text)

        point = PointStruct(
            id=get_point_id(data["product_id"]),
            vector=vector,
            payload=data
        )

        # Upsert this single point to Qdrant
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[point]
        )
        print(f"Uploaded {len(points)} products to Qdrant.")
        # exit(1)
        time.sleep(0.5)
    else:
        print(f"[!] Skipped {pid} — no data found or error")

    time.sleep(0.5)  # avoid rate limits
