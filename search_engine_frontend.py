import os
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI
from qdrant_client import QdrantClient
from supabase import create_client
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "search_engine"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
SOAP_URL = os.getenv("SOAP_URL")
SOAP_INVENTORY_URL_SANMAR = os.getenv("SOAP_INVENTORY_URL_SANMAR")
SOAP_ID = os.getenv("SOAP_ID")
SOAP_PASSWORD = os.getenv("SOAP_PASSWORD")
COLLECTION_NAME = "products"
VECTOR_DIM = 1536

# Clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=qdrant_api_key)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

def get_embedding(text: str) -> list:
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def get_inventory(product_id, color, size):
    payload = f"""<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:ns=\"http://www.promostandards.org/WSDL/Inventory/2.0.0/\" xmlns:shar=\"http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/\">
        <soapenv:Header />
        <soapenv:Body>
            <ns:GetInventoryLevelsRequest>
                <shar:wsVersion>2.0.0</shar:wsVersion>
                <shar:id>{SOAP_ID}</shar:id>
                <shar:password>{SOAP_PASSWORD}</shar:password>
                <shar:productId>{product_id}</shar:productId>
                <shar:Filter>
                    <shar:LabelSizeArray>
                        <shar:labelSize>{size}</shar:labelSize>
                    </shar:LabelSizeArray>
                    <shar:PartColorArray>
                        <shar:partColor>{color}</shar:partColor>
                    </shar:PartColorArray>
                </shar:Filter>
            </ns:GetInventoryLevelsRequest>
        </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {'Content-Type': 'text/xml'}
    response = requests.post(SOAP_INVENTORY_URL_SANMAR, headers=headers, data=payload)
    return parse_inventory_response(response.text)

def parse_inventory_response(xml_str):
    ns = {'s': 'http://schemas.xmlsoap.org/soap/envelope/',
          'ns2': 'http://www.promostandards.org/WSDL/Inventory/2.0.0/',
          'shar': 'http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/'}

    root = ET.fromstring(xml_str)
    inventory_locations = []
    for loc in root.findall('.//shar:InventoryLocation', ns):
        location_name = loc.find('shar:inventoryLocationName', ns).text
        value = loc.find('shar:inventoryLocationQuantity/shar:Quantity/shar:value', ns).text
        inventory_locations.append({"location": location_name, "quantity": int(value)})
    return inventory_locations

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    excluded_brands = request.args.getlist("excluded_brands")
    if not query:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    query_vector = get_embedding(query)
    result = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        with_vectors=True,
        with_payload=True,
    )
    hits = result.points
    product_ids = [hit.payload.get("product_id", hit.id) for hit in hits]
    response = supabase.table(SUPABASE_TABLE).select("*").in_("product_id", product_ids).execute()
    id_to_product = {p["product_id"]: p for p in response.data}
    ordered_results = [id_to_product[pid] for pid in product_ids if pid in id_to_product]
    if excluded_brands:
        ordered_results = [p for p in ordered_results if p.get("brand") not in excluded_brands]
    return jsonify(ordered_results)

@app.route("/inventory", methods=["POST"])
def inventory():
    data = request.get_json()
    product_id = data.get("product_id")
    color = data.get("color")
    size = data.get("size")
    if not (product_id and color and size):
        return jsonify({"error": "Missing product_id, color, or size"}), 400
    locations = get_inventory(product_id, color, size)
    print(locations)
    return jsonify(locations)

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Product Search</title>
    <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css\" rel=\"stylesheet\" />
</head>
<body class=\"p-4\">
<div class=\"container\">
    <h1 class=\"text-center mb-4\">Product Search</h1>
    <form id=\"search-form\" class=\"mb-3\" onsubmit=\"return false;\">
        <div class=\"row\">
            <div class=\"col-md-6 mb-2\">
                <input id=\"query\" type=\"text\" class=\"form-control\" placeholder=\"Search products...\">
            </div>
            <div class=\"col-md-4 mb-2\">
                <select id=\"excluded-brands\" multiple class=\"form-select\">
                    <option value=\"Nike\">Nike</option>
                    <option value=\"Adidas\">Adidas</option>
                </select>
            </div>
            <div class=\"col-md-2 mb-2\">
                <button onclick=\"searchProducts()\" class=\"btn btn-primary w-100\">Search</button>
            </div>
        </div>
    </form>
    <div id=\"results\"></div>
</div>
<script>
async function searchProducts() {
    const query = document.getElementById("query").value;
    const brands = Array.from(document.getElementById("excluded-brands").selectedOptions).map(o => o.value);
    const params = new URLSearchParams({ q: query });
    brands.forEach(b => params.append("excluded_brands", b));

    const res = await fetch(`/search?${params.toString()}`);
    const data = await res.json();

    const container = document.getElementById("results");
    container.innerHTML = "";

    data.forEach(product => {
        const div = document.createElement("div");
        div.className = "card p-3 mb-3";
        div.innerHTML = `
            <img src="${product.image_url}" alt="${product.name}" style="object-fit:contain; height:180px;" class="mb-3 rounded">
            <h5>${product.name}</h5>
            <p><strong>Brand:</strong> ${product.brand || 'N/A'}</p>
            <p><strong>Product ID:</strong> ${product.product_id}</p>
            <select id="color-${product.product_id}" class="form-select mb-2">
                ${(JSON.parse(product.colors || '[]')).map(c => `<option>${c}</option>`).join('')}
            </select>
            <select id="size-${product.product_id}" class="form-select mb-2">
                ${(JSON.parse(product.sizes || '[]')).map(s => `<option>${s}</option>`).join('')}
            </select>
            <button onclick="checkInventory('${product.product_id}')" class="btn btn-info">Check Inventory</button>
            <div id="inv-${product.product_id}" class="mt-2"></div>
        `;
        container.appendChild(div);
    });
}

async function checkInventory(pid) {
    const color = document.getElementById(`color-${pid}`).value;
    const size = document.getElementById(`size-${pid}`).value;
    const res = await fetch("/inventory", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: pid, color: color, size: size })
    });
    const data = await res.json();
    console.log(data)
    const target = document.getElementById(`inv-${pid}`);
    if (!data || data.length === 0) {
        console.log("data is zero")
        target.innerHTML = "<p>Failed to retrieve data</p>";  
    } else {        
        console.log("data is not zero")
        target.innerHTML = '<ul>' + data.map(loc => 
            `<li>${loc.location}: ${loc.quantity}</li>`
        ).join('') + '</ul>';
    }
}
</script>
</body>
</html>
""")

if __name__ == "__main__":
    app.run(debug=True)
