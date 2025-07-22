from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def product_exists(product_id: str):
    res = supabase.table(SUPABASE_TABLE).select("product_id").eq("product_id", product_id).execute()
    return bool(res.data)

def upsert_to_supabase(product_data: dict):
    supabase.table(SUPABASE_TABLE).upsert(product_data).execute()
