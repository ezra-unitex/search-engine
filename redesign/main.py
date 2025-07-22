from supabase_store import upsert_to_supabase, product_exists
from vector_store import generate_embedding, upsert_to_qdrant
from soap_client import get_client
import uuid

def get_point_id(product_id_str):
    # Use UUID5 (namespace + name) to deterministically generate UUID from string ID
    namespace = uuid.NAMESPACE_OID
    return str(uuid.uuid5(namespace, product_id_str))


def process_products(supplier):
    soap_client = get_client(supplier)
    product_ids = soap_client.get_sellable_product_ids()
    print(f"Found {len(product_ids)} unique sellable product IDs")

    for pid in product_ids:
        if product_exists(pid):
            print(f"✅ {pid} already exists in Supabase. Skipping.")
            continue

        data = soap_client.fetch_product_data(pid)
        if not data:
            print(f"❌ Failed to fetch or parse data for {pid}")
            continue

        # Upsert to Supabase
        upsert_to_supabase(data)

        # Prepare embedding input
        text = " ".join([
            data.get("name", ""),
            data.get("brand", ""),
            data.get("description", ""),
            ", ".join(data.get("keywords", [])),
            ", ".join(data.get("categories", []))
        ])

        vector = generate_embedding(text)

        # Upsert into Qdrant
        point_id = get_point_id(data["product_id"])
        upsert_to_qdrant(point_id, vector, data)

        print(f"🔄 Processed and uploaded: {pid}")

if __name__ == "__main__":
    process_products("edwards")
    # process_products("sanmar")
