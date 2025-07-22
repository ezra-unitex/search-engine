import os
from openai import OpenAI
from qdrant_client import QdrantClient
from supabase import create_client
from flask import Flask, request, jsonify, render_template_string

from dotenv import load_dotenv
load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "search_engine"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
SOAP_URL = os.getenv("SOAP_URL")
SOAP_ID = os.getenv("SOAP_ID")
SOAP_PASSWORD = os.getenv("SOAP_PASSWORD")

# Configurations
COLLECTION_NAME = "products"
VECTOR_DIM = 1536  # Dimension for OpenAI text-embedding-3-small




# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant = QdrantClient(
    url=QDRANT_URL,
    api_key=qdrant_api_key,
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

def get_embedding(text: str) -> list:
    """Generate vector embedding for input text using OpenAI."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    excluded_brands = request.args.getlist("excluded_brands")  # e.g., ?excluded_brands=Nike&excluded_brands=Adidas

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



@app.route("/")
def index():
    # Serve the search UI
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Product Search</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet" />
    <style>
        body { padding: 2rem; background: #f8f9fa; }
        .product-card { box-shadow: 0 2px 6px rgba(0,0,0,0.1); border-radius: 0.5rem; background: #fff; }
        .color-badge { cursor: default; user-select: none; margin-right: 0.3rem; margin-bottom: 0.3rem; }
        .keyword-badge { background-color: #0d6efd; color: white; margin-right: 0.3rem; margin-bottom: 0.3rem; }
    </style>
</head>
<body>
<div class="container">
    <h1 class="mb-4 text-center">Product Search</h1>

    <form id="search-form" class="mb-4" onsubmit="return false;">
        <div class="row justify-content-center g-2">
            <div class="col-md-5">
                <input
                    type="search"
                    id="query-input"
                    class="form-control"
                    placeholder="Search products..."
                />
            </div>
            <div class="col-md-4">
                <select id="excluded-brands" class="form-select" multiple>
                    <option value="Nike">Nike</option>
                    <option value="Adidas">Adidas</option>
                    <option value="Under Armour">Under Armour</option>
                    <option value="Sport-Tek">Sport-Tek</option>
                    <!-- Add more known brands here -->
                </select>
                <small class="form-text text-muted">Hold Ctrl/⌘ to select multiple brands to exclude.</small>
            </div>
            <div class="col-md-2">
                <button id="search-btn" class="btn btn-primary w-100">Search</button>
            </div>
        </div>
    </form>


    <div id="results" class="row g-4"></div>
</div>

<script>
const form = document.getElementById("search-form");
const input = document.getElementById("query-input");
const resultsDiv = document.getElementById("results");
const searchBtn = document.getElementById("search-btn");

function parseJSONField(field) {
    try {
        return JSON.parse(field);
    } catch {
        return [];
    }
}

function clearResults() {
    resultsDiv.innerHTML = "";
}

function createBadge(text, classes = "badge bg-secondary") {
    const span = document.createElement("span");
    span.className = classes + " me-1";
    span.textContent = text;
    return span;
}

function createProductCard(product) {
    const colors = parseJSONField(product.colors);
    const keywords = parseJSONField(product.keywords);
    const sizes = parseJSONField(product.sizes);
    const categories = parseJSONField(product.categories);

    const col = document.createElement("div");
    col.className = "col-md-6 col-lg-4";

    const card = document.createElement("div");
    card.className = "product-card p-3 h-100 d-flex flex-column";

    const img = document.createElement("img");
    img.src = product.image_url;
    img.alt = product.name;
    img.style.objectFit = "contain";
    img.style.height = "180px";
    img.className = "mb-3 rounded";

    const title = document.createElement("h5");
    title.textContent = product.name;

    const brand = document.createElement("div");
    brand.innerHTML = "<strong>Brand:</strong> " + (product.brand || "N/A");

    const pid = document.createElement("div");
    pid.innerHTML = "<strong>Product ID:</strong> " + (product.product_id || "N/A");

    const categoryDiv = document.createElement("div");
    categoryDiv.innerHTML = "<strong>Categories:</strong> " + (categories.join(", ") || "N/A");

    const desc = document.createElement("p");
    desc.textContent = product.description;

    const colorsDiv = document.createElement("div");
    colorsDiv.innerHTML = "<strong>Colors:</strong> ";
    colors.forEach(c => {
        const badge = createBadge(c, "badge bg-light text-dark color-badge");
        colorsDiv.appendChild(badge);
    });

    const sizesDiv = document.createElement("div");
    sizesDiv.innerHTML = "<strong>Sizes:</strong> " + (sizes.join(", ") || "N/A");

    const keywordsDiv = document.createElement("div");
    keywordsDiv.innerHTML = "<strong>Keywords:</strong> ";
    keywords.forEach(k => {
        const badge = createBadge(k, "keyword-badge");
        keywordsDiv.appendChild(badge);
    });

    card.append(img, title, brand, pid, categoryDiv, desc, colorsDiv, sizesDiv, keywordsDiv);
    col.appendChild(card);

    return col;
}

async function searchProducts() {
    const query = input.value.trim();
    const brandSelect = document.getElementById("excluded-brands");
    const excluded = Array.from(brandSelect.selectedOptions).map(opt => opt.value);

    if (!query) {
        alert("Please enter a search term.");
        return;
    }

    clearResults();
    searchBtn.disabled = true;
    searchBtn.textContent = "Searching...";

    const params = new URLSearchParams({ q: query });
    excluded.forEach(brand => params.append("excluded_brands", brand));

    try {
        const response = await fetch(`/search?${params.toString()}`);
        if (!response.ok) throw new Error("Search failed");

        const data = await response.json();
        if (data.length === 0) {
            resultsDiv.innerHTML = "<p class='text-center'>No results found.</p>";
            return;
        }

        data.forEach(product => {
            const card = createProductCard(product);
            resultsDiv.appendChild(card);
        });
    } catch (error) {
        console.error(error);
        resultsDiv.innerHTML = "<p class='text-center text-danger'>Error fetching results.</p>";
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = "Search";
    }
}


form.addEventListener("submit", searchProducts);
</script>
</body>
</html>
    """)

if __name__ == "__main__":
    app.run(debug=True)
